import bpy
import xml.etree.ElementTree as ET
import mathutils
import collections
import logging
from typing import (OrderedDict, Optional, List)
from .node import (SceneGraphNode, Node)
from ..i3d import I3D
from .. import debugging


class SubSet:
    def __init__(self, material_id: int):
        self.first_index = 0
        self.first_vertex = 0
        self.number_of_indices = 0
        self.number_of_vertices = 0
        self.triangles = []
        self.material_id = material_id

    def as_dict(self):
        subset_attributes = {'firstIndex': f"{self.first_index}",
                             'firstVertex': f"{self.first_vertex}",
                             'numIndices': f"{self.number_of_indices}",
                             'numVertices': f"{self.number_of_vertices}"}
        return subset_attributes

    def __str__(self):
        return f'materialId="{self.material_id}" numTriangles="{len(self.triangles)}" ' \
               f'firstIndex="{self.first_index}" firstVertex="{self.first_vertex}" ' \
               f'numIndices="{self.number_of_indices}" numVertices="{self.number_of_vertices}"'

    def add_triangle(self, triangle):
        self.triangles.append(triangle)


class Vertex:
    def __init__(self, material_name, position, normal, vertex_color, uvs):
        self._material_name = material_name
        self._position = position
        self._normal = normal
        self._vertex_color = vertex_color
        self._uvs = uvs
        self._str = ''
        self._make_hash_string()

    def _make_hash_string(self):
        self._str = f"{self._material_name}{self._position}{self._normal}{self._vertex_color}"

        for uv in self._uvs:
            self._str += f"{uv}"

    def __str__(self):
        return self._str

    def __hash__(self):
        return hash(self._str)

    def __eq__(self, other):
        return f"{self!s}" == f'{other!s}'

    def position_for_xml(self):
        return "{0:.6f} {1:.6f} {2:.6f}".format(*self._position)

    def normal_for_xml(self):
        return "{0:.6f} {1:.6f} {2:.6f}".format(*self._normal)

    def vertex_color_for_xml(self):
        if self._vertex_color is not None:
            return "{0:.6f} {1:.6f} {2:.6f} {3:.6f}".format(*self._vertex_color)
        else:
            return ''

    def uvs_for_xml(self):
        uvs = []
        for uv in self._uvs:
            uvs.append("{0:.6f} {1:.6f}".format(*uv))
        return uvs


class EvaluatedMesh:
    def __init__(self, i3d: I3D, mesh_object: bpy.types.Object, name: str = None,
                 reference_frame: mathutils.Matrix = None):
        if name is None:
            self.name = mesh_object.data.name
        else:
            self.name = name
        self.i3d = i3d
        self.object = None
        self.mesh = None
        self.logger = debugging.ObjectNameAdapter(logging.getLogger(f"{__name__}.{type(self).__name__}"),
                                                  {'object_name': self.name})
        self.generate_evaluated_mesh(mesh_object, reference_frame)

    def generate_evaluated_mesh(self, mesh_object: bpy.types.Object, reference_frame: mathutils.Matrix = None):
        # Evaluate the dependency graph to make sure that all data is evaluated. As long as nothing changes, this
        # should only be 'heavy' to call the first time a mesh is exported.
        # https://docs.blender.org/api/current/bpy.types.Depsgraph.html
        depsgraph = bpy.context.evaluated_depsgraph_get()
        if self.i3d.get_setting('apply_modifiers'):
            self.object = mesh_object.evaluated_get(depsgraph).copy()
            self.logger.debug(f"is exported with modifiers applied")
        else:
            self.object = mesh_object.copy()
            self.logger.debug(f"is exported without modifiers applied")

        self.mesh = self.object.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)

        # If a reference is given transform the generated mesh by that frame to place it somewhere else than center of
        # the mesh origo
        if reference_frame is not None:
            self.mesh.transform(reference_frame.inverted() @ self.object.matrix_world)

        conversion_matrix = self.i3d.conversion_matrix
        if self.i3d.get_setting('apply_unit_scale'):
            self.logger.debug(f"applying unit scaling")
            conversion_matrix = \
                mathutils.Matrix.Scale(bpy.context.scene.unit_settings.scale_length, 4) @ conversion_matrix

        self.mesh.transform(conversion_matrix)
        if conversion_matrix.is_negative:
            self.mesh.flip_normals()
            self.logger.debug(f"conversion matrix is negative, flipping normals")

        # Calculates triangles from mesh polygons
        self.mesh.calc_loop_triangles()
        # Recalculates normals after the scaling has messed with them
        self.mesh.calc_normals_split()

    def __del__(self):
        self.object.to_mesh_clear()
        bpy.data.objects.remove(self.object, do_unlink=True)


class IndexedTriangleSet(Node):
    ELEMENT_TAG = 'IndexedTriangleSet'
    NAME_FIELD_NAME = 'name'
    ID_FIELD_NAME = 'shapeId'

    def __init__(self, id_: int, i3d: I3D, evaluated_mesh: EvaluatedMesh, shape_name: Optional[str] = None,
                 is_merge_group: bool = False):
        self.id: int = id_
        self.i3d: I3D = i3d
        self.evaluated_mesh: EvaluatedMesh = evaluated_mesh
        self.vertices: OrderedDict[Vertex, int] = collections.OrderedDict()
        self.triangles: List[List[int]] = list()  # List of lists of vertex indexes
        self.subsets: OrderedDict[str, SubSet] = collections.OrderedDict()
        self.material_indexes: str = ''
        self.is_merge_group = is_merge_group
        self.bind_index = 0
        if shape_name is None:
            self.shape_name = self.evaluated_mesh.name
        else:
            self.shape_name = shape_name
        super().__init__(id_, i3d, None)

    def _create_xml_element(self) -> None:
        super()._create_xml_element()
        self.xml_elements['vertices'] = ET.SubElement(self.element, 'Vertices')
        self.xml_elements['triangles'] = ET.SubElement(self.element, 'Triangles')
        self.xml_elements['subsets'] = ET.SubElement(self.element, 'Subsets')

    @property
    def name(self):
        return self.shape_name

    @property
    def element(self):
        return self.xml_elements['node']

    @element.setter
    def element(self, value):
        self.xml_elements['node'] = value

    def process_subsets(self, mesh):
        for idx, (material_name, subset) in enumerate(self.subsets.items()):
            self.logger.debug(f"Subset with index [{idx}] based on material '{material_name}'")

            if idx > 0:
                self.logger.debug(f"Previous subset exists")
                _, previous_subset = list(self.subsets.items())[idx-1]
                subset.first_vertex = previous_subset.first_vertex + previous_subset.number_of_vertices
                subset.first_index = previous_subset.first_index + previous_subset.number_of_indices

            self.process_subset(mesh, material_name)

    def process_subset(self, mesh, material_name: str, triangle_offset: int = 0):
        subset = self.subsets[material_name]
        self.logger.debug(f"Processing subset: {subset}")
        for triangle in subset.triangles[triangle_offset:]:

            # Add a new empty container for the vertex indexes of the triangle
            self.triangles.append(list())

            for loop_index in triangle.loops:
                blender_vertex = mesh.vertices[mesh.loops[loop_index].vertex_index]

                # Add vertex color
                vertex_color = None
                if len(mesh.vertex_colors):
                    # Get the color from the active layer, since only one vertex color layer is supported in GE
                    vertex_color = mesh.vertex_colors.active.data[loop_index].color

                # Add uvs
                uvs = []
                for count, uv in enumerate(mesh.uv_layers):
                    if count < 4:
                        uvs.append(uv.data[loop_index].uv)

                vertex = Vertex(material_name,
                                blender_vertex.co.xyz,
                                mesh.loops[loop_index].normal,
                                vertex_color,
                                uvs)

                if vertex not in self.vertices:
                    vertex_index = len(self.vertices)
                    self.vertices[vertex] = vertex_index
                    subset.number_of_vertices += 1
                else:
                    vertex_index = self.vertices[vertex]

                self.triangles[-1].append(vertex_index)

            subset.number_of_indices += 3

        self.logger.debug(f"Has subset '{material_name}' with '{len(subset.triangles)}' triangles and {subset}")

    def populate_from_evaluated_mesh(self):
        mesh = self.evaluated_mesh.mesh
        if len(mesh.materials) == 0:
            self.logger.info(f"has no material assigned, assigning default material")
            mesh.materials.append(self.i3d.get_default_material().blender_material)
            self.logger.info(f"assigned default material i3d_default_material")

        for triangle in mesh.loop_triangles:
            triangle_material = mesh.materials[triangle.material_index]
            if triangle_material.name not in self.subsets:
                self.logger.info(f"Has material {triangle_material.name!r}")
                material_id = self.i3d.add_material(triangle_material)
                self.subsets[triangle_material.name] = SubSet(material_id)

            # Add triangle to subset
            self.subsets[triangle_material.name].add_triangle(triangle)

        self.process_subsets(mesh)

    def append_from_evaluated_mesh(self, mesh_to_append):
        if not self.is_merge_group:
            self.logger.warning("Can't add a mesh to a IndexedTriangleSet that is not a merge group")
            return

        # Material checks for subset consistency
        mesh = mesh_to_append.mesh
        if len(mesh.materials) == 0:
            self.logger.warning(f"Mesh '{mesh.name}' to be added has no materials, "
                                f"mergegroups need to share the same subset!")
            return
        elif len(mesh.materials) > 1:
            self.logger.warning(f"Mesh '{mesh.name}' has more than one material, "
                                f"merge groups need to share the same subset!")
            return
        else:
            if mesh.materials[0].name not in self.subsets:
                self.logger.warning(f"Mesh '{mesh.name}' has a different material from merge group root, "
                                    f"which is not allowed!")
                return

        material_name = mesh.materials[0].name
        triangle_offset = len(self.subsets[material_name].triangles)
        vertex_offset = self.subsets[material_name].number_of_vertices
        for triangle in mesh.loop_triangles:
            self.subsets[material_name].add_triangle(triangle)

        self.bind_index += 1
        self.process_subset(mesh, material_name, triangle_offset)
        self.write_vertices(vertex_offset)
        self.write_triangles(triangle_offset)
        list(self.xml_elements['subsets'])[0].attrib = self.subsets[material_name].as_dict()

    def write_vertices(self, offset=0):
        # Vertices
        self._write_attribute('count', len(self.vertices), 'vertices')
        self._write_attribute('normal', True, 'vertices')
        self._write_attribute('tangent', True, 'vertices')
        for count, _ in enumerate(list(self.vertices.keys())[0].uvs_for_xml()):
            self._write_attribute(f"uv{count}", True, 'vertices')

        if self.is_merge_group:
            self._write_attribute('singleblendweights', True, 'vertices')

        # Write vertices to xml
        for vertex in list(self.vertices.keys())[offset:]:
            vertex_attributes = {'p': vertex.position_for_xml(),
                                 'n': vertex.normal_for_xml()
                                 }

            for count, uv in enumerate(vertex.uvs_for_xml()):
                vertex_attributes[f"t{count}"] = uv

            vertex_color = vertex.vertex_color_for_xml()
            if vertex_color != '':
                vertex_attributes['c'] = vertex_color

            if self.is_merge_group:
                vertex_attributes['bi'] = str(self.bind_index)

            ET.SubElement(self.xml_elements['vertices'], 'v', vertex_attributes)

    def write_triangles(self, offset=0):
        self._write_attribute('count', len(self.triangles), 'triangles')

        # Write triangles to xml
        for triangle in self.triangles[offset:]:
            ET.SubElement(self.xml_elements['triangles'], 't', {'vi': "{0} {1} {2}".format(*triangle)})

    def populate_xml_element(self):
        self.populate_from_evaluated_mesh()
        self.logger.debug(f"Has '{len(self.subsets)}' subsets, "
                          f"'{len(self.triangles)}' triangles and "
                          f"'{len(self.vertices)}' vertices")

        self.write_vertices()
        self.write_triangles()

        # Subsets
        self._write_attribute('count', len(self.subsets), 'subsets')

        # Write subsets
        for _, subset in self.subsets.items():
            self.material_indexes += f"{subset.material_id}"
            ET.SubElement(self.xml_elements['subsets'], 'Subset', subset.as_dict())

        # Removes the last whitespace from the string, since an extra will always be added
        self.material_indexes = self.material_indexes.strip()


class ShapeNode(SceneGraphNode):
    ELEMENT_TAG = 'Shape'

    def __init__(self, id_: int, mesh_object: [bpy.types.Object, None], i3d: I3D,
                 parent: [SceneGraphNode or None] = None):
        self.shape_id = None
        super().__init__(id_=id_, blender_object=mesh_object, i3d=i3d, parent=parent)

    @property
    def _transform_for_conversion(self) -> mathutils.Matrix:
        return self.i3d.conversion_matrix @ self.blender_object.matrix_local @ self.i3d.conversion_matrix.inverted()

    def add_shape(self):
        self.shape_id = self.i3d.add_shape(EvaluatedMesh(self.i3d, self.blender_object))

    def populate_xml_element(self):
        self.add_shape()
        self.logger.debug(f"has shape ID '{self.shape_id}'")
        self._write_attribute('shapeId', self.shape_id)
        self._write_attribute('materialIds', self.i3d.shapes[self.shape_id].material_indexes)
        super().populate_xml_element()