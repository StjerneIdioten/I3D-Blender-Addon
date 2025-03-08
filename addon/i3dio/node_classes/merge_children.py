import bpy
import mathutils

from .node import SceneGraphNode
from .shape import (ShapeNode, EvaluatedMesh)
from ..i3d import I3D

# Maximum index value for `mergeChildren` objects, used to normalize
# generic values (g_value) for shaders. This constant is critical for:
# - Calculating normalized indices for motion paths or animations (e.g., vertex animation textures).
# - Controlling visibility of elements via the `hideByIndex` shader parameter.
# NOTE: The value must match the expected range in the shaders (e.g., [0..32767]).
MERGE_CHILDREN_MAX_INDEX = 32767


class MergeChildrenRoot(ShapeNode):
    def __init__(self, id_: int, merge_child_root: bpy.types.Object, i3d: I3D, parent: SceneGraphNode | None = None):
        super().__init__(id_=id_, shape_object=merge_child_root, i3d=i3d, parent=parent)

        self._add_children_meshes()

    def add_shape(self) -> None:
        """Override to prevent adding any data from the root object to the shape."""
        self.shape_id = self.i3d.add_shape(EvaluatedMesh(self.i3d, self.blender_object, node=self), is_generic=True)
        self.xml_elements['IndexedTriangleSet'] = self.i3d.shapes[self.shape_id].element

    def _process_child_subtree(self, obj: bpy.types.Object, g_value: float, reference_frame: mathutils.Matrix) -> None:
        """
        Recursively processes `obj` and its descendants, assigning `g_value` to each mesh.

        - Mesh objects are added to the evaluated shape with `g_value`.
        - Non-mesh objects act as interpolation steps but are otherwise ignored.
        """
        if obj.type == 'MESH':
            self.logger.debug(f"Processing mesh: '{obj.name}', g_value: {g_value}")
            self.i3d.shapes[self.shape_id].append_from_evaluated_mesh(
                EvaluatedMesh(self.i3d, obj, reference_frame=reference_frame),
                g_value
            )

        for child in obj.children:
            self._process_child_subtree(child, g_value, reference_frame)

    def _add_children_meshes(self) -> None:
        """
        Merges all child meshes of `merge_child_root`. Each *top-level child* (and its descendants)
        is assigned the same normalized `generic_value`, which is used in shaders.

        If `apply_transforms` is True, local transforms are baked into the root’s transform.
        Otherwise, each mesh preserves its own local transform.
        """
        root_obj = self.blender_object
        apply_child_transforms = root_obj.i3d_merge_children.apply_transforms
        root_world_matrix = root_obj.matrix_world
        interpolation_steps = root_obj.i3d_merge_children.interpolation_steps

        self.logger.debug(f"Merging child meshes (Interpolation steps: {interpolation_steps})")

        g_value_index = 0
        for child in root_obj.children:
            # Both mesh and non-mesh objects are processed; non-mesh objects only affect interpolation steps.
            # Generic value for this child and its descendants.
            generic_value = g_value_index / MERGE_CHILDREN_MAX_INDEX
            reference_frame = root_world_matrix if apply_child_transforms else child.matrix_world
            # Process the child and its descendants.
            self._process_child_subtree(child, generic_value, reference_frame)
            # Increment the g_value index for the next group of child meshes.
            g_value_index += interpolation_steps

    def populate_xml_element(self) -> None:
        self.logger.debug("Populating XML")
        super().populate_xml_element()
