import logging
import dataclasses
from dataclasses import dataclass
import numpy as np
import mathutils
from collections import OrderedDict, ChainMap, defaultdict
import bpy

from .node import Node, SceneGraphNode

from .. import debugging, xml_i3d
from ..i3d import I3D


class EvaluatedMesh:
    def __init__(self, i3d: I3D, mesh_object: bpy.types.Object, name: str = None,
                 reference_frame: mathutils.Matrix = None, node: SceneGraphNode = None):
        self.node = node
        self.name = name or mesh_object.data.name
        self.i3d = i3d
        self.object = None
        self.mesh = None
        self.logger = debugging.ObjectNameAdapter(logging.getLogger(f"{__name__}.{type(self).__name__}"),
                                                  {'object_name': self.name})
        self.generate_evaluated_mesh(mesh_object, reference_frame)

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


@dataclass
class MeshExtraction:
    loop_positions: np.ndarray         # (num_loops, 3) positions per face corner (loop)
    normals: np.ndarray                # (num_loops, 3) normals per face corner (loop)
    uvs: np.ndarray | None             # List of (num_loops, 2) UV arrays or None
    colors: np.ndarray | None          # (num_loops, 4) RGBA or None
    loop_vertex_indices: np.ndarray    # (num_loops,) mapping loop to vertex
    blend_indices: np.ndarray | None   # (num_verts, 4) or None
    blend_weights: np.ndarray | None   # (num_verts, 4) or None
    triangle_loop_indices: np.ndarray  # (num_tris, 3) indices of loops for each triangle
    tri_material_indices: np.ndarray   # (num_tris,) material slot for each triangle
    materials: list                    # List of *non-None* Blender materials


@dataclass
class LocalMeshResult:
    unique_dots: np.ndarray
    triangles: np.ndarray
    material_indices: np.ndarray
    mesh_obj: bpy.types.Mesh


@dataclass
class TriangleAssignment:
    mesh_data: MeshExtraction
    loop_indices: np.ndarray  # shape (3,)
    id_value: float


class IndexedTriangleSet(Node):
    """
    Represents a collection of triangles (possibly merged from multiple meshes) to be exported as a single
    IdexedTriangleSet element in the I3D file. Handles mesh data extraction, attribute packing, material assignment,
    vertex deduplication, and final XML output.
    """
    ELEMENT_TAG = 'IndexedTriangleSet'
    NAME_FIELD_NAME = 'name'
    ID_FIELD_NAME = 'shapeId'

    def __init__(self, id_: int, i3d: I3D, evaluated_mesh: EvaluatedMesh, *,
                 shape_name: str | None = None,
                 is_merge_group: bool = False,
                 is_generic: bool = False,
                 bone_mapping: ChainMap = None):
        self.id: int = id_
        self.i3d: I3D = i3d
        self.evaluated_mesh: EvaluatedMesh = evaluated_mesh
        self.shape_name: str = shape_name or self.evaluated_mesh.name
        self.bounding_volume_object: bpy.types.Object | None = \
            self.evaluated_mesh.mesh.i3d_attributes.bounding_volume_object

        self.is_generic: bool = is_generic
        self.is_generic_from_geometry_nodes: bool = False
        self.is_merge_group: bool = is_merge_group
        self.bone_mapping: ChainMap = bone_mapping

        self.pending_meshes: list[dict] = []
        self.bind_index: int = 0

        self.material_ids: list[int] = []
        self.tangent: bool = False
        self.final_skin_bind_node_ids: list[int] = []

        self.final_has_uvs: bool = False
        self.final_max_uv_layers: int = 0
        self.final_has_colors: bool = False

        # self.child_index: int = 0
        # self.generic_values_by_child_index = {}

        self.final_vertices = np.array([])
        self.final_triangles = np.array([])
        self.final_subsets = []
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

    def append_from_evaluated_mesh(self, mesh_to_append: EvaluatedMesh, generic_value: float = None):
        """Appends mesh data from another EvaluatedMesh to the pending queue."""
        if self.is_generic:
            self.logger.debug(f"Queueing mesh {mesh_to_append.mesh.name!r} with generic value '{generic_value}'")
            self.pending_meshes.append({
                'mesh_obj': mesh_to_append.mesh,
                'object': mesh_to_append.object,
                'id_value': generic_value or 0.0,  # The generic value
            })
            return
        if self.is_merge_group:
            self.logger.debug(f"Queueing mesh {mesh_to_append.mesh.name!r} with bind index '{self.bind_index}'")
            self.pending_meshes.append({
                'mesh_obj': mesh_to_append.mesh,
                'object': mesh_to_append.object,
                'id_value': self.bind_index,  # The index into the final skinBindNodeIds list
            })
            self.bind_index += 1
            return
        self.logger.warning("Cannot add a mesh to an IndexedTriangleSet that is neither a merge group nor generic.")

    def _extract_mesh_data(self, mesh: bpy.types.Mesh, obj: bpy.types.Object) -> MeshExtraction | None:
        """Extracts mesh data from a Blender mesh object and returns it in a structured format."""
        num_verts = len(mesh.vertices)
        num_loops = len(mesh.loops)
        num_tris = len(mesh.loop_triangles)

        if not all([num_verts, num_loops, num_tris]):
            self.logger.warning(f"Object {obj.name!r} (mesh {mesh.name!r}) has no vertices, loops, or triangles. "
                                "Skipping extraction.")
            return None

        if not len(mesh.materials):
            self.logger.warning(f"Object {obj.name!r} (mesh {mesh.name!r}) has no materials. "
                                "Assigning default material for export.")
            mesh.materials.append(self.i3d.get_default_material().blender_material)
        else:
            # Fill empty material slots with single valid material (if exactly one), otherwise use default
            non_none_materials = [mat for mat in mesh.materials if mat is not None]
            fallback_material = (non_none_materials[0] if len(non_none_materials) == 1
                                 else self.i3d.get_default_material().blender_material)
            for i, mat in enumerate(mesh.materials):
                if mat is None:
                    self.logger.warning(
                        f"Object {obj.name!r} (mesh {mesh.name!r}) has an empty material slot at index {i}. "
                        f"Assigning fallback/default material {fallback_material.name!r} for export."
                    )
                    mesh.materials[i] = fallback_material

        # Vertex positions
        positions = np.empty((num_verts, 3), dtype=np.float32)
        mesh.vertices.foreach_get('co', positions.ravel())
        # Loop data
        loop_vertex_indices = np.empty(num_loops, dtype=np.int32)
        mesh.loops.foreach_get('vertex_index', loop_vertex_indices)
        normals = np.empty((num_loops, 3), dtype=np.float32)
        mesh.loops.foreach_get('normal', normals.ravel())
        # Triangles
        tri_loop_indices = np.empty(num_tris * 3, dtype=np.int32)
        mesh.loop_triangles.foreach_get('loops', tri_loop_indices)
        tri_loop_indices = tri_loop_indices.reshape(num_tris, 3)
        tri_material_indices = np.empty(num_tris, dtype=np.int32)
        mesh.loop_triangles.foreach_get('material_index', tri_material_indices)

        uvs = None
        uv_layers = mesh.uv_layers
        uv_keys = list(uv_layers.keys())
        if uv_keys:
            if self.i3d.get_setting('alphabetic_uvs'):
                uv_keys = sorted(uv_keys)
            uvs = [np.zeros((num_loops, 2), dtype=np.float32) for _ in range(self.final_max_uv_layers)]
            for i, uv_key in enumerate(uv_keys[:self.final_max_uv_layers]):
                uv_layers[uv_key].data.foreach_get('uv', uvs[i].ravel())

        colors = None
        if len(mesh.color_attributes):
            # Fallback to first layer if no active color layer is set
            color_layer = mesh.color_attributes.active_color or mesh.color_attributes[0]
            match color_layer.domain:
                case 'CORNER':  # Color data stored per corner (loop)
                    colors = np.empty((num_loops, 4), dtype=np.float32)
                    color_layer.data.foreach_get('color_srgb', colors.ravel())
                case 'POINT':  # Color data stored per vertex
                    verts_colors = np.empty((num_verts, 4), dtype=np.float32)
                    color_layer.data.foreach_get('color_srgb', verts_colors.ravel())
                    colors = verts_colors[loop_vertex_indices]
                case _:
                    self.logger.warning(f"Unsupported color domain '{color_layer.domain}' for mesh '{mesh.name}'.")

        # NOTE: Vertex groups are stored on the object and not the mesh
        vert_bone_indices, vert_bone_weights = self._extract_skinning_data(mesh, obj)

        return MeshExtraction(
            loop_positions=positions[loop_vertex_indices],
            normals=normals,
            uvs=uvs,
            colors=colors,
            loop_vertex_indices=loop_vertex_indices,
            blend_indices=vert_bone_indices,
            blend_weights=vert_bone_weights,
            triangle_loop_indices=tri_loop_indices,
            tri_material_indices=tri_material_indices,
            materials=mesh.materials[:]
        )

    def _extract_skinning_data(self,
                               mesh: bpy.types.Mesh,
                               mesh_object: bpy.types.Object) -> tuple[np.ndarray | None, np.ndarray | None]:
        """Extracts, processes, and normalizes skinning data for up to 4 bone influences."""
        if not self.bone_mapping:
            return None, None  # Not a skinned mesh
        if not mesh_object.vertex_groups:
            self.logger.debug(
                f"Object {mesh_object.name!r} (mesh {mesh.name!r}) has no vertex groups. Skipping skinning."
            )
            return None, None  # Was initialized as skinned mesh, but has no vertex groups
        num_verts = len(mesh.vertices)

        # Map Blenders vertex groups to the final bone indices for the i3d file
        vg_map = {vg.index: self.bone_mapping[vg.name]
                  for vg in mesh_object.vertex_groups if vg.name in self.bone_mapping}
        if not vg_map:
            self.logger.warning(f"Object {mesh_object.name!r} (mesh {mesh.name!r}) is skinned "
                                "but has no vertex groups matching the armature bones.")
            return None, None

        # The 'skinBindNodeIds' attribute must be sorted by node ID. This creates the final mapping.
        self.final_skin_bind_node_ids = sorted(vg_map.values())
        node_id_to_final_index = {node_id: i for i, node_id in enumerate(self.final_skin_bind_node_ids)}

        # Extract all raw weight data from the mesh vertices
        groups_per_vert = np.array([len(v.groups) for v in mesh.vertices], dtype=np.int32)
        if (total_weights_count := groups_per_vert.sum()) == 0:
            self.logger.debug(f"Object {mesh_object.name!r} (mesh {mesh.name!r}) has no skinning weights. "
                              "Skipping skinning data extraction.")
            return None, None

        # Pre-allocate lists and fill them with zeros
        all_weights_list = [0.0] * total_weights_count
        all_group_indices_list = [0] * total_weights_count

        cursor = 0
        for i, vert in enumerate(mesh.vertices):
            if (num_groups := groups_per_vert[i]) == 0:
                continue
            vert_weights = np.empty(num_groups, dtype=np.float32)
            vert.groups.foreach_get('weight', vert_weights)
            vert_indices = np.empty(num_groups, dtype=np.int32)
            vert.groups.foreach_get('group', vert_indices)
            # Place the weights and indices in the final lists
            all_weights_list[cursor:cursor + num_groups] = vert_weights
            all_group_indices_list[cursor:cursor + num_groups] = vert_indices
            cursor += num_groups

        # Convert the final lists to numpy arrays
        all_weights = np.array(all_weights_list, dtype=np.float32)
        all_group_indices = np.array(all_group_indices_list, dtype=np.int32)

        # Process weights per-vertex to filter, sort, and truncate to the top 4 influences
        final_indices = np.zeros((num_verts, 4), dtype=np.int32)
        final_weights = np.zeros((num_verts, 4), dtype=np.float32)

        weight_cursor = 0
        for i in range(num_verts):
            num_groups = groups_per_vert[i]
            if num_groups == 0:
                continue  # No weights for this vertex

            vert_weights = all_weights[weight_cursor:weight_cursor + num_groups]
            vert_group_indices = all_group_indices[weight_cursor:weight_cursor + num_groups]

            influences = []
            for j in range(num_groups):
                vg_idx = vert_group_indices[j]
                if vg_idx in vg_map:
                    node_id = vg_map[vg_idx]
                    final_idx = node_id_to_final_index[node_id]
                    influences.append((vert_weights[j], final_idx))  # weight, final bone index

            # Sort by weight descending and take the top 4
            influences.sort(key=lambda x: x[0], reverse=True)

            num_to_take = min(4, len(influences))
            for k in range(num_to_take):
                weight, index = influences[k]
                final_weights[i, k] = weight
                final_indices[i, k] = index

            weight_cursor += num_groups

        # Normalize weights so each vertex's influences sum to 1.0
        row_sums = final_weights.sum(axis=1, keepdims=True)
        # Avoid division by zero for vertices with no valid weights assigned
        np.divide(final_weights, row_sums, out=final_weights, where=row_sums != 0)
        return final_indices, final_weights

    def _get_vertex_buffer_dtype(self) -> np.dtype:
        """Creates the numpy dtype for the final packed vertex buffer."""
        fields = [
            ('position', '(3,)f4'),  # Vector of 3 floats for position
            ('normal', '(3,)f4'),  # Vector of 3 floats for normal
        ]
        for i in range(self.final_max_uv_layers):
            fields.append((f'uv{i}', '(2,)f4'))  # Each UV layer is a vector of 2 floats
        if self.final_has_colors:
            fields.append(('color', '(4,)f4'))  # RGBA color as a vector of 4 floats
        if self.is_merge_group or self.is_generic:
            fields.append(('id', 'f4'))
        if self.bone_mapping is not None:
            fields.extend([
                ('blend_indices', '(4,)i4'),  # Vector of 4 ints
                ('blend_weights', '(4,)f4')  # Vector of 4 floats
            ])
        return np.dtype(fields)

    def _pad_mesh_data(self, mesh_data: MeshExtraction, source_mesh_name: str) -> MeshExtraction:
        """ Pads the mesh data to ensure it has the correct number of UVs and colors."""
        group_type = "Shape"
        if self.is_merge_group:
            group_type = "Merge Group"
        elif self.is_generic:
            group_type = "Merge Children (generic)"

        max_uvs = self.final_max_uv_layers
        padded_uvs = mesh_data.uvs
        padded_colors = mesh_data.colors

        if self.final_has_uvs:
            if padded_uvs is None:
                self.logger.warning(
                    f"{group_type} Inconsistency: Mesh {source_mesh_name!r} has no UV layers, "
                    f"but other meshes in the group do. Padding with defaults."
                )
                padded_uvs = [np.zeros((len(mesh_data.loop_positions), 2), dtype=np.float32) for _ in range(max_uvs)]
            elif len(padded_uvs) < max_uvs:
                self.logger.warning(
                    f"{group_type} Inconsistency: Mesh {source_mesh_name!r} has fewer UVs than expected. "
                    f"Padding with zeros to match {max_uvs} UV layers."
                )
                padded_uvs = list(padded_uvs) + [np.zeros((len(mesh_data.loop_positions), 2), dtype=np.float32)
                                                 for _ in range(max_uvs - len(padded_uvs))]

        if self.final_has_colors and padded_colors is None:
            self.logger.warning(
                f"{group_type} Inconsistency: Mesh {source_mesh_name!r} has no color attributes, "
                f"but other meshes in the group do. Padding with defaults."
            )
            padded_colors = np.ones((len(mesh_data.loop_positions), 4), dtype=np.float32)
        return dataclasses.replace(mesh_data, uvs=padded_uvs, colors=padded_colors)

    def _get_safe_material(self, mesh_data: MeshExtraction, mat_idx: int, fallback_material: bpy.types.Material | None,
                           obj_name: str, warned: set) -> bpy.types.Material:
        """Safely retrieves a material by index from the mesh data."""
        if 0 <= mat_idx < len(mesh_data.materials):
            return mesh_data.materials[mat_idx]
        # Out of bounds
        if obj_name not in warned:
            self.logger.warning(f"Object {obj_name!r} has a triangle referencing a non-existent material slot "
                                f"(index {mat_idx}). Using fallback/default material.")
            warned.add(obj_name)
        return fallback_material or self.i3d.get_default_material().blender_material

    def _process_meshes(self, meshes_to_process: list[dict]) -> None:
        """
        Processes all meshes and groups triangles by final material subset,
        producing packed, unique vertices and triangle indices for export.
        """
        self.logger.info(f"Starting Subset-by-Subset processing of {len(meshes_to_process)} mesh blocks.")

        # Max 4 UV layers allowed per mesh
        self.final_max_uv_layers = min(4, max((len(m['mesh_obj'].uv_layers)
                                               for m in meshes_to_process if m['mesh_obj'].uv_layers), default=0))
        self.final_has_uvs = self.final_max_uv_layers > 0
        self.final_has_colors = any(m['mesh_obj'].color_attributes for m in meshes_to_process)
        dot_dtype = self._get_vertex_buffer_dtype()
        # Padding only needed if there are multiple meshes to process
        needs_padding = len(meshes_to_process) > 1

        # Group ALL triangles from ALL meshes by material
        self.logger.debug("Grouping all triangles by final material subset...")

        # Exract & pad mesh data
        padded_mesh_data_cache = {}
        extracted_mesh_data: list[tuple[dict, MeshExtraction]] = []
        for item in meshes_to_process:
            mesh_data = self._extract_mesh_data(item['mesh_obj'], item['object'])
            object_name = item['mesh_obj'].name
            if not mesh_data:
                self.logger.warning(f"Object {object_name!r} (mesh {item['mesh_obj'].name!r}) "
                                    "has no valid mesh data. Skipping.")
                continue
            mesh_name = item['mesh_obj'].name
            if needs_padding:
                mesh_id = id(mesh_data)
                if mesh_id not in padded_mesh_data_cache:
                    self.logger.debug(f"Padding mesh data for {object_name!r} (mesh {mesh_name!r})")
                    # In case of multiple meshes, we need to ensure that all of them have same amount of uvs & colors
                    padded_mesh_data_cache[mesh_id] = self._pad_mesh_data(mesh_data, mesh_name)
                final_mesh_data = padded_mesh_data_cache[mesh_id]
            else:
                final_mesh_data = mesh_data
            # Store both item and its mesh data for later use
            extracted_mesh_data.append((item, final_mesh_data))

        # Build master list of unique materials from processed mesh data which have triangles assigned to them.
        globally_ordered_materials = []
        visited_materials = set()
        for _, mesh_data in extracted_mesh_data:
            for mat_idx in mesh_data.tri_material_indices:
                if 0 <= mat_idx < len(mesh_data.materials):
                    mat = mesh_data.materials[mat_idx]
                    if mat and mat not in visited_materials:
                        globally_ordered_materials.append(mat)
                        visited_materials.add(mat)

        # Create final mapping based on the globally ordered materials
        master_material_map = OrderedDict({mat.name: i for i, mat in enumerate(globally_ordered_materials)})
        material_object_map = {mat.name: mat for mat in globally_ordered_materials}

        self.logger.debug(f"Found {len(master_material_map)} unique materials across all processed meshes.")

        # Assign triangles to subsets by material
        subset_data_to_process = defaultdict(list)
        for item, mesh_data in extracted_mesh_data:
            obj_name = item['object'].name
            unique_mats_in_mesh = {mat for mat in mesh_data.materials}
            fallback_material = next(iter(unique_mats_in_mesh), None) if len(unique_mats_in_mesh) == 1 else None
            warned = set()  # Track warnings per mesh to avoid duplicates
            for i, mat_idx in enumerate(mesh_data.tri_material_indices):
                material = self._get_safe_material(mesh_data, mat_idx, fallback_material, obj_name, warned)
                subset_data_to_process[material.name].append(
                    TriangleAssignment(
                        mesh_data=mesh_data,
                        loop_indices=mesh_data.triangle_loop_indices[i],
                        id_value=item['id_value']
                    )
                )

        # Process material subsets to create contiguous buffers
        self.logger.debug("Processing subsets one by one to create contiguous vertex buffer...")

        final_vertices_list = []
        final_triangles_list = []
        final_subsets_info = []
        vertex_offset = 0
        triangle_offset = 0

        for mat_name in master_material_map.keys():
            tri_data_list = subset_data_to_process[mat_name]
            if not tri_data_list:
                continue
            # Preallocate, fill, and process the triangles for this material subset using numpy!
            num_tris = len(tri_data_list)
            num_loops_in_subset = num_tris * 3

            self.logger.debug(f"Processing subset for material '{mat_name}' with {num_tris} triangles...")

            # Prepare mapping of unique mesh_data objects to indices for this subset
            mesh_data_to_index = {}
            unique_mesh_datas = []

            # Preallocate triangle corner arrays for all triangles in this material subset
            all_triangle_loop_indices = np.empty(num_loops_in_subset, dtype=np.int32)  # Each entry is a loop index
            all_triangle_mesh_indices = np.empty(num_loops_in_subset, dtype=np.int32)  # a mesh_data index
            all_triangle_id_values = np.empty(num_loops_in_subset, dtype=np.float32)   # the id_value for that triangle

            write_idx = 0
            for assignment in tri_data_list:
                # Get a unique index for each mesh_data instance in this subset
                mesh_data_id = id(assignment.mesh_data)
                if mesh_data_id not in mesh_data_to_index:
                    mesh_data_to_index[mesh_data_id] = len(unique_mesh_datas)
                    unique_mesh_datas.append(assignment.mesh_data)
                mesh_data_idx = mesh_data_to_index[mesh_data_id]
                # Assign the three loop indices and associated mesh_data and id_value for this triangle
                all_triangle_loop_indices[write_idx:write_idx + 3] = assignment.loop_indices
                all_triangle_mesh_indices[write_idx:write_idx + 3] = mesh_data_idx
                all_triangle_id_values[write_idx:write_idx + 3] = assignment.id_value
                write_idx += 3

            subset_dots = np.empty(num_loops_in_subset, dtype=dot_dtype)

            for mesh_data_idx, mesh_data in enumerate(unique_mesh_datas):
                mask = (all_triangle_mesh_indices == mesh_data_idx)
                indices_for_this_mesh = all_triangle_loop_indices[mask]
                ids_for_this_mesh = all_triangle_id_values[mask]

                subset_dots['position'][mask] = mesh_data.loop_positions[indices_for_this_mesh]
                subset_dots['normal'][mask] = mesh_data.normals[indices_for_this_mesh]

                if self.final_has_uvs and mesh_data.uvs is not None:
                    for i in range(min(self.final_max_uv_layers, len(mesh_data.uvs))):
                        subset_dots[f'uv{i}'][mask] = mesh_data.uvs[i][indices_for_this_mesh]
                if self.final_has_colors and mesh_data.colors is not None:
                    subset_dots['color'][mask] = mesh_data.colors[indices_for_this_mesh]
                if self.is_merge_group or self.is_generic:
                    subset_dots['id'][mask] = ids_for_this_mesh
                if self.bone_mapping is not None and mesh_data.blend_indices is not None:
                    vertex_indices_for_loops = mesh_data.loop_vertex_indices[indices_for_this_mesh]
                    # Assign the entire (num_loops, 4) array to the field
                    subset_dots['blend_indices'][mask] = mesh_data.blend_indices[vertex_indices_for_loops]
                    subset_dots['blend_weights'][mask] = mesh_data.blend_weights[vertex_indices_for_loops]

            # Perform the weld on this single, complete subset. This creates the unique vertices for this subset.
            unique_verts_in_subset, inverse_indices = np.unique(subset_dots, return_inverse=True)

            # The inverse_indices are the new triangles, with indices relative "to this subset".
            new_triangles = inverse_indices.reshape(-1, 3)

            # Append results and update offsets
            final_vertices_list.append(unique_verts_in_subset)
            final_triangles_list.append(new_triangles + vertex_offset)

            final_subsets_info.append({
                'firstIndex': triangle_offset,
                'numVertices': len(unique_verts_in_subset),
                'firstVertex': vertex_offset,
                'numIndices': len(new_triangles) * 3,
            })

            vertex_offset += len(unique_verts_in_subset)
            triangle_offset += len(new_triangles) * 3

            # Clean up large arrays for this subset
            del subset_dots, unique_verts_in_subset, inverse_indices, new_triangles

        # Finalize and Cache
        self.final_vertices = np.concatenate(final_vertices_list) if final_vertices_list else np.array([])
        self.final_triangles = np.concatenate(final_triangles_list) if final_triangles_list else np.array([])
        self.final_subsets = final_subsets_info

        self.material_ids = [self.i3d.add_material(material_object_map.get(name))
                             for name in master_material_map.keys()]
        self.tangent = self.tangent or any(self.i3d.materials[mat_id].is_normalmapped() for mat_id in self.material_ids)
        self.logger.info("Finished mesh processing.")

    def process_and_write_mesh_data(self):
        """
        This is the main workhorse. It processes mesh data (either single or merged)
        and writes the final results to the XML elements.
        """
        self.logger.debug(f"Starting final processing for shape '{self.name}'")

        # Gather all meshes to process
        meshes_to_process = []
        if self.is_merge_group or self.is_generic:
            meshes_to_process = self.pending_meshes
        else:  # Standard mesh case
            meshes_to_process = [{'mesh_obj': self.evaluated_mesh.mesh,
                                  'object': self.evaluated_mesh.object, 'id_value': None}]

        if not meshes_to_process:
            self.logger.warning(f"No meshes to process for shape '{self.name}'.")
            return
        self._process_meshes(meshes_to_process)

        # Write the final mesh data to XML
        final_verts = self.final_vertices
        if final_verts.size == 0:
            self.logger.warning(f"No vertices to export for shape '{self.name}'.")
            return

        self._write_attribute('count', final_verts.shape[0], 'vertices')
        self._write_attribute('normal', True, 'vertices')
        if self.tangent:  # Dependant on if the mesh has a normal map connected in the material or not
            self._write_attribute('tangent', True, 'vertices')
        if self.final_has_uvs:
            # Determine the actual number of UV layers present
            final_verts_dtype = self.final_vertices.dtype
            for i in range(self.final_max_uv_layers):
                if f'uv{i}' in final_verts_dtype.names:
                    self._write_attribute(f"uv{i}", True, 'vertices')

        if self.is_generic:
            self.logger.debug(f"Setting generic to True for shape '{self.name}'")
            self._write_attribute('generic', True, 'vertices')
        elif self.is_merge_group:
            self.logger.debug(f"Setting singleblendweights to True for merge group '{self.name}'")
            self._write_attribute('singleblendweights', True, 'vertices')
        elif self.bone_mapping is not None:
            self.logger.debug(f"Setting blendweights to True for skinned shape '{self.name}'")
            self._write_attribute('blendweights', True, 'vertices')

        self._process_bounding_volume()

        for vert_row in final_verts:
            vertex_attributes = {
                'p': " ".join(f"{v:.6g}" for v in vert_row['position']),
                'n': " ".join(f"{v:.6g}" for v in vert_row['normal'])
            }

            if self.final_has_uvs:
                for i in range(self.final_max_uv_layers):
                    if f'uv{i}' in final_verts.dtype.names:
                        vertex_attributes[f't{i}'] = " ".join(f"{v:.6g}" for v in vert_row[f'uv{i}'])

            # Cannot have merge groups or generic in combination with skinning
            if 'id' in final_verts.dtype.names:
                if self.is_generic:
                    vertex_attributes['g'] = f"{vert_row['id']}"
                elif self.is_merge_group:
                    vertex_attributes['bi'] = f"{int(vert_row['id'])}"
            elif self.bone_mapping is not None:
                vertex_attributes['bw'] = " ".join(f"{w:.6g}" for w in vert_row['blend_weights'])
                vertex_attributes['bi'] = " ".join(str(i) for i in vert_row['blend_indices'])

            if self.final_has_colors:
                vertex_attributes['c'] = " ".join(f"{v:.6g}" for v in vert_row['color'])

            xml_i3d.SubElement(self.xml_elements['vertices'], 'v', vertex_attributes)
        self._write_attribute('count', self.final_triangles.shape[0], 'triangles')
        for tri in self.final_triangles:
            xml_i3d.SubElement(self.xml_elements['triangles'], 't', {'vi': "{0} {1} {2}".format(*tri[:3])})

        self._write_attribute('count', len(self.final_subsets), 'subsets')
        for subset_info in self.final_subsets:
            attrs = {k: str(v) for k, v in subset_info.items()}
            xml_i3d.SubElement(self.xml_elements['subsets'], 'Subset', attrs)

        self.evaluated_mesh.node._write_attribute('materialIds', ' '.join(map(str, self.material_ids)))
        self.logger.debug(f"Added {len(self.material_ids)} material IDs for shape '{self.evaluated_mesh.node.name}'")

        self.logger.info(f"Exported {self.final_vertices.shape[0]} vertices, {self.final_triangles.shape[0]} triangles"
                         f" and {len(self.final_subsets)} subsets for shape '{self.name}'.")

    def populate_xml_element(self):
        if self.is_merge_group or self.is_generic:
            # Defer merge groups and generic shapes until all nodes are created
            self.logger.debug(f"Deferring population of '{self.name}' until all nodes are created.")
            if self not in self.i3d.deferred_shapes_to_populate:
                self.i3d.deferred_shapes_to_populate.append(self)
            return

        # For single meshes, we can process them immediately
        self.logger.debug(f"Processing mesh '{self.evaluated_mesh.name}'")
        self.process_and_write_mesh_data()

    def _process_bounding_volume(self):
        if self.bounding_volume_object is None:
            return
        # Calculate the bounding volume center from the corners of the bounding box
        bv_center = mathutils.Vector([sum(x) for x in zip(*self.bounding_volume_object.bound_box)]) * 0.125
        # Transform the bounding volume center to world coordinates
        bv_center_world = self.bounding_volume_object.matrix_world @ bv_center
        # Get the translation offset between the bounding volume center in world coordinates
        # and the data objects world coordinates
        bv_center_offset = bv_center_world - self.evaluated_mesh.object.matrix_world.to_translation()
        # Get the bounding volume center in coordinates relative to the data object using it
        bv_center_relative = self.evaluated_mesh.object.matrix_world.to_3x3().inverted() @ bv_center_offset

        self._write_attribute("bvCenter", bv_center_relative @ self.i3d.conversion_matrix.inverted())
        self._write_attribute("bvRadius", max(self.bounding_volume_object.dimensions) / 2)


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

    def __init__(self, id_: int, i3d: I3D, evaluated_curve_data: EvaluatedNurbsCurve, shape_name: str | None = None):
        self.id: int = id_
        self.i3d: I3D = i3d
        self.evaluated_curve_data: EvaluatedNurbsCurve = evaluated_curve_data
        self.control_vertex: OrderedDict[ControlVertex, int] = OrderedDict()
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
        self.shape_id: int | None = None
        super().__init__(id_=id_, blender_object=shape_object, i3d=i3d, parent=parent)

        self._create_shape()  # Create shape immediately upon initialization

    def _create_shape(self) -> None:
        """Creates the associated shape data (IndexTriangleSet or NurbsCurve) and stores its ID."""
        self.logger.debug(f"Creating shape data for object {self.blender_object.name!r}")
        if self.blender_object.type == 'CURVE':
            # Create and add the NurbsCurve data object to the i3d file
            self.shape_id = self.i3d.add_curve(EvaluatedNurbsCurve(self.i3d, self.blender_object))
            # Keep reference to the NurbsCurve element
            self.xml_elements['NurbsCurve'] = self.i3d.shapes[self.shape_id].element
        else:
            # Create and add the EvaluatedMesh data object to the i3d file
            self.shape_id = self.i3d.add_shape(EvaluatedMesh(self.i3d, self.blender_object, node=self))
            # Keep reference to the IndexedTriangleSet element
            self.xml_elements['IndexedTriangleSet'] = self.i3d.shapes[self.shape_id].element

    @property
    def _transform_for_conversion(self) -> mathutils.Matrix:
        return self.i3d.conversion_matrix @ self.blender_object.matrix_local @ self.i3d.conversion_matrix.inverted()

    def populate_xml_element(self) -> None:
        self._write_attribute('shapeId', self.shape_id)
        super().populate_xml_element()
