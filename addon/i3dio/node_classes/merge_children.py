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
        self.shape_id = self.i3d.add_shape(EvaluatedMesh(self.i3d, self.blender_object), is_generic=True,
                                           tangent=self.tangent)
        self.xml_elements['IndexedTriangleSet'] = self.i3d.shapes[self.shape_id].element

    def add_children_meshes(self, empty_object: bpy.types.Object):
        """
        Collect and evaluate all child meshes of the empty object (mergeChildren root).

        Each child mesh is assigned a normalized `generic_value`, which is used
        in shaders for animations or visibility controls. Transforms can be
        baked into the mesh or preserved based on the `apply_transforms` setting.
        """
        apply_child_transforms = empty_object.i3d_merge_children.apply_transforms
        root_world_matrix = empty_object.matrix_world
        interpolation_steps = empty_object.i3d_merge_children.interpolation_steps

        self.logger.debug(
            f"Starting collection of child meshes for '{empty_object.name}'. "
            f"Interpolation steps: {interpolation_steps}."
        )

        child_meshes = (child for child in empty_object.children if child.type == 'MESH')

        g_value_index = 0
        for child in child_meshes:
            generic_value = g_value_index / MERGE_CHILDREN_MAX_INDEX
            self.logger.debug(f"Processing child: '{child.name}', g_value: {generic_value}")

            # Use root_matrix to bake transforms into the mesh, or preserve the child's local transform.
            reference_frame = root_world_matrix if apply_child_transforms else child.matrix_world

            self.i3d.shapes[self.shape_id].append_from_evaluated_mesh_generic(
                EvaluatedMesh(self.i3d, child, reference_frame=reference_frame), generic_value
            )

            g_value_index += interpolation_steps

    def populate_xml_element(self):
        self.logger.debug("Populating XML element for MergeChildrenRoot")
        super().populate_xml_element()
