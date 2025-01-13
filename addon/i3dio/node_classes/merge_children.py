from typing import Optional
import bpy
import mathutils

from .node import SceneGraphNode
from .shape import (ShapeNode, EvaluatedMesh)
from ..i3d import I3D

MERGE_CHILDREN_DIVIDER = 32768


class MergeChildrenRoot(ShapeNode):
    def __init__(self, id_: int, merge_children_object: bpy.types.Object, i3d: I3D,
                 parent: Optional[SceneGraphNode] = None):
        self.merge_children_name = f"MergeChildren_{merge_children_object.name}"
        name = merge_children_object.parent.name
        super().__init__(id_=id_, shape_object=merge_children_object, i3d=i3d, parent=parent, custom_name=name)

    def add_shape(self):
        """Override to add the merged mesh as the shape."""
        self.shape_id = self.i3d.add_shape(EvaluatedMesh(self.i3d, self.blender_object), self.merge_children_name,
                                           is_generic=True, tangent=self.tangent)
        self.xml_elements['IndexedTriangleSet'] = self.i3d.shapes[self.shape_id].element

    def add_children_meshes(self):
        """Collect and evaluate all mesh children starting from the root child."""
        root = self.blender_object.parent
        freeze_translation = root.i3d_merge_children.freeze_translation
        freeze_rotation = root.i3d_merge_children.freeze_rotation
        freeze_scale = root.i3d_merge_children.freeze_scale

        reference_frame = self.blender_object.matrix_world

        for i, sibling in enumerate(self.blender_object.parent.children):
            if sibling != self.blender_object and sibling.type == 'MESH':  # Skip the "root" object already added
                g_value = i / MERGE_CHILDREN_DIVIDER
                self.logger.debug(f"Sibling mesh: {sibling.name} with generic value: {g_value}")
                self.i3d.shapes[self.shape_id].append_from_evaluated_mesh_generic(
                    EvaluatedMesh(self.i3d, sibling, reference_frame=reference_frame), g_value)
                self.logger.debug(f"Collected sibling mesh: {sibling.name}")
