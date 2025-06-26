import math
import mathutils
import collections
import logging
from typing import (OrderedDict, Optional, List, ChainMap)
import bpy

from .node import (Node, SceneGraphNode)

from .. import (debugging, xml_i3d)
from ..i3d import I3D


class MaterialStorage:
    def __init__(self, triangles: list = None, material_slot_name: str = None):
        self.material_slot_name = material_slot_name
        self.triangles = triangles or []

    def __str__(self):
        return f"triangles={len(self.triangles)}-{self.triangles} " \
               f"material_slot_name={self.material_slot_name}"

    def __repr__(self):
        return self.__str__()


class SubSet:
    def __init__(self):
        self.first_index = 0
        self.first_vertex = 0
        self.number_of_indices = 0
        self.number_of_vertices = 0
        self.triangles = []
        self.material_slot_name = None

    def as_dict(self):
        subset_attributes = {'firstIndex': f"{self.first_index}",
                             'firstVertex': f"{self.first_vertex}",
                             'numIndices': f"{self.number_of_indices}",
                             'numVertices': f"{self.number_of_vertices}"}
        if self.material_slot_name is not None:
            subset_attributes['materialSlotName'] = self.material_slot_name
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
        self.source_object = mesh_object
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
                if len(mesh.color_attributes):
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

    def _get_material_slot_name(self, _material: bpy.types.Material) -> str | None:
        """Returns the material slot name of the given material if set, otherwise None."""
        if _material.i3d_attributes.use_material_slot_name:
            return _material.i3d_attributes.material_slot_name or _material.name
        return None

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
        # Group triangles by material in a temporary dictionary, order here does not matter
        material_to_triangles_map = {}

        # Determine a fallback material for handling corrupt mesh data.
        # If the mesh has only one material, we'll use that. Otherwise, use the default.
        unique_mats = {mat for mat in mesh.materials if mat is not None}
        fallback_material = (next(iter(unique_mats), None) if len(unique_mats) == 1 else None)

        has_warned_for_invalid_index = False
        has_warned_for_empty_slot = False

        for triangle in mesh.loop_triangles:
            triangle_material = None
            if not (0 <= triangle.material_index < len(mesh.materials)):
                # Check if the triangle's material index is within the bounds for the slots list
                if not has_warned_for_invalid_index:
                    self.logger.warning("triangle(s) found with invalid material index, assigning fallback material")
                    has_warned_for_invalid_index = True
                if fallback_material is None:
                    fallback_material = self.i3d.get_default_material().blender_material
                triangle_material = fallback_material
            else:
                # Check if the slot assigned to this triangle is empty (None)
                mat = mesh.materials[triangle.material_index]
                if mat is None:
                    if not has_warned_for_empty_slot:
                        self.logger.warning("triangle(s) found with empty material slot, assigning fallback material")
                        has_warned_for_empty_slot = True
                    if fallback_material is None:
                        fallback_material = self.i3d.get_default_material().blender_material
                    triangle_material = fallback_material
                else:
                    triangle_material = mat

            # Add the triangle to the list for its assigned material
            triangles_list = material_to_triangles_map.setdefault(triangle_material, [])

            # For merge/append operations, we must also store the mesh and its bind index
            if append or self.is_merge_group:
                triangles_list.append((triangle, index or self.bind_index, mesh))
            else:
                triangles_list.append(triangle)

        if not material_to_triangles_map:
            self.logger.warning("No used materials found on mesh.")
            return

        # Build the final list of materials in the correct order. Important for preventing material mix-ups.
        # We loop through the mesh's material slots (which have the right order) and create a new list containing
        # only the materials that are actually used. This guarantees that the order stays consistent.
        ordered_used_materials = [mat for mat in mesh.materials if mat in material_to_triangles_map]

        # Very unlikely, but could happen on a mesh with all empty slots or fully corrupted indices
        if fallback_material and fallback_material not in ordered_used_materials \
                and fallback_material in material_to_triangles_map:
            self.logger.debug(f"Adding fallback material '{fallback_material.name}' to the ordered list.")
            ordered_used_materials.append(fallback_material)

        self.logger.debug(f"Material slot order being processed: {', '.join(m.name for m in ordered_used_materials)}")

        # Build the final export data using the ordered list
        self.material_ids = [self.i3d.add_material(m) for m in ordered_used_materials]
        self.tangent = self.tangent or any(self.i3d.materials[m_id].is_normalmapped() for m_id in self.material_ids)

        # If appending, we add to the existing self.materials dictionary. Otherwise, we create new subsets.
        if append or self.is_merge_group:
            # Add the newly collected triangles to the `self.materials` storage
            for mat in ordered_used_materials:
                triangles_for_mat = material_to_triangles_map[mat]
                storage_entry = self.materials.setdefault(mat.name, MaterialStorage())
                storage_entry.triangles.extend(triangles_for_mat)
                storage_entry.material_slot_name = self._get_material_slot_name(mat)

            # Rebuild subsets from the now-updated self.materials dictionary
            self.subsets.clear()
            for mat_name, storage in self.materials.items():
                subset = SubSet()
                subset.triangles = storage.triangles
                subset.material_slot_name = storage.material_slot_name
                self.subsets.append(subset)

        else:  # For single meshes, directly create subsets from the ordered list of materials
            self.subsets.clear()
            for mat in ordered_used_materials:
                subset = SubSet()
                subset.material_slot_name = self._get_material_slot_name(mat)
                subset.triangles = material_to_triangles_map[mat]
                self.subsets.append(subset)

        # Warn about any materials in slots that were not used
        all_slot_mats = {mat for mat in mesh.materials if mat is not None}
        used_mats = set(material_to_triangles_map.keys())
        for mat in all_slot_mats - used_mats:
            self.logger.warning(f"Material '{mat.name}' is not used by any triangle, it will be ignored.")

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

    def populate_xml_element(self):
        if len(self.evaluated_mesh.mesh.vertices) == 0 or self.is_generic:
            if self.is_generic:
                # Skip writing mesh data for the root object of merged children.
                # This ensures no vertices are exported while still allowing the bounding volume to be calculated.
                self._process_bounding_volume()
                return

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

        self._process_bounding_volume()

        # Write subsets
        for subset in self.subsets:
            xml_i3d.SubElement(self.xml_elements['subsets'], 'Subset', subset.as_dict())

    def _process_bounding_volume(self):
        bounding_volume_object = self.evaluated_mesh.source_object.data.i3d_attributes.bounding_volume_object
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
        if self.blender_object.type == 'CURVE':
            self.shape_id = self.i3d.add_curve(EvaluatedNurbsCurve(self.i3d, self.blender_object))
            self.xml_elements['NurbsCurve'] = self.i3d.shapes[self.shape_id].element
        else:
            self.shape_id = self.i3d.add_shape(EvaluatedMesh(self.i3d, self.blender_object))
            self.xml_elements['IndexedTriangleSet'] = self.i3d.shapes[self.shape_id].element

    def populate_xml_element(self):
        self.add_shape()
        if self.blender_object.type == 'MESH':
            self._write_attribute('materialIds', ' '.join(map(str, self.i3d.shapes[self.shape_id].material_ids)))
        self.logger.debug(f"has shape ID '{self.shape_id}'")
        self._write_attribute('shapeId', self.shape_id)
        super().populate_xml_element()
