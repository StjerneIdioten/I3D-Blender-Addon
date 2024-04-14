import math
import mathutils
import collections
import logging
from typing import (OrderedDict, Optional, List, Dict, ChainMap, Union)
from itertools import zip_longest
import bpy

from .node import (Node, SceneGraphNode)

from .. import (debugging, utility, xml_i3d)
from ..i3d import I3D


class SubSet:
    def __init__(self):
        self.first_index = 0
        self.first_vertex = 0
        self.number_of_indices = 0
        self.number_of_vertices = 0
        self.triangles = []

    def as_dict(self):
        subset_attributes = {'firstIndex': f"{self.first_index}",
                             'firstVertex': f"{self.first_vertex}",
                             'numIndices': f"{self.number_of_indices}",
                             'numVertices': f"{self.number_of_vertices}"}
        return subset_attributes

    def __str__(self):
        return f'numTriangles="{len(self.triangles)}" ' \
               f'firstIndex="{self.first_index}" firstVertex="{self.first_vertex}" ' \
               f'numIndices="{self.number_of_indices}" numVertices="{self.number_of_vertices}"'

    def add_triangle(self, triangle):
        self.triangles.append(triangle)


class Vertex:
    def __init__(self, subset_idx: int, position, normal, vertex_color, uvs, blend_ids=None, blend_weights=None):
        self._subset_idx = subset_idx
        self._position = position
        self._normal = normal
        self._vertex_color = vertex_color
        self._uvs = uvs
        self._blend_ids = blend_ids
        self._blend_weights = blend_weights
        self._str = ''
        self._make_hash_string()

    def _make_hash_string(self):
        self._str = f"{self._subset_idx}{self._position}{self._normal}{self._vertex_color}"

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

    def blend_ids_for_xml(self):
        return "{0:d} {1:d} {2:d} {3:d}".format(*self._blend_ids)

    def blend_weights_for_xml(self):
        return "{0:.6f} {1:.6f} {2:.6f} {3:.6f}".format(*self._blend_weights)


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
        if self.i3d.get_setting('apply_modifiers'):
            self.object = mesh_object.evaluated_get(self.i3d.depsgraph)
            self.logger.debug(f"is exported with modifiers applied")
        else:
            self.object = mesh_object
            self.logger.debug(f"is exported without modifiers applied")

        self.mesh = self.object.to_mesh(preserve_all_data_layers=False, depsgraph=self.i3d.depsgraph)

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
        if bpy.app.version < (4, 1, 0):
            self.mesh.calc_normals_split()

    # On hold for the moment, it seems to be triggered at random times in the middle of an export which messes with
    # everything. Further investigation is needed.
    def __del__(self):
        pass
        #self.object.to_mesh_clear()


class IndexedTriangleSet(Node):
    ELEMENT_TAG = 'IndexedTriangleSet'
    NAME_FIELD_NAME = 'name'
    ID_FIELD_NAME = 'shapeId'

    def __init__(self, id_: int, i3d: I3D, evaluated_mesh: EvaluatedMesh, shape_name: Optional[str] = None,
                 is_merge_group: bool = False, bone_mapping: ChainMap = None, tangent = False):
        self.id: int = id_
        self.i3d: I3D = i3d
        self.evaluated_mesh: EvaluatedMesh = evaluated_mesh
        self.vertices: OrderedDict[Vertex, int] = collections.OrderedDict()
        self.triangles: List[List[int]] = list()  # List of lists of vertex indexes
        self.subsets: List[SubSet] = []
        self.is_merge_group = is_merge_group
        self.bone_mapping: ChainMap = bone_mapping
        self.bind_index = 0
        self.vertex_group_ids = {}
        self.tangent = tangent
        if shape_name is None:
            self.shape_name = self.evaluated_mesh.name
        else:
            self.shape_name = shape_name
        super().__init__(id_, i3d, None)

    def _create_xml_element(self) -> None:
        super()._create_xml_element()
        self.xml_elements['vertices'] = xml_i3d.SubElement(self.element, 'Vertices')
        self.xml_elements['triangles'] = xml_i3d.SubElement(self.element, 'Triangles')
        self.xml_elements['subsets'] = xml_i3d.SubElement(self.element, 'Subsets')

    @property
    def name(self):
        return self.shape_name

    @property
    def element(self):
        return self.xml_elements['node']

    @element.setter
    def element(self, value):
        self.xml_elements['node'] = value

    def process_subsets(self, mesh) -> None:
        next_vertex = 0
        next_index = 0
        for idx, subset in enumerate(self.subsets):
            self.logger.debug(f"Subset with index {idx}")
            subset.first_vertex = next_vertex
            subset.first_index = next_index
            next_vertex, next_index = self.process_subset(mesh, subset)

    def process_subset(self, mesh, subset: SubSet, triangle_offset: int = 0) -> tuple[int, int]:
        self.logger.debug(f"Processing subset: {subset}")
        for triangle in subset.triangles[triangle_offset:]:

            # Add a new empty container for the vertex indexes of the triangle
            self.triangles.append(list())

            for loop_index in triangle.loops:
                blender_vertex = mesh.vertices[mesh.loops[loop_index].vertex_index]


                # Add vertex color
                vertex_color = None
                if len(mesh.vertex_colors):
                    # Get the color from the active layer or first layer, since only one vertex color layer is supported in GE
                    color_layer = mesh.vertex_colors.active if mesh.vertex_colors.active is not None else mesh.vertex_colors[0]
                    vertex_color = color_layer.data[loop_index].color

                # Add uvs
                uvs = []
                uv_keys = mesh.uv_layers.keys()
                if self.i3d.settings['alphabetic_uvs']:
                    uv_keys = sorted(uv_keys)

                for count, uv_key in enumerate(uv_keys):
                    if count < 4:
                        uvs.append(mesh.uv_layers.get(uv_key).data[loop_index].uv)

                blend_weights = []
                blend_ids = []
                if self.bone_mapping is not None:
                    for vertex_group in blender_vertex.groups:
                        # Filter out any potential vertex groups that aren't related to armatures
                        if self.evaluated_mesh.object.vertex_groups[vertex_group.group].name in self.bone_mapping:
                            if len(blend_ids) < 4:
                                # Filters out weightings that are less than the decimal precision of i3d anyway
                                if not math.isclose(vertex_group.weight, 0, abs_tol=0.000001):
                                    if vertex_group.group not in self.vertex_group_ids:
                                        self.vertex_group_ids[vertex_group.group] = len(self.vertex_group_ids)
                                    blend_ids.append(self.vertex_group_ids[vertex_group.group])
                                    blend_weights.append(vertex_group.weight)
                            else:
                                self.logger.warning(f"Vertex has weights from more than 4 bones! Rest of bones will be"
                                                    f"ignored for export!")
                                break

                    if len(blend_ids) == 0:
                        self.logger.warning("Has a vertex with 0.0 weight to all bones. "
                                            "This will confuse GE and results in the mesh showing up as just a "
                                            "wireframe. Please correct by assigning some weight to all vertices")

                    if len(blend_ids) < 4:
                        padding = [0]*(4-len(blend_ids))
                        blend_ids += padding
                        blend_weights += padding

                vertex = Vertex(triangle.material_index,
                                blender_vertex.co.xyz,
                                mesh.loops[loop_index].normal,
                                vertex_color,
                                uvs,
                                blend_ids,
                                blend_weights)

                if vertex not in self.vertices:
                    vertex_index = len(self.vertices)
                    self.vertices[vertex] = vertex_index
                    subset.number_of_vertices += 1
                else:
                    vertex_index = self.vertices[vertex]

                self.triangles[-1].append(vertex_index)
            subset.number_of_indices += 3
        self.logger.debug(f"Subset {triangle.material_index} with '{len(subset.triangles)}' triangles and {subset}")
        return subset.first_vertex + subset.number_of_vertices, subset.first_index + subset.number_of_indices

    def populate_from_evaluated_mesh(self):
        mesh = self.evaluated_mesh.mesh

        if len(mesh.materials) == 0:
            self.logger.info(f"has no material assigned, assigning default material")
            mesh.materials.append(self.i3d.get_default_material().blender_material)
            self.logger.info(f"assigned default material i3d_default_material")
        
        for _ in mesh.materials:
            self.subsets.append(SubSet())

        has_warned_for_empty_slot = False
        for triangle in mesh.loop_triangles:
            triangle_material = mesh.materials[triangle.material_index]

            if triangle_material is None:
                if not has_warned_for_empty_slot: 
                    self.logger.warning(f"triangle(s) found with empty material slot, assigning default material")
                    has_warned_for_empty_slot = True
                triangle_material = self.i3d.get_default_material().blender_material

            # Add triangle to subset
            self.subsets[triangle.material_index].add_triangle(triangle)

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
            if mesh.materials[0].name != self.evaluated_mesh.mesh.materials[0].name:
                self.logger.warning(f"Mesh '{mesh.name}' has a different material from merge group root, "
                                    f"which is not allowed!")
                return

        triangle_offset = len(self.subsets[-1].triangles)
        vertex_offset = self.subsets[-1].number_of_vertices
        for triangle in mesh.loop_triangles:
            self.subsets[-1].add_triangle(triangle)

        self.bind_index += 1
        self.process_subset(mesh, self.subsets[-1], triangle_offset)
        self.write_vertices(vertex_offset)
        self.write_triangles(triangle_offset)
        subset = list(self.xml_elements['subsets'])[0]
        for key, value in self.subsets[-1].as_dict().items():
            subset.set(key, value)

    def write_vertices(self, offset=0):
        # Vertices
        self._write_attribute('count', len(self.vertices), 'vertices')
        self._write_attribute('normal', True, 'vertices')
        if self.tangent:
            self._write_attribute('tangent', True, 'vertices')
        for count, _ in enumerate(list(self.vertices.keys())[0].uvs_for_xml()):
            self._write_attribute(f"uv{count}", True, 'vertices')

        if self.is_merge_group:
            self._write_attribute('singleblendweights', True, 'vertices')
        elif self.bone_mapping is not None:
            self._write_attribute('blendweights', True, 'vertices')

        # Write vertices to xml
        vertices_has_colors = False
        for vertex in list(self.vertices.keys())[offset:]:
            vertex_attributes = {'p': vertex.position_for_xml(),
                                 'n': vertex.normal_for_xml()
                                 }

            for count, uv in enumerate(vertex.uvs_for_xml()):
                vertex_attributes[f"t{count}"] = uv

            vertex_color = vertex.vertex_color_for_xml()
            if vertex_color != '':
                vertices_has_colors = True
                vertex_attributes['c'] = vertex_color

            if self.is_merge_group:
                vertex_attributes['bi'] = str(self.bind_index)
            elif self.bone_mapping is not None:
                vertex_attributes['bw'] = vertex.blend_weights_for_xml()
                vertex_attributes['bi'] = vertex.blend_ids_for_xml()

            xml_i3d.SubElement(self.xml_elements['vertices'], 'v', vertex_attributes)

        if vertices_has_colors:
            self._write_attribute('color', True, 'vertices')

    def write_triangles(self, offset=0):
        self._write_attribute('count', len(self.triangles), 'triangles')

        # Write triangles to xml
        for triangle in self.triangles[offset:]:
            xml_i3d.SubElement(self.xml_elements['triangles'], 't', {'vi': "{0} {1} {2}".format(*triangle)})

    def populate_xml_element(self):
        if len(self.evaluated_mesh.mesh.vertices) == 0:
            self.logger.warning(f"has no vertices! Export of this mesh is aborted.")
            return
        self.populate_from_evaluated_mesh()
        self.logger.debug(f"Has '{len(self.subsets)}' subsets, "
                          f"'{len(self.triangles)}' triangles and "
                          f"'{len(self.vertices)}' vertices")

        self.write_vertices()
        self.write_triangles()

        # Subsets
        self._write_attribute('count', len(self.subsets), 'subsets')

        bounding_volume_object = self.evaluated_mesh.mesh.i3d_attributes.bounding_volume_object
        if bounding_volume_object is not None:
            # Calculate the bounding volume center from the corners of the bounding box
            bv_center = mathutils.Vector([sum(x) for x in zip(*bounding_volume_object.bound_box)]) * 0.125
            # Transform the bounding volume center to world coordinates
            bv_center_world = bounding_volume_object.matrix_world @ bv_center
            # Get the translation offset between the bounding volume center in world coordinates and the data objects world coordinates
            bv_center_offset = bv_center_world - self.evaluated_mesh.object.matrix_world.to_translation()
            # Get the bounding volume center in coordinates relative to the data object using it
            bv_center_relative = self.evaluated_mesh.object.matrix_world.to_3x3().inverted() @ bv_center_offset

            self._write_attribute(
                "bvCenter",
                bv_center_relative @ self.i3d.conversion_matrix.inverted(),
            )
            self._write_attribute(
                "bvRadius", max(bounding_volume_object.dimensions) / 2
            )

        # Write subsets
        for subset in self.subsets:
            xml_i3d.SubElement(self.xml_elements['subsets'], 'Subset', subset.as_dict())


class ControlVertex:
    def __init__(self, position):
        self._position = position
        self._str = ''
        self._make_hash_string()

    def _make_hash_string(self):
        self._str = f"{self._position}"

    def __str__(self):
        return self._str

    def __hash__(self):
        return hash(self._str)

    def __eq__(self, other):
        return f"{self!s}" == f'{other!s}'

    def position_for_xml(self):
        return "{0:.6f} {1:.6f} {2:.6f}".format(*self._position)


class EvaluatedNurbsCurve:
    def __init__(self, i3d: I3D, shape_object: bpy.types.Object, name: str = None,
                 reference_frame: mathutils.Matrix = None):
        if name is None:
            self.name = shape_object.data.name
        else:
            self.name = name
        self.i3d = i3d
        self.object = None
        self.curve_data = None
        self.logger = debugging.ObjectNameAdapter(logging.getLogger(f"{__name__}.{type(self).__name__}"),
                                                  {'object_name': self.name})
        self.control_vertices = []
        self.generate_evaluated_curve(shape_object, reference_frame)

    def generate_evaluated_curve(self, shape_object: bpy.types.Object, reference_frame: mathutils.Matrix = None):
        self.object = shape_object

        self.curve_data = self.object.to_curve(depsgraph=self.i3d.depsgraph)

        # If a reference is given transform the generated mesh by that frame to place it somewhere else than center of
        # the mesh origo
        if reference_frame is not None:
            self.curve_data.transform(reference_frame.inverted() @ self.object.matrix_world)

        conversion_matrix = self.i3d.conversion_matrix
        if self.i3d.get_setting('apply_unit_scale'):
            self.logger.debug(f"applying unit scaling")
            conversion_matrix = \
                mathutils.Matrix.Scale(bpy.context.scene.unit_settings.scale_length, 4) @ conversion_matrix

        self.curve_data.transform(conversion_matrix)


class NurbsCurve(Node):
    ELEMENT_TAG = 'NurbsCurve'
    NAME_FIELD_NAME = 'name'
    ID_FIELD_NAME = 'shapeId'

    def __init__(self, id_: int, i3d: I3D, evaluated_curve_data: EvaluatedNurbsCurve, shape_name: Optional[str] = None):
        self.id: int = id_
        self.i3d: I3D = i3d
        self.evaluated_curve_data: EvaluatedNurbsCurve = evaluated_curve_data
        self.control_vertex: OrderedDict[ControlVertex, int] = collections.OrderedDict()
        self.spline_type = None
        self.spline_form = None
        if shape_name is None:
            self.shape_name = self.evaluated_curve_data.name
        else:
            self.shape_name = shape_name
        super().__init__(id_, i3d, None)

    @property
    def name(self):
        return self.shape_name

    @property
    def element(self):
        return self.xml_elements['node']

    @element.setter
    def element(self, value):
        self.xml_elements['node'] = value

    def process_spline(self, spline):
        if spline.type == 'BEZIER':
            points = spline.bezier_points
            self.spline_type = "cubic"
        elif spline.type == 'NURBS':
            points = spline.points
            self.spline_type = "cubic"
        elif spline.type == 'POLY':
            points = spline.points
            self.spline_type = "linear"
        else:
            self.logger.warning(f"{spline.type} is not supported! Export of this curve is aborted.")
            return

        for loop_index, point in enumerate(points):
            ctrl_vertex = ControlVertex(point.co.xyz)
            self.control_vertex[ctrl_vertex] = loop_index

        self.spline_form = "closed" if spline.use_cyclic_u else "open"

    def populate_from_evaluated_nurbscurve(self):
        spline = self.evaluated_curve_data.curve_data.splines[0]
        self.process_spline(spline)

    def write_control_vertices(self):
        for control_vertex in list(self.control_vertex.keys()):
            vertex_attributes = {'c': control_vertex.position_for_xml()}

            xml_i3d.SubElement(self.element, 'cv', vertex_attributes)

    def populate_xml_element(self):
        if len(self.evaluated_curve_data.curve_data.splines) == 0:
            self.logger.warning(f"has no splines! Export of this curve is aborted.")
            return

        self.populate_from_evaluated_nurbscurve()
        if self.spline_type:
            self._write_attribute('type', self.spline_type, 'node')
        if self.spline_form:
            self._write_attribute('form', self.spline_form, 'node')
        self.logger.debug(f"Has '{len(self.control_vertex)}' control vertices")
        self.write_control_vertices()


class ShapeNode(SceneGraphNode):
    ELEMENT_TAG = 'Shape'

    def __init__(self, id_: int, shape_object: Optional[bpy.types.Object], i3d: I3D,
                 parent: Optional[SceneGraphNode] = None):
        self.shape_id = None
        self.tangent = False
        super().__init__(id_=id_, blender_object=shape_object, i3d=i3d, parent=parent)

    @property
    def _transform_for_conversion(self) -> mathutils.Matrix:
        return self.i3d.conversion_matrix @ self.blender_object.matrix_local @ self.i3d.conversion_matrix.inverted()

    def add_shape(self):
        if self.blender_object.type == 'CURVE':
            self.shape_id = self.i3d.add_curve(EvaluatedNurbsCurve(self.i3d, self.blender_object))
            self.xml_elements['NurbsCurve'] = self.i3d.shapes[self.shape_id].element
        else:
            self.shape_id = self.i3d.add_shape(EvaluatedMesh(self.i3d, self.blender_object), tangent=self.tangent)
            self.xml_elements['IndexedTriangleSet'] = self.i3d.shapes[self.shape_id].element

    def populate_xml_element(self):
        if self.blender_object.type == 'MESH':
            m_ids = [self.i3d.add_material(m.material) for m in self.blender_object.material_slots]
            self._write_attribute('materialIds', ' '.join(map(str, m_ids)) or str(self.i3d.add_material(self.i3d.get_default_material())))
            self.tangent = any((self.i3d.materials[m_id].is_normalmapped() for m_id in m_ids))
        self.add_shape()
        self.logger.debug(f"has shape ID '{self.shape_id}'")
        self._write_attribute('shapeId', self.shape_id)
        super().populate_xml_element()
