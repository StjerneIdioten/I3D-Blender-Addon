import dataclasses
from dataclasses import dataclass
import numpy as np
import mathutils
import collections
import logging
from typing import (OrderedDict, Optional, List, ChainMap)
import bpy

from .node import (Node, SceneGraphNode)

from .. import (debugging, xml_i3d)
from ..i3d import I3D
import time


class EvaluatedMesh:
    def __init__(self, i3d: I3D, mesh_object: bpy.types.Object, name: str = None,
                 reference_frame: mathutils.Matrix = None, node=None):
        self.node: SceneGraphNode = node
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
    positions: np.ndarray
    normals: np.ndarray
    uvs: np.ndarray | None
    colors: np.ndarray | None
    tri_loops: np.ndarray
    tri_material_indices: np.ndarray
    materials: list


@dataclass
class LocalMeshResult:
    unique_dots: np.ndarray
    triangles: np.ndarray
    material_indices: np.ndarray
    mesh_obj: bpy.types.Mesh


class IndexedTriangleSet(Node):
    ELEMENT_TAG = 'IndexedTriangleSet'
    NAME_FIELD_NAME = 'name'
    ID_FIELD_NAME = 'shapeId'

    def __init__(self, id_: int, i3d: I3D, evaluated_mesh: EvaluatedMesh, shape_name: Optional[str] = None,
                 is_merge_group: bool = False, is_generic: bool = False, bone_mapping: ChainMap = None):
        self.id: int = id_
        self.i3d: I3D = i3d
        self.evaluated_mesh: EvaluatedMesh = evaluated_mesh
        self.bounding_volume_object: bpy.types.Object | None = \
            self.evaluated_mesh.mesh.i3d_attributes.bounding_volume_object
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

        self.pending_meshes = []
        self.final_vertices = np.array([])
        self.final_triangles = np.array([])
        self.final_subsets = []

        self.shape_name = shape_name or self.evaluated_mesh.name
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
        """Appends mesh data from another EvaluatedMesh to existing IndexedTriangleSet."""
        if not (self.is_merge_group or self.is_generic):
            self.logger.warning("Cannot add a mesh to an IndexedTriangleSet that is neither a merge group nor generic.")
            return
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

    def _extract_mesh_data(self, mesh: bpy.types.Mesh) -> MeshExtraction | None:
        """
        Extracts mesh data from a Blender mesh object and returns it in a structured format.
        """
        num_verts = len(mesh.vertices)
        num_loops = len(mesh.loops)
        num_tris = len(mesh.loop_triangles)

        if not all([num_verts, num_loops, num_tris]):
            self.logger.warning(f"Mesh '{mesh.name}' has no vertices, loops, or triangles. Skipping extraction.")
            return None

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
            max_uvs = min(4, len(uv_keys))
            uvs = np.empty((num_loops, max_uvs * 2), dtype=np.float32)
            for i, uv_key in enumerate(uv_keys[:max_uvs]):
                uv_data = np.empty((num_loops, 2), dtype=np.float32)
                uv_layers[uv_key].data.foreach_get('uv', uv_data.ravel())
                uvs[:, i * 2: (i + 1) * 2] = uv_data

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

        loop_positions = positions[loop_vertex_indices]
        return MeshExtraction(
            positions=loop_positions,
            normals=normals,
            uvs=uvs,
            colors=colors,
            tri_loops=tri_loop_indices,
            tri_material_indices=tri_material_indices,
            materials=[mat for mat in mesh.materials if mat is not None]
        )

    def _get_dot_dtype(self, num_uvs: int, has_id: bool, has_colors: bool) -> np.dtype:
        fields = [
            ('px', 'f4'), ('py', 'f4'), ('pz', 'f4'),
            ('nx', 'f4'), ('ny', 'f4'), ('nz', 'f4'),
        ]
        if has_id:
            fields.append(('id', 'f4'))
        for i in range(num_uvs):
            fields.extend([(f'u{i}', 'f4'), (f'v{i}', 'f4')])
        if has_colors:
            fields.extend([('r', 'f4'), ('g', 'f4'), ('b', 'f4'), ('a', 'f4')])
        return np.dtype(fields)

    def _populate_dot_array(self, dot_array, positions, normals, uvs, colors, id_value, num_uvs, has_id, has_colors):
        dot_array['px'], dot_array['py'], dot_array['pz'] = positions.T
        dot_array['nx'], dot_array['ny'], dot_array['nz'] = normals.T
        if has_id:
            dot_array['id'] = id_value
        if num_uvs and uvs is not None:
            for i in range(min(num_uvs, uvs.shape[1] // 2)):
                dot_array[f'u{i}'], dot_array[f'v{i}'] = uvs[:, i * 2: i * 2 + 2].T
        if has_colors and colors is not None:
            dot_array['r'], dot_array['g'], dot_array['b'], dot_array['a'] = colors.T
        return dot_array

    def process_meshes_numpy(self, meshes_to_process: list):
        if not meshes_to_process:
            self.logger.debug("No meshes to process.")
            self.final_structured_vertices = np.array([])
            self.final_triangles = np.array([])
            self.final_subsets = []
            return

        self.logger.info(f"Starting V5 (Subset-by-Subset) processing of {len(meshes_to_process)} mesh blocks.")

        # Max 4 UV layers allowed per mesh
        max_uvs = min(4, max((len(m['mesh_obj'].uv_layers)
                              for m in meshes_to_process if m['mesh_obj'].uv_layers), default=0))
        has_colors = any(m['mesh_obj'].color_attributes for m in meshes_to_process)
        has_id = self.is_merge_group or self.is_generic
        dot_dtype = self._get_dot_dtype(max_uvs, has_id, has_colors)
        self.final_has_uvs = max_uvs > 0
        self.final_max_uv_layers = max_uvs
        self.final_has_colors = has_colors

        # Group ALL triangles from ALL meshes by material
        self.logger.debug("Grouping all triangles by final material subset...")

        # This dictionary will hold the data needed to build the 'dots' for each subset.
        # Key: material_name
        # Value: list of (mesh_data_object, tri_loop_indices_array, id_value)
        subset_data_to_process = collections.defaultdict(list)
        master_material_map = collections.OrderedDict()
        material_object_map = {}

        # In case of multiple meshes, we need to ensure that all of them have same amount of "data" (uvs, colors, etc.)
        padded_mesh_data_cache = {}
        for item in meshes_to_process:
            mesh_data = self._extract_mesh_data(item['mesh_obj'])
            if not mesh_data:
                continue

            mesh_id = id(mesh_data)
            if mesh_id not in padded_mesh_data_cache:
                self.logger.debug(f"First encounter with mesh data for '{item['mesh_obj'].name}', check for padding.")

                padded_uvs = mesh_data.uvs
                padded_colors = mesh_data.colors

                if self.final_has_uvs:
                    if padded_uvs is None:
                        self.logger.debug(f"Mesh '{item['mesh_obj'].name}' has no UVs. Padding with defaults.")
                        # This mesh has no UVs at all, create a full default array.
                        padded_uvs = np.zeros((len(mesh_data.positions), max_uvs * 2), dtype=np.float32)
                    elif padded_uvs.shape[1] < max_uvs * 2:
                        self.logger.debug(f"Mesh '{item['mesh_obj'].name}' has fewer UVs than max. Padding.")
                        # This mesh has some UVs, but not enough. Add columns of zeros.
                        padding_shape = (padded_uvs.shape[0], max_uvs * 2 - padded_uvs.shape[1])
                        padded_uvs = np.hstack([padded_uvs, np.zeros(padding_shape, dtype=np.float32)])

                if self.final_has_colors and padded_colors is None:
                    self.logger.debug(f"Mesh '{item['mesh_obj'].name}' has no vertex colors. Padding with defaults.")
                    # This mesh has no colors, but others do. Create a default white array.
                    padded_colors = np.ones((len(mesh_data.positions), 4), dtype=np.float32)

                padded_mesh_data_cache[mesh_id] = dataclasses.replace(
                    mesh_data,
                    uvs=padded_uvs,
                    colors=padded_colors
                )

            final_mesh_data: MeshExtraction = padded_mesh_data_cache[mesh_id]

            for i, mat_idx in enumerate(final_mesh_data.tri_material_indices):
                # Gracefully handle out-of-bounds material indices
                if not (0 <= mat_idx < len(mesh_data.materials)):
                    self.logger.warning(f"Invalid material index {mat_idx} found. Using default material.")
                    material = self.i3d.get_default_material().blender_material
                else:
                    material = mesh_data.materials[mat_idx]

                if material.name not in master_material_map:
                    master_material_map[material.name] = len(master_material_map)
                    material_object_map[material.name] = material

                # For each triangle, store the mesh it came from and its three loop indices
                subset_data_to_process[material.name].append(
                    (final_mesh_data, final_mesh_data.tri_loops[i], item['id_value'])
                )

        # Process One Complete Material Subset at a Time
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

            self.logger.debug(f"Processing subset for material '{mat_name}' with {len(tri_data_list)} triangles...")
            start_time = time.time()

            # Build mapping from mesh_data to int index
            mesh_data_to_index = {}
            unique_mesh_datas = []

            # Preallocate arrays for all triangle data
            all_loop_indices = np.empty(num_loops_in_subset, dtype=np.int32)
            all_mesh_data_indices = np.empty(num_loops_in_subset, dtype=np.int32)
            all_id_values = np.empty(num_loops_in_subset, dtype=np.float32)

            write_idx = 0
            for mesh_data, tri_loops, id_value in tri_data_list:
                mesh_data_id = id(mesh_data)
                if mesh_data_id not in mesh_data_to_index:
                    mesh_data_to_index[mesh_data_id] = len(unique_mesh_datas)
                    unique_mesh_datas.append(mesh_data)
                mesh_idx = mesh_data_to_index[mesh_data_id]
                # Fill arrays by slice
                all_loop_indices[write_idx:write_idx + 3] = tri_loops
                all_mesh_data_indices[write_idx:write_idx + 3] = mesh_idx
                all_id_values[write_idx:write_idx + 3] = id_value
                write_idx += 3

            subset_dots = np.empty(num_loops_in_subset, dtype=dot_dtype)

            for mesh_idx, mesh_data in enumerate(unique_mesh_datas):
                mask = (all_mesh_data_indices == mesh_idx)
                indices_for_this_mesh = all_loop_indices[mask]
                ids_for_this_mesh = all_id_values[mask]

                subset_dots['px'][mask], subset_dots['py'][mask], subset_dots['pz'][mask] = (
                    mesh_data.positions[indices_for_this_mesh].T
                )
                subset_dots['nx'][mask], subset_dots['ny'][mask], subset_dots['nz'][mask] = (
                    mesh_data.normals[indices_for_this_mesh].T
                )
                if has_id:
                    subset_dots['id'][mask] = ids_for_this_mesh
                if self.final_has_uvs and mesh_data.uvs is not None:
                    num_uvs_in_mesh = mesh_data.uvs.shape[1] // 2
                    for i in range(min(max_uvs, num_uvs_in_mesh)):
                        subset_dots[f'u{i}'][mask], subset_dots[f'v{i}'][mask] = \
                            mesh_data.uvs[indices_for_this_mesh, i * 2:i * 2 + 2].T
                if self.final_has_colors and mesh_data.colors is not None:
                    subset_dots['r'][mask], subset_dots['g'][mask], subset_dots['b'][mask], subset_dots['a'][mask] = \
                        mesh_data.colors[indices_for_this_mesh].T

            self.logger.debug(f"Populated dots for material '{mat_name}' in {time.time() - start_time:.4f} seconds")

            # Perform the weld on this single, complete subset. This creates the unique vertices for this subset.
            unique_verts_in_subset, inverse_indices = np.unique(subset_dots, return_inverse=True)

            # The inverse_indices are the new triangles, with indices relative "to this subset".
            new_triangles = inverse_indices.reshape(-1, 3)

            # Append results and update offsets
            final_vertices_list.append(unique_verts_in_subset)
            final_triangles_list.append(new_triangles + vertex_offset)

            final_subsets_info.append({
                'firstIndex': triangle_offset,
                'firstVertex': vertex_offset,
                'numIndices': len(new_triangles) * 3,
                'numVertices': len(unique_verts_in_subset),
            })

            vertex_offset += len(unique_verts_in_subset)
            triangle_offset += len(new_triangles) * 3

            # Clean up large arrays for this subset
            del subset_dots, unique_verts_in_subset, inverse_indices, new_triangles

        # Finalize and Cache
        self.final_structured_vertices = np.concatenate(final_vertices_list) if final_vertices_list else np.array([])
        self.final_triangles = np.concatenate(final_triangles_list) if final_triangles_list else np.array([])
        self.final_subsets = final_subsets_info

        self.material_ids = [self.i3d.add_material(material_object_map.get(name))
                             for name in master_material_map.keys()]
        self.tangent = self.tangent or any(self.i3d.materials[mat_id].is_normalmapped() for mat_id in self.material_ids)

    def process_and_write_mesh_data(self):
        """
        This is the main workhorse. It processes mesh data (either single or
        merged) and writes the final results to the XML elements.
        """
        self.logger.debug(f"Starting final processing for shape '{self.name}'")

        # Gather all meshes to process
        meshes_to_process = []
        if self.is_merge_group or self.is_generic:
            meshes_to_process = self.pending_meshes
        else:
            # Standard mesh case
            meshes_to_process = [{'mesh_obj': self.evaluated_mesh.mesh, 'id_value': None}]

        start_time = time.time()
        self.process_meshes_numpy(meshes_to_process)
        self.logger.debug(f"Processed {len(meshes_to_process)} meshes in {time.time() - start_time:.4f} seconds")

        # Write the final mesh data to XML
        start_time = time.time()
        final_verts = self.final_structured_vertices
        if final_verts.size == 0:
            self.logger.warning(f"No vertices to export for shape '{self.name}'.")
            return

        self._write_attribute('count', final_verts.shape[0], 'vertices')
        self._write_attribute('normal', True, 'vertices')
        if self.tangent:  # Dependant on if the mesh has a normal map connected in the material or not
            self._write_attribute('tangent', True, 'vertices')
        if self.final_has_uvs:
            # Determine the actual number of UV layers present
            final_verts_dtype = self.final_structured_vertices.dtype
            for i in range(self.final_max_uv_layers):
                uv_field_name = f'u{i}'
                if uv_field_name in final_verts_dtype.names:
                    self._write_attribute(f"uv{i}", True, 'vertices')

        if self.is_generic:
            self._write_attribute('generic', True, 'vertices')
        elif self.is_merge_group:
            self.logger.debug(f"Writing singleblendweights for merge group '{self.name}'")
            self._write_attribute('singleblendweights', True, 'vertices')
        self._process_bounding_volume()

        for vert_row in final_verts:
            # Format with "general" less numbers for the exporter and Giants Editor will format it like this anyways
            vertex_attributes = {
                'p': f"{vert_row['px']:.6g} {vert_row['py']:.6g} {vert_row['pz']:.6g}",
                'n': f"{vert_row['nx']:.6g} {vert_row['ny']:.6g} {vert_row['nz']:.6g}"
            }

            if self.final_has_uvs:
                for i in range(getattr(self, 'final_max_uv_layers', 0)):
                    if f'u{i}' in final_verts.dtype.names:
                        vertex_attributes[f't{i}'] = f"{vert_row[f'u{i}']:.6g} {vert_row[f'v{i}']:.6g}"

            if 'id' in final_verts.dtype.names:
                if self.is_merge_group:
                    vertex_attributes['bi'] = f"{int(vert_row['id'])}"
                elif self.is_generic:
                    vertex_attributes['g'] = f"{vert_row['id']}"

            if self.final_has_colors:
                vertex_attributes['c'] = \
                    f"{vert_row['r']:.6g} {vert_row['g']:.6g} {vert_row['b']:.6g} {vert_row['a']:.6g}"

            xml_i3d.SubElement(self.xml_elements['vertices'], 'v', vertex_attributes)
        self._write_attribute('count', self.final_triangles.shape[0], 'triangles')
        for tri in self.final_triangles:
            xml_i3d.SubElement(self.xml_elements['triangles'], 't', {'vi': "{0} {1} {2}".format(*tri[:3])})

        self._write_attribute('count', len(self.final_subsets), 'subsets')
        for subset_info in self.final_subsets:
            xml_i3d.SubElement(self.xml_elements['subsets'], 'Subset', {
                'firstVertex': str(subset_info['firstVertex']),
                'numVertices': str(subset_info['numVertices']),
                'firstIndex': str(subset_info['firstIndex']),
                'numIndices': str(subset_info['numIndices'])
            })

        self.evaluated_mesh.node._write_attribute('materialIds', ' '.join(map(str, self.material_ids)))
        self.logger.debug(f"Written {len(self.material_ids)} material IDs for shape '{self.evaluated_mesh.node.name}'")

        self.logger.info(f"Finished processing and writing data for shape '{self.name}'.")
        self.logger.debug(f"Processed shape '{self.name}' in {time.time() - start_time:.4f} seconds ) to xml")

    def populate_xml_element(self):
        start_time = time.time()

        if self.is_merge_group or self.is_generic:
            # Defer merge groups and generic shapes until all nodes are created
            self.logger.debug(f"Deferring population of '{self.name}' until all nodes are created.")
            if self not in self.i3d.deferred_shapes_to_populate:
                self.i3d.deferred_shapes_to_populate.append(self)
            return

        # For single meshes, we can process them immediately
        self.logger.debug(f"Processing mesh '{self.evaluated_mesh.name}'")
        self.process_and_write_mesh_data()

        self._process_bounding_volume()

        self.logger.debug(f"Populated mesh '{self.evaluated_mesh.name}' in {time.time() - start_time:.4f} seconds")

    def _process_bounding_volume(self):
        if self.bounding_volume_object is not None:
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
            self.shape_id = self.i3d.add_shape(EvaluatedMesh(self.i3d, self.blender_object, node=self))
            self.xml_elements['IndexedTriangleSet'] = self.i3d.shapes[self.shape_id].element

    def populate_xml_element(self):
        self.add_shape()
        self._write_attribute('shapeId', self.shape_id)
        super().populate_xml_element()
