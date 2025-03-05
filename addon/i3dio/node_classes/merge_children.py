from typing import Optional
import bpy

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
    def __init__(self, id_: int, merge_children_object: bpy.types.Object, i3d: I3D,
                 parent: Optional[SceneGraphNode] = None):
        name = merge_children_object.name
        if merge_children_object.name.endswith('_dummy'):
            name = merge_children_object.name.replace('_dummy', '')
        super().__init__(id_=id_, shape_object=merge_children_object, i3d=i3d, parent=parent, custom_name=name)

    def add_shape(self):
        """Override to add the merged mesh as the shape."""
        self.shape_id = self.i3d.add_shape(EvaluatedMesh(self.i3d, self.blender_object, node=self), is_generic=True)
        self.xml_elements['IndexedTriangleSet'] = self.i3d.shapes[self.shape_id].element

    def add_children_meshes(self, empty_object: bpy.types.Object):
        """
        Merges all child meshes of `empty_object`. Each *top-level child* (and its descendants)
        is assigned the same normalized `generic_value`.

        If `apply_transforms` is true, local transforms are baked into the root’s transform.
        Otherwise, each mesh preserves its own local transform.

        :param empty_object: The root object containing child meshes.
        """
        apply_child_transforms = empty_object.i3d_merge_children.apply_transforms
        root_world_matrix = empty_object.matrix_world
        interpolation_steps = empty_object.i3d_merge_children.interpolation_steps

        self.logger.debug(
            f"Starting collection of child meshes for '{empty_object.name}'. "
            f"Interpolation steps: {interpolation_steps}."
        )

        def process_child_subtree(obj: bpy.types.Object, g_value: float):
            """
            Recursively process `obj` and its descendants, assigning `g_value` to every mesh in this branch.
            """
            # Use root_matrix to bake transforms into the mesh, or preserve the child's local transform.
            reference_frame = root_world_matrix if apply_child_transforms else obj.matrix_world

            if obj.type == 'MESH':
                self.logger.debug(f"Processing mesh: '{obj.name}', g_value: {g_value}")
                self.i3d.shapes[self.shape_id].append_from_evaluated_mesh(
                    EvaluatedMesh(self.i3d, obj, reference_frame=reference_frame),
                    g_value
                )

            for child in obj.children:
                process_child_subtree(child, g_value)

        g_value_index = 0
        for child in empty_object.children:
            # Any object can be processed here.
            # Non-mesh objects act as "g_value" increments, similar to interpolation steps.

            # Generic value for this child and its descendants.
            generic_value = g_value_index / MERGE_CHILDREN_MAX_INDEX
            # Process the child and its descendants.
            process_child_subtree(child, generic_value)
            # Increment the g_value index for the next child
            g_value_index += interpolation_steps

    def populate_xml_element(self):
        self.logger.debug("Populating XML element for MergeChildrenRoot")
        super().populate_xml_element()
