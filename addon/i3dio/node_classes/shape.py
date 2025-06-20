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
            # TODO: Add support for point(vertex) as well
            colors = np.empty((num_loops, 4), dtype=np.float32)
            mesh.color_attributes.active_color.data.foreach_get('color_srgb', colors.ravel())

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

    def _populate_dot_array(self, dot_array, mesh_data: MeshExtraction, id_value, num_uvs, has_id, has_colors):
        dot_array['px'], dot_array['py'], dot_array['pz'] = mesh_data.positions.T
        dot_array['nx'], dot_array['ny'], dot_array['nz'] = mesh_data.normals.T
        if has_id:
            dot_array['id'] = id_value
        if num_uvs and mesh_data.uvs is not None:
            for i in range(num_uvs):
                dot_array[f'u{i}'], dot_array[f'v{i}'] = mesh_data.uvs[:, i * 2: i * 2 + 2].T
        if has_colors and mesh_data.colors is not None:
            dot_array['r'], dot_array['g'], dot_array['b'], dot_array['a'] = mesh_data.colors.T
        return dot_array

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
        if not meshes_to_process:
            self.logger.debug("No meshes to process.")
            self.final_structured_vertices = np.array([])
            self.final_triangles = np.array([])
            self.final_subsets = []
            return

        # Determine final structure
        max_uvs = min(4, max(len(m['mesh_obj'].uv_layers) for m in meshes_to_process if m['mesh_obj'].uv_layers) or 0)
        has_colors = any(m['mesh_obj'].color_attributes for m in meshes_to_process)
        has_id = self.is_merge_group or self.is_generic

        # Define the structured array dtype for the final vertex data
        dot_dtype = self._get_dot_dtype(max_uvs, has_id, has_colors)
        self.final_has_uvs = max_uvs > 0
        self.final_max_uv_layers = max_uvs
        self.final_has_colors = has_colors

        local_results = []
        for item in meshes_to_process:
            mesh = item['mesh_obj']
            id_value = item['id_value']
            mesh_data = self._extract_mesh_data(mesh)
            if mesh_data is None:
                self.logger.warning(f"Mesh '{mesh.name}' has no valid data to process. Skipping.")
                continue

            dots = np.empty(len(mesh_data.positions), dtype=dot_dtype)
            dots = self._populate_dot_array(dots, mesh_data, id_value, max_uvs, has_id, has_colors)
            unique_dots, inv = np.unique(dots, return_inverse=True)
            local_tris = inv[mesh_data.tri_loops.flatten()].reshape(-1, 3)

            local_results.append(LocalMeshResult(
                unique_dots=unique_dots,
                triangles=local_tris,
                material_indices=mesh_data.tri_material_indices,
                mesh_obj=mesh
            ))

        if not local_results:
            self.logger.warning("No processable geometry found in any mesh.")
            self.final_structured_vertices = np.array([])
            self.final_triangles = np.array([])
            self.final_subsets = []
            return

        all_unique = np.concatenate([r.unique_dots for r in local_results])
        global_unique, global_inv = np.unique(all_unique, return_inverse=True)

        # Assign global indices to each mesh's local unique vertices
        offset = 0
        for result in local_results:
            num_local_uniques = len(result.unique_dots)
            result.local_to_global_map = global_inv[offset:offset + num_local_uniques]
            offset += num_local_uniques

        subset_triangles = collections.defaultdict(list)
        master_material_map = collections.OrderedDict()
        material_object_map = {}

        for result in local_results:
            global_triangles = result.local_to_global_map[result.triangles]
            for i, mat_idx in enumerate(result.material_indices):
                material = result.mesh_obj.materials[mat_idx]
                if material.name not in master_material_map:
                    master_material_map[material.name] = len(master_material_map)
                    material_object_map[material.name] = material
                subset_triangles[material.name].append(global_triangles[i])

        self.final_structured_vertices = global_unique

        final_triangles_list = []
        final_subsets_info = []
        triangle_offset = 0
        for mat_name in master_material_map.keys():
            tris = subset_triangles[mat_name]
            if not tris:
                continue
            tris_array = np.array(tris, dtype=np.int32)
            final_triangles_list.append(tris_array)

            unique_verts_in_subset = np.unique(tris_array)
            num_verts_in_subset = len(unique_verts_in_subset)

            first_vertex_in_subset = np.min(unique_verts_in_subset) if num_verts_in_subset > 0 else 0

            final_subsets_info.append({
                'firstIndex': triangle_offset * 3,
                'numIndices': tris_array.size,
                'firstVertex': first_vertex_in_subset,
                'numVertices': num_verts_in_subset,
            })
            triangle_offset += len(tris_array)

        self.final_triangles = np.vstack(final_triangles_list) if final_triangles_list else np.array([])
        self.final_subsets = final_subsets_info

        self.material_ids = []
        for name in master_material_map.keys():
            mat = material_object_map.get(name)
            if mat is None:
                mat = self.i3d.get_default_material().blender_material
            self.material_ids.append(self.i3d.add_material(mat))

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
        final_verts = self.final_structured_vertices
        if final_verts.size == 0:
            self.logger.warning(f"No vertices to export for shape '{self.name}'.")
            return

        self._write_attribute('count', final_verts.shape[0], 'vertices')
        self._write_attribute('normal', True, 'vertices')
        if self.tangent:
            self._write_attribute('tangent', True, 'vertices')
        if self.final_has_uvs:
            # Determine the actual number of UV layers present
            num_uvs = 0
            if final_verts.ndim > 1 and final_verts.shape[1] > 6:
                num_uvs = (final_verts.shape[1] - 6) // 2
            for count in range(num_uvs):
                self._write_attribute(f"uv{count}", True, 'vertices')

        for vert_row in final_verts:
            # Accessing data is now by field name, not by column index.
            # This is much more readable and robust!
            vertex_attributes = {
                'p': f"{vert_row['px']:.6f} {vert_row['py']:.6f} {vert_row['pz']:.6f}",
                'n': f"{vert_row['nx']:.6f} {vert_row['ny']:.6f} {vert_row['nz']:.6f}"
            }

            if 'id' in final_verts.dtype.names:
                if self.is_merge_group:
                    vertex_attributes['bi'] = f"{int(vert_row['id'])}"
                elif self.is_generic:
                    vertex_attributes['g'] = f"{vert_row['id']}"
            if self.final_has_uvs:
                for i in range(getattr(self, 'final_max_uv_layers', 0)):
                    if f'u{i}' in final_verts.dtype.names:
                        vertex_attributes[f't{i}'] = f"{vert_row[f'u{i}']:.6f} {vert_row[f'v{i}']:.6f}"

            if self.final_has_colors:
                vertex_attributes['c'] = \
                    f"{vert_row['r']:.6f} {vert_row['g']:.6f} {vert_row['b']:.6f} {vert_row['a']:.6f}"

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
