import math
import mathutils
import collections
import logging
from typing import (OrderedDict, Optional, List, ChainMap)
import bpy

from .node import (Node, SceneGraphNode)

from .. import (debugging, xml_i3d)
from ..i3d import I3D
import numpy as np


class MaterialStorage:
    triangles: List = None

    def __init__(self):
        self.triangles = []

    def __str__(self):
        return f"triangles={len(self.triangles)}-{self.triangles}"

    def __repr__(self):
        return self.__str__()


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
    def __init__(self, subset_idx: int, position, normal, vertex_color, uvs, blend_ids=None,
                 blend_weights=None, generic_value=None):
        self._subset_idx = subset_idx
        self._position = position
        self._normal = normal
        self._vertex_color = vertex_color
        self._uvs = uvs
        self._blend_ids = blend_ids
        self._blend_weights = blend_weights
        self._generic_value = generic_value
        self._str = ''
        self._make_hash_string()

    def _make_hash_string(self):
        self._str = f"{self._subset_idx}{self._position}{self._normal}{self._vertex_color}"
        if self._generic_value is not None:
            self._str += f"{self._generic_value}"

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

    def blend_id_for_xml(self):
        return "{0:d}".format(self._blend_ids)

    def generic_value_for_xml(self):
        return "{}".format(self._generic_value)


class EvaluatedMesh:
    def __init__(self, i3d: I3D, mesh_object: bpy.types.Object, name: str = None,
                 reference_frame: mathutils.Matrix = None, node=None):
        self.name = name or mesh_object.data.name
        self.i3d = i3d
        self.object = None
        self.mesh = None
        self.logger = debugging.ObjectNameAdapter(logging.getLogger(f"{__name__}.{type(self).__name__}"),
                                                  {'object_name': self.name})
        self.generate_evaluated_mesh(mesh_object, reference_frame)
        self.node = node

    def generate_evaluated_mesh(self, mesh_object: bpy.types.Object, reference_frame: mathutils.Matrix = None) -> None:
        if self.i3d.get_setting('apply_modifiers'):
            self.object = mesh_object.evaluated_get(self.i3d.depsgraph)
            self.logger.debug("is exported with modifiers applied")
        else:
            self.object = mesh_object
            self.logger.debug("is exported without modifiers applied")

        self.mesh = self.object.to_mesh(preserve_all_data_layers=False, depsgraph=self.i3d.depsgraph)

        # If a reference is given transform the generated mesh by that frame to place it somewhere else than center of
        # the mesh origo
        if reference_frame is not None:
            self.mesh.transform(reference_frame.inverted() @ self.object.matrix_world)

        conversion_matrix = self.i3d.conversion_matrix
        if self.i3d.get_setting('apply_unit_scale'):
            self.logger.debug("applying unit scaling")
            conversion_matrix = \
                mathutils.Matrix.Scale(bpy.context.scene.unit_settings.scale_length, 4) @ conversion_matrix

        self.mesh.transform(conversion_matrix)
        if conversion_matrix.is_negative:
            self.mesh.flip_normals()
            self.logger.debug("conversion matrix is negative, flipping normals")

        # Calculates triangles from mesh polygons
        self.mesh.calc_loop_triangles()

    # On hold for the moment, it seems to be triggered at random times in the middle of an export which messes with
    # everything. Further investigation is needed.
    def __del__(self):
        pass
        # self.object.to_mesh_clear()


class IndexedTriangleSet(Node):
    ELEMENT_TAG = 'IndexedTriangleSet'
    NAME_FIELD_NAME = 'name'
    ID_FIELD_NAME = 'shapeId'

    def __init__(self, id_: int, i3d: I3D, evaluated_mesh: EvaluatedMesh, shape_name: Optional[str] = None,
                 is_merge_group: bool = False, is_generic: bool = False, bone_mapping: ChainMap = None):
        self.id: int = id_
        self.i3d: I3D = i3d
        self.evaluated_mesh: EvaluatedMesh = evaluated_mesh
        self.vertices: OrderedDict[Vertex, int] = collections.OrderedDict()
        self.triangles: List[List[int]] = list()  # List of lists of vertex indexes
        self.subsets: List[SubSet] = []
        self.is_merge_group = is_merge_group
        self.is_generic = is_generic
        self.is_generic_from_geometry_nodes = False
        self.bone_mapping: ChainMap = bone_mapping
        self.bind_index = 0
        self.child_index: int = 0
        self.generic_values_by_child_index = {}
        self.vertex_group_ids = {}
        self.tangent: bool = False
        self.material_ids: List[int] = []
        self.materials: dict[str, MaterialStorage] = {}

        self.pending_meshes = []
        self.final_vertices = np.array([])
        self.final_triangles = np.array([])
        self.final_subsets = []

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
        self.triangles = []
        self.vertices = collections.OrderedDict()
        next_vertex = 0
        next_index = 0
        for idx, subset in enumerate(self.subsets):
            self.logger.debug(f"Subset with index {idx}")
            subset.first_vertex = next_vertex
            subset.first_index = next_index
            next_vertex, next_index = self.process_subset(mesh, subset, subset_idx=idx)

    def process_subset(self, mesh: bpy.types.Mesh, subset: SubSet, triangle_offset: int = 0, subset_idx: int = 0) -> \
            tuple[int, int]:
        self.logger.debug(f"Processing subset: {subset}")

        zero_weight_vertices = set()
        for triangle_ in subset.triangles[triangle_offset:]:
            bind_index = 0
            if isinstance(triangle_, tuple):
                triangle = triangle_[0]
                bind_index = triangle_[1]
                mesh = triangle_[2]
            else:
                triangle = triangle_

            # Add a new empty container for the vertex indexes of the triangle
            self.triangles.append(list())
            for loop_index in triangle.loops:
                blender_vertex = mesh.vertices[mesh.loops[loop_index].vertex_index]

                # Add vertex color
                vertex_color = None
                if mesh.i3d_attributes.use_vertex_colors and len(mesh.color_attributes):
                    # Use the active color layer or fallback to the first (GE supports only one layer)
                    color_layer = mesh.color_attributes.active_color or mesh.color_attributes[0]

                    match color_layer.domain:
                        case 'CORNER':
                            # Color data is stored per corner/loop
                            vertex_color = color_layer.data[loop_index].color_srgb
                        case 'POINT':
                            # Color data is stored per vertex
                            color_vertex_index = mesh.loops[loop_index].vertex_index
                            vertex_color = color_layer.data[color_vertex_index].color_srgb
                        case _:
                            self.logger.warning(f"Incompatible color attribute {color_layer.name}: "
                                                f"domain={color_layer.domain}, data_type={color_layer.data_type}")

                generic_value = None
                if self.is_generic_from_geometry_nodes:
                    # Get the generic value from the mesh attributes, can come from Geometry Nodes
                    generic_layer = mesh.attributes["generic"]
                    generic_vertex_index = mesh.loops[loop_index].vertex_index
                    generic_value = generic_layer.data[generic_vertex_index].value
                elif self.is_generic:
                    generic_value = self.generic_values_by_child_index[bind_index]

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
                                self.logger.warning("Vertex has weights from more than 4 bones! Rest of bones will be"
                                                    "ignored for export!")
                                break

                    if len(blend_ids) == 0:
                        zero_weight_vertices.add(blender_vertex.index)

                    if len(blend_ids) < 4:
                        padding = [0] * (4 - len(blend_ids))
                        blend_ids += padding
                        blend_weights += padding

                vertex = Vertex(subset_idx,
                                blender_vertex.co.xyz,
                                mesh.loops[loop_index].normal,
                                vertex_color,
                                uvs,
                                bind_index if isinstance(triangle_, tuple) else blend_ids,
                                blend_weights,
                                generic_value)

                if vertex not in self.vertices:
                    vertex_index = len(self.vertices)
                    self.vertices[vertex] = vertex_index
                    subset.number_of_vertices += 1
                else:
                    vertex_index = self.vertices[vertex]

                self.triangles[-1].append(vertex_index)
            subset.number_of_indices += 3

        if zero_weight_vertices:
            self.logger.warning(f"Has {len(zero_weight_vertices)} vertices with 0.0 weight to all bones. "
                                "This will confuse GE and result in the mesh showing up as just a wireframe. "
                                "Please correct by assigning some weight to all vertices.")

        self.logger.debug(f"Subset {triangle.material_index} with '{len(subset.triangles)}' triangles and {subset}")
        return subset.first_vertex + subset.number_of_vertices, subset.first_index + subset.number_of_indices

    def populate_from_evaluated_mesh(self):
        """Populates mesh data from evaluated mesh."""
        mesh = self.evaluated_mesh.mesh
        # Check if evaluated mesh has "generic" attribute in its attributes
        if "generic" in mesh.attributes:
            self.logger.debug("'generic' was found in mesh attributes, likely from a 'Geometry Nodes' modifer. "
                              "Exporting as generic")
            self.is_generic = True
            self.is_generic_from_geometry_nodes = True

        self._ensure_materials_exist(mesh)
        self._process_mesh_triangles(mesh)
        self.process_subsets(mesh)

    def append_from_evaluated_mesh(self, mesh_to_append: EvaluatedMesh, generic_value: float = None):
        """Appends mesh data from another EvaluatedMesh to existing IndexedTriangleSet."""
        if not (self.is_merge_group or self.is_generic):
            self.logger.warning("Cannot add a mesh to an IndexedTriangleSet that is neither a merge group nor generic.")
            return

        if self.i3d.get_setting('use_numpy'):
            if self.is_generic:
                self.logger.debug(f"Queueing mesh '{mesh_to_append.mesh.name}' with generic value '{generic_value}'")
                self.pending_meshes.append({
                    'mesh_obj': mesh_to_append.mesh,
                    'id_value': generic_value or 0.0,  # The generic value
                })
            else:  # is_merge_group
                self.logger.debug(f"Queueing mesh '{mesh_to_append.mesh.name}' with bind index '{self.bind_index}'")
                self.pending_meshes.append({
                    'mesh_obj': mesh_to_append.mesh,
                    'id_value': self.bind_index,  # The singleBlendWeight bind ID
                })
                self.bind_index += 1
                return

        mesh = mesh_to_append.mesh
        self._ensure_materials_exist(mesh)

        if self.is_generic and generic_value is not None:
            self.logger.debug(f"Added mesh '{mesh.name}' with generic value '{generic_value}'")
            prev_child_index = self.child_index
            self.generic_values_by_child_index[prev_child_index] = generic_value
            self._process_mesh_triangles(mesh, index=prev_child_index, append=True)
            self.child_index += 1
        else:
            self.bind_index += 1
            self._process_mesh_triangles(mesh, index=self.bind_index, append=True)

        self.process_subsets(mesh)
        self.xml_elements['vertices'].clear()
        self.write_vertices()
        self.xml_elements['triangles'].clear()
        self.write_triangles()

        self.xml_elements['subsets'].clear()
        self._write_attribute('count', len(self.subsets), 'subsets')
        for subset in self.subsets:
            xml_i3d.SubElement(self.xml_elements['subsets'], 'Subset', subset.as_dict())

    def _ensure_materials_exist(self, mesh: bpy.types.Mesh) -> None:
        """Ensure that the mesh has at least one material, and if not, assign the default material."""
        if not len(mesh.materials):
            self.logger.warning(f"Mesh '{mesh.name}' has no materials, assigning default material")
            mesh.materials.append(self.i3d.get_default_material().blender_material)
            self.logger.info(f"Assigned default material '{mesh.materials[-1].name}'")

    def _process_mesh_triangles(self, mesh: bpy.types.Mesh, index: int = None, append: bool = False) -> None:
        """
        Processes triangles of the given mesh and assigns them to materials.
        - Ensures all triangles have valid materials.
        - Assigns triangles to `MaterialStorage` for merging or subsets otherwise.
        - Handles appending when merging multiple meshes.
        - Updates material IDs and determines if tangents are needed.

        Args:
            mesh (bpy.types.Mesh): The mesh whose triangles will be processed.
            index (int, optional): The index used when appending a new mesh.
            append (bool, optional): If True, appends triangles to an existing set.
        """
        unique_mats = {mat for mat in mesh.materials if mat is not None}  # Ignore empty material slots
        fallback_material = next(iter(unique_mats), None) if len(unique_mats) == 1 else None
        has_warned_for_invalid_index = False
        has_warned_for_empty_slot = False
        used_materials = set()
        material_to_subset = {} if not append else None  # Only used when creating new subsets

        for triangle in mesh.loop_triangles:
            # A triangle's material index may be invalid (out of range) if the mesh contains
            # corrupted or mismatched 'material_index' data. If detected, we assign a fallback material.
            if triangle.material_index >= len(mesh.materials) or triangle.material_index < 0:
                if not has_warned_for_invalid_index:
                    self.logger.warning("triangle(s) found with invalid material index, assigning fallback material")
                    has_warned_for_invalid_index = True
                # If the mesh has exactly one valid material, use it as fallback. Otherwise, use the default material.
                triangle_material = fallback_material or self.i3d.get_default_material().blender_material
            else:
                triangle_material = mesh.materials[triangle.material_index]
                # In Blender, it's possible to assign triangles to material slots that have no material. These show up
                # as `None` in the material list. If used, they are replaced with a fallback material during export.
                if triangle_material is None:
                    if not has_warned_for_empty_slot:
                        self.logger.warning("triangle(s) found with empty material slot, assigning fallback material")
                        has_warned_for_empty_slot = True
                    triangle_material = fallback_material or self.i3d.get_default_material().blender_material

            used_materials.add(triangle_material)

            if append:
                material_entry = self.materials.setdefault(triangle_material.name, MaterialStorage())
                material_entry.triangles.append((triangle, index, mesh))
            else:
                # If not appending, we need to determine whether to create a new subset
                if triangle_material not in material_to_subset:
                    material_to_subset[triangle_material] = SubSet()
                    self.subsets.append(material_to_subset[triangle_material])

                # Handle merging logic (merge groups store materials separately)
                if self.is_merge_group:
                    if triangle_material.name not in self.materials:
                        self.materials[triangle_material.name] = MaterialStorage()
                    self.materials[triangle_material.name].triangles.append((triangle, self.bind_index, mesh))
                else:
                    # Assign triangle to the appropriate subset
                    material_to_subset[triangle_material].add_triangle(triangle)

        unused_materials = set(mesh.materials) - set(used_materials)
        for mat in (m for m in unused_materials if m is not None):
            self.logger.warning(f"Material '{mat.name}' is not used by any triangle, material will be ignored!")

        self.material_ids = [self.i3d.add_material(m) for m in used_materials]
        self.tangent = self.tangent or any(self.i3d.materials[m_id].is_normalmapped() for m_id in self.material_ids)
        # Only clear and rebuild subsets when appending or using merge groups
        if append or self.is_merge_group:
            # Since a default processed shape has no node yet, restrict materialIds writing to append or merge groups
            ids = [self.i3d.materials[m].id for m in self.materials]
            self.evaluated_mesh.node._write_attribute('materialIds', ' '.join(map(str, ids)))
            # Rebuild subsets to ensure correct material assignment
            self.subsets.clear()
            for _key, mat in self.materials.items():
                subset = SubSet()
                subset.triangles = mat.triangles
                self.subsets.append(subset)

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
        elif self.is_generic:
            self._write_attribute('generic', True, 'vertices')
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
                vertex_attributes['bi'] = vertex.blend_id_for_xml()
            elif self.is_generic:
                vertex_attributes['g'] = vertex.generic_value_for_xml()
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

    def get_numpy_mesh_data(self, mesh: bpy.types.Mesh):
        """
        Efficiently extract mesh data using NumPy and foreach_get
        """
        num_verts = len(mesh.vertices)
        num_loops = len(mesh.loops)
        num_tris = len(mesh.loop_triangles)

        if not all([num_verts, num_loops, num_tris]):
            return None, None, None, None, None

        # Vertex data
        positions = np.empty((num_verts, 3), dtype=np.float32)
        mesh.vertices.foreach_get('co', positions.ravel())

        # Loop data
        loop_vertex_indices = np.empty(num_loops, dtype=np.int32)
        mesh.loops.foreach_get('vertex_index', loop_vertex_indices)

        normals = np.empty((num_loops, 3), dtype=np.float32)
        mesh.loops.foreach_get('normal', normals.ravel())

        # Triangle data
        tri_loop_indices = np.empty(num_tris * 3, dtype=np.int32)
        mesh.loop_triangles.foreach_get('loops', tri_loop_indices)
        tri_loop_indices = tri_loop_indices.reshape(num_tris, 3)

        tri_material_indices = np.empty(num_tris, dtype=np.int32)
        mesh.loop_triangles.foreach_get('material_index', tri_material_indices)

        # Optional data
        # Collect up to 4 UV layers (alphabetically sorted if needed)
        uvs = None
        uv_layers = mesh.uv_layers
        uv_keys = list(uv_layers.keys())
        if uv_keys:
            if self.i3d.get_setting('alphabetic_uvs'):
                uv_keys = sorted(uv_keys)
            max_uvs = min(4, len(uv_keys))
            uvs = np.empty((num_loops, max_uvs * 2), dtype=np.float32)
            for i, uv_key in enumerate(uv_keys[:max_uvs]):
                uv_data = np.empty((num_loops, 2), dtype=np.float32)
                uv_layers[uv_key].data.foreach_get('uv', uv_data.ravel())
                uvs[:, i * 2:(i + 1) * 2] = uv_data

        colors = None
        if len(mesh.color_attributes):
            colors = np.empty((num_loops, 4), dtype=np.float32)
            # Use color_srgb for linear color space, seems to be the way to go for colors to 1:1 Blender:GE
            mesh.color_attributes.active_color.data.foreach_get('color_srgb', colors.ravel())

        loop_positions = positions[loop_vertex_indices]

        return loop_positions, normals, uvs, colors, tri_loop_indices, tri_material_indices

    def process_meshes_numpy(self, meshes_to_process: list):
        """
        UNIVERSAL PROCESSOR for both single and merged meshes.
        Takes a list of dictionaries, where each dict contains a mesh and its ID value.
        """
        # The rest of the function is 99% the same as the one I provided before!
        # I'll paste it here again for completeness, with the new name.
        if not meshes_to_process:
            self.logger.debug("No meshes to process.")
            self.final_vertices, self.final_triangles, self.final_subsets = np.array([]), np.array([]), []
            return

        all_loop_data_blocks, all_triangle_blocks = [], []
        master_material_map = collections.OrderedDict()
        has_uvs, has_colors = False, False
        material_object_map = {}

        self.logger.debug(f"Starting processing of {len(meshes_to_process)} mesh blocks.")

        for item in meshes_to_process:
            mesh = item['mesh_obj']
            id_value = item['id_value']

            # 1a. Use our new, improved helper function.
            result = self.get_numpy_mesh_data(mesh)
            if result[0] is None:
                self.logger.debug(f"Skipping empty mesh '{mesh.name}'.")
                continue

            loop_positions, normals, uvs, colors, tri_loop_indices, tri_material_indices = result
            num_loops = len(loop_positions)

            if uvs is not None:
                has_uvs = True
            if colors is not None:
                has_colors = True

            # 1b. Build the primary data block.
            loop_vertex_cols = [loop_positions, normals]

            # For a standard mesh, id_value is None. We need to handle this.
            # This processor will now handle skinned meshes, merge groups, and generics.
            if self.bone_mapping is not None:
                # TODO: Add logic to extract blend weights and IDs here
                pass
            elif self.is_merge_group or self.is_generic:
                id_column = np.full((num_loops, 1), id_value, dtype=np.float32)
                loop_vertex_cols.append(id_column)

            if uvs is not None:
                loop_vertex_cols.append(uvs)
            if colors is not None:
                loop_vertex_cols.append(colors)

            mesh_loop_data = np.hstack(loop_vertex_cols)
            all_loop_data_blocks.append(mesh_loop_data)

            # 1c. Map materials. (This part is identical to before)
            remapped_tri_mats = np.empty_like(tri_material_indices)
            for i, tri_mat_idx in enumerate(tri_material_indices):
                if not (0 <= tri_mat_idx < len(mesh.materials)) or mesh.materials[tri_mat_idx] is None:
                    material = self.i3d.get_default_material().blender_material
                else:
                    material = mesh.materials[tri_mat_idx]
                if material.name not in master_material_map:
                    master_material_map[material.name] = len(master_material_map)
                    material_object_map[material.name] = material
                remapped_tri_mats[i] = master_material_map[material.name]

            # 1d. Combine triangle data. (Identical to before)
            mesh_triangles = np.hstack([tri_loop_indices, remapped_tri_mats.reshape(-1, 1)])
            all_triangle_blocks.append(mesh_triangles)

        # --- PART 2 & 3: Combination, Welding, Caching ---
        # This entire section is IDENTICAL to the function I provided before.
        # It takes the collected lists and produces the final_vertices, final_triangles, etc.
        # ... (omitted for brevity, it's the same as before)
        if not all_loop_data_blocks:
            self.logger.warning("All pending meshes were empty. No geometry to export.")
            self.final_vertices, self.final_triangles, self.final_subsets = np.array([]), np.array([]), []
            return

        # Vertically stack all the collected data blocks into two huge arrays.
        combined_loop_data = np.vstack(all_loop_data_blocks)

        # We must adjust the triangle loop indices to be correct for the `combined_loop_data` array.
        loop_offset = 0
        for i in range(len(all_triangle_blocks)):
            if i > 0:
                # The offset is the number of loops from all *previous* meshes.
                loop_offset += len(all_loop_data_blocks[i - 1])
            all_triangle_blocks[i][:, :3] += loop_offset  # Adjust the three loop indices

        combined_triangles = np.vstack(all_triangle_blocks)

        # --- PART 3: Subsetting, Welding, and Caching ---
        final_unique_verts_list, final_remapped_tris_list, final_subsets_info = [], [], []
        vertex_offset, triangle_offset = 0, 0

        for subset_idx in range(len(master_material_map)):
            mask = (combined_triangles[:, 3] == subset_idx)
            subset_tris_with_loops = combined_triangles[mask][:, :3]
            if subset_tris_with_loops.size == 0:
                continue

            loop_indices_for_subset = subset_tris_with_loops.flatten()
            subset_vertex_data = combined_loop_data[loop_indices_for_subset]

            unique_verts, inverse_indices = np.unique(subset_vertex_data, axis=0, return_inverse=True)
            remapped_tris = inverse_indices.reshape(-1, 3)

            final_unique_verts_list.append(unique_verts)
            final_remapped_tris_list.append(remapped_tris + vertex_offset)

            final_subsets_info.append({
                'firstVertex': vertex_offset, 'firstIndex': triangle_offset * 3,
                'numVertices': unique_verts.shape[0], 'numIndices': remapped_tris.size,
            })

            vertex_offset += unique_verts.shape[0]
            triangle_offset += remapped_tris.shape[0]

        self.final_vertices = np.vstack(final_unique_verts_list) if final_unique_verts_list else np.array([])
        self.final_triangles = np.vstack(final_remapped_tris_list) if final_remapped_tris_list else np.array([])
        self.final_subsets = final_subsets_info

        self.logger.debug(f"Hey ho materials: {master_material_map.keys()}, "
                          f"final vertices: {self.final_vertices.shape}, "
                          f"final triangles: {self.final_triangles.shape}, "
                          f"final subsets: {len(self.final_subsets)}")

        # Ensure materials are added to self.i3d.materials and get their IDs
        self.material_ids = []
        for name in master_material_map.keys():
            # Find the Blender material by name from the mesh or fallback
            mat = material_object_map.get(name)
            self.logger.debug(f"Processing material {name!r} with Blender material: {mat}")
            if mat is None:
                mat = self.i3d.get_default_material().blender_material
            mat_id = self.i3d.add_material(mat)
            self.material_ids.append(mat_id)
        self.logger.debug(f"Final material IDs: {self.material_ids}")
        self.final_has_uvs = has_uvs
        self.final_has_colors = has_colors

    def process_and_write_mesh_data(self):
        """
        This is the main workhorse. It processes mesh data (either single or
        merged) and writes the final results to the XML elements.
        """
        self.logger.debug(f"Starting final processing for shape '{self.name}'")

        # --- 1. GATHER MESHES ---
        meshes_to_process = []
        if self.is_merge_group or self.is_generic:
            meshes_to_process = self.pending_meshes
        else:
            # Standard mesh case
            meshes_to_process = [{'mesh_obj': self.evaluated_mesh.mesh, 'id_value': None}]

        # --- 2. PROCESS WITH NUMPY ---
        self.process_meshes_numpy(meshes_to_process)

        # --- 3. WRITE RESULTS TO XML ---
        # This is the XML writing logic, moved from populate_xml_element
        if self.final_vertices.size == 0:
            self.logger.warning(f"No vertices to export for shape '{self.name}'.")
            return

        self._write_attribute('count', self.final_vertices.shape[0], 'vertices')
        self._write_attribute('normal', True, 'vertices')
        if self.tangent:
            self._write_attribute('tangent', True, 'vertices')
        if self.final_has_uvs:
            # Determine the actual number of UV layers present
            num_uvs = 0
            if self.final_vertices.shape[1] > 6:
                num_uvs = (self.final_vertices.shape[1] - 6) // 2
            for count in range(num_uvs):
                self._write_attribute(f"uv{count}", True, 'vertices')

        for vert_row in self.final_vertices:
            vertex_attributes = {
                'p': "{0:.6f} {1:.6f} {2:.6f}".format(*vert_row[:3]),
                'n': "{0:.6f} {1:.6f} {2:.6f}".format(*vert_row[3:6])
            }
            if self.final_has_uvs:
                # Each UV should be two consecutive values; adjust slicing accordingly
                num_uvs = (len(vert_row) - 6) // 2
                for i in range(num_uvs):
                    uv_start = 6 + i * 2
                    uv_end = uv_start + 2
                    if uv_end <= len(vert_row):
                        vertex_attributes[f"t{i}"] = "{0:.6f} {1:.6f}".format(*vert_row[uv_start:uv_end])
            xml_i3d.SubElement(self.xml_elements['vertices'], 'v', vertex_attributes)

        self._write_attribute('count', self.final_triangles.shape[0], 'triangles')
        for tri in self.final_triangles:
            xml_i3d.SubElement(self.xml_elements['triangles'], 't', {'vi': "{0} {1} {2}".format(*tri[:3])})

        self._write_attribute('count', len(self.final_subsets), 'subsets')
        for subset_info in self.final_subsets:
            xml_i3d.SubElement(self.xml_elements['subsets'], 'Subset', {
                'firstVertex': str(subset_info['firstVertex']),
                'firstIndex': str(subset_info['firstIndex']),
                'numVertices': str(subset_info['numVertices']),
                'numIndices': str(subset_info['numIndices'])
            })

        owning_shape_node = self.evaluated_mesh.node
        if owning_shape_node:
            owning_shape_node._write_attribute('materialIds', ' '.join(map(str, self.material_ids)))
            self.logger.info(f"Wrote materialIds '{self.material_ids}' to ShapeNode '{owning_shape_node.name}'")
        else:
            self.logger.warning("Could not find owning ShapeNode to write materialIds attribute.")
        self.logger.info(f"Finished processing and writing data for shape '{self.name}'.")

    def populate_xml_element(self):
        # _process_bounding_volume needs to be called first, when deferring meshes self.evaluated_mesh:
        # bounding_volume_object = self.evaluated_mesh.mesh.i3d_attributes.bounding_volume_object
        #                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        # ReferenceError: StructRNA of type Mesh has been removed
        self._process_bounding_volume()
        import time
        start_time = time.time()
        if not self.i3d.get_setting('use_numpy'):
            self.logger.debug("Processing mesh without numpy.")
            if len(self.evaluated_mesh.mesh.vertices) == 0 or self.is_generic:
                if self.is_generic:
                    return  # Skip writing mesh data for the root object of merged children.
                self.logger.warning("has no vertices! Export of this mesh is aborted.")
                return
            self.populate_from_evaluated_mesh()
            self.logger.debug(f"Has '{len(self.subsets)}' subsets, "
                              f"'{len(self.triangles)}' triangles and "
                              f"'{len(self.vertices)}' vertices")
            self.write_vertices()
            self.write_triangles()
            # Subsets
            self._write_attribute('count', len(self.subsets), 'subsets')
            # Write subsets
            for subset in self.subsets:
                xml_i3d.SubElement(self.xml_elements['subsets'], 'Subset', subset.as_dict())
            self.logger.debug(f"Populated mesh '{self.evaluated_mesh.name}' in {time.time() - start_time:.4f} seconds, "
                              f"numpy={self.i3d.get_setting('use_numpy')}")
            self._process_bounding_volume()
            return

        self.logger.debug("Processing mesh with numpy.")

        if self.is_merge_group or self.is_generic:
            # Defer complex shapes
            self.logger.debug(f"Deferring population of '{self.name}' until all nodes are created.")
            if self not in self.i3d.deferred_shapes_to_populate:
                self.i3d.deferred_shapes_to_populate.append(self)
            return

        # For single meshes, we can process them immediately
        self.logger.debug(f"Processing mesh '{self.evaluated_mesh.name}' with numpy.")
        self.process_and_write_mesh_data()

        self.logger.debug(f"Populated mesh '{self.evaluated_mesh.name}' in {time.time() - start_time:.4f} seconds, "
                          f"numpy={self.i3d.get_setting('use_numpy')}")

    def _process_bounding_volume(self):
        bounding_volume_object = self.evaluated_mesh.mesh.i3d_attributes.bounding_volume_object
        if bounding_volume_object is not None:
            # Calculate the bounding volume center from the corners of the bounding box
            bv_center = mathutils.Vector([sum(x) for x in zip(*bounding_volume_object.bound_box)]) * 0.125
            # Transform the bounding volume center to world coordinates
            bv_center_world = bounding_volume_object.matrix_world @ bv_center
            # Get the translation offset between the bounding volume center in world coordinates
            # and the data objects world coordinates
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
            self.logger.debug("applying unit scaling")
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
            self.logger.warning("has no splines! Export of this curve is aborted.")
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

    def __init__(self, id_: int, shape_object: bpy.types.Object | None, i3d: I3D, parent: SceneGraphNode | None = None):
        self.shape_id = None
        super().__init__(id_=id_, blender_object=shape_object, i3d=i3d, parent=parent)

    @property
    def _transform_for_conversion(self) -> mathutils.Matrix:
        return self.i3d.conversion_matrix @ self.blender_object.matrix_local @ self.i3d.conversion_matrix.inverted()

    def add_shape(self):
        self.logger.debug(f"Adding shape for object '{self.blender_object.name}'")
        if self.blender_object.type == 'CURVE':
            self.shape_id = self.i3d.add_curve(EvaluatedNurbsCurve(self.i3d, self.blender_object))
            self.xml_elements['NurbsCurve'] = self.i3d.shapes[self.shape_id].element
        else:
            self.shape_id = self.i3d.add_shape(EvaluatedMesh(self.i3d, self.blender_object))
            self.xml_elements['IndexedTriangleSet'] = self.i3d.shapes[self.shape_id].element

    def populate_xml_element(self):
        self.logger.debug(f"Inside populate_xml_element for shape node with ID '{self.shape_id}'")
        self.add_shape()
        self.logger.debug(f"Inside populate_xml_element for shape node with ID '{self.shape_id}' after add_shape()")
        if self.blender_object.type == 'MESH':
            self._write_attribute('materialIds', ' '.join(map(str, self.i3d.shapes[self.shape_id].material_ids)))
        self._write_attribute('shapeId', self.shape_id)
        super().populate_xml_element()
