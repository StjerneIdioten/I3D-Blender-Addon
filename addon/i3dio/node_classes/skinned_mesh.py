"""
A lot of classes in this file is purely to have different classes for different objects that are functionally the same,
but it helps with debugging big trees and seeing the structure.
"""
from __future__ import annotations
from typing import (Union, Dict, List, Optional)
from collections import ChainMap
import mathutils
import bpy

from .node import (TransformGroupNode, SceneGraphNode)
from .shape import (ShapeNode, EvaluatedMesh)
from ..i3d import I3D
from .. import xml_i3d

import math


def _get_child_of_target(armature: bpy.types.Object, bone_node: SkinnedMeshBoneNode) -> Optional[bpy.types.Object]:
    """Return the target object from the first 'Child Of' constraint on the bone, if any."""
    if pose_bone := armature.pose.bones.get(bone_node.name):
        child_of = next((c for c in pose_bone.constraints if c.type == 'CHILD_OF'), None)
        return child_of.target if (child_of and child_of.target) else None
    return None


class SkinnedMeshBoneNode(TransformGroupNode):
    def __init__(self, id_: int, bone_object: bpy.types.Bone,
                 i3d: I3D, parent: SceneGraphNode):
        super().__init__(id_=id_, empty_object=bone_object, i3d=i3d, parent=parent)

    def _matrix_to_i3d_space(self, matrix: mathutils.Matrix) -> mathutils.Matrix:
        return self.i3d.conversion_matrix @ matrix @ self.i3d.conversion_matrix.inverted()

    @property
    def _transform_for_conversion(self) -> mathutils.Matrix:
        if self.blender_object.parent and isinstance(self.blender_object.parent, bpy.types.Bone):
            # For bones parented to other bones, matrix_local is relative to the parent.
            # No transformation to I3D space is needed because the orientation is already relative to the parent bone.
            return self.blender_object.parent.matrix_local.inverted() @ self.blender_object.matrix_local

        # Get the bone's transformation in armature space
        bone_matrix = self._matrix_to_i3d_space(self.blender_object.matrix_local)
        # Giants Engine expects bones to point along the Z-axis (Blender's visual alignment).
        # However, root bones in Blender internally align along the Y-axis.
        # Rotate -90° around X-axis to correct root bone orientation. Child bones remain unaffected.
        rot_fix = mathutils.Matrix.Rotation(math.radians(-90.0), 4, 'X')
        translation = bone_matrix.to_translation()
        bone_matrix = rot_fix @ bone_matrix.to_3x3().to_4x4()
        bone_matrix.translation = translation

        if target_obj := _get_child_of_target(self.parent.blender_object, self.blender_object):
            target_matrix = self._matrix_to_i3d_space(target_obj.matrix_world)
            armature_matrix = self._matrix_to_i3d_space(self.parent.blender_object.matrix_local)
            return target_matrix.inverted() @ armature_matrix @ bone_matrix

        # For bones parented directly to the armature, matrix_local already represents their transform
        # relative to the armature, so no additional adjustments are needed.
        if self.i3d.settings['collapse_armatures'] and self.parent.blender_object:
            # If collapse_armatures is enabled, the armature is removed in the I3D.
            # The root bone replaces the armature in the hierarchy,
            # so multiply its matrix with the armature matrix to preserve the correct transformation.
            armature_matrix = self._matrix_to_i3d_space(self.parent.blender_object.matrix_local)
            return armature_matrix @ bone_matrix
        # Return the bone's local transform unchanged, as it is already correct relative to the armature.
        return bone_matrix


class SkinnedMeshRootNode(TransformGroupNode):
    def __init__(self, id_: int, armature_object: bpy.types.Armature,
                 i3d: I3D, parent: Union[SceneGraphNode, None] = None):
        # The skinBindID essentially, but mapped with the bone names for easy reference. An ordered dict is important
        # but dicts should be ordered going forwards in python
        self.bones: List[SkinnedMeshBoneNode] = list()
        self.bone_mapping: Dict[str, int] = {}
        # To determine if we just added the armature through a modifier lookup or knows its position in the scenegraph
        self.is_located = False

        super().__init__(id_=id_, empty_object=armature_object, i3d=i3d, parent=parent)

        # Create all bones in normal Blender parent-child order
        for bone in armature_object.data.bones:
            if bone.parent is None:
                self._add_bone(bone, self)

        # Make a dict of child-of targets {bone_node: target_object}
        self.child_of_parents = {bone_node: target for bone_node in self.bones
                                 if (target := _get_child_of_target(armature_object, bone_node))}

    def add_i3d_mapping_to_xml(self):
        """Wont export armature mapping, if 'collapsing armatures' is enabled"""
        if not self.i3d.settings['collapse_armatures']:
            super().add_i3d_mapping_to_xml()

    def _add_bone(self, bone_object: bpy.types.Bone, parent: Union[SkinnedMeshBoneNode, SkinnedMeshRootNode]):
        """Recursive function for adding a bone along with all of its children"""
        self.bones.append(self.i3d.add_bone(bone_object, parent))
        current_bone = self.bones[-1]
        self.bone_mapping[bone_object.name] = current_bone.id
        for child_bone in bone_object.children:
            self._add_bone(child_bone, current_bone)

    @staticmethod
    def _find_node_by_blender_object(root_nodes: List[SceneGraphNode],
                                     target_object: bpy.types.Object) -> SceneGraphNode | None:
        """Recursively find a node in the scene graph by its Blender object."""
        for root_node in root_nodes:
            if root_node.blender_object == target_object:
                return root_node
            if child_result := SkinnedMeshRootNode._find_node_by_blender_object(root_node.children, target_object):
                return child_result
        return None

    def update_bone_parent(self, fallback_parent: SceneGraphNode | None) -> None:
        """Update the parent of each bone based on constraints or fallback to default behavior."""
        for bone in self.bones:
            if target_obj := self.child_of_parents.get(bone):
                new_parent_node = self._find_node_by_blender_object(self.i3d.scene_root_nodes, target_obj)
                if not new_parent_node:
                    # If the target object is not in the scene graph, use the fallback parent
                    self.logger.warning(f"Child Of target '{target_obj.name}' not found. Using fallback.")
                    new_parent_node = fallback_parent
            else:  # If no Child Of constraint is found, use the fallback parent
                new_parent_node = fallback_parent

            if bone.parent == new_parent_node:
                continue  # Already parented correctly

            # Remove bone from old parent
            if bone.parent and (bone in bone.parent.children):
                bone.parent.children.remove(bone)
                bone.parent.element.remove(bone.element)

            # Reassign parent
            if new_parent_node:
                bone.parent = new_parent_node
                new_parent_node.children.append(bone)
                new_parent_node.element.append(bone.element)
            else:  # If no valid parent is found, add to the root
                bone.parent = None
                self.i3d.scene_root_nodes.append(bone)
                self.i3d.xml_elements['Scene'].append(bone.element)


class SkinnedMeshShapeNode(ShapeNode):
    def __init__(self, id_: int, skinned_mesh_object: bpy.types.Object, i3d: I3D,
                 parent: [SceneGraphNode | None] = None):
        self.armature_nodes = []
        self.skinned_mesh_name = xml_i3d.skinned_mesh_prefix + skinned_mesh_object.data.name
        for modifier in skinned_mesh_object.modifiers:
            if modifier.type == 'ARMATURE':
                self.armature_nodes.append(i3d.add_armature(modifier.object))
        self.bone_mapping = ChainMap(*[armature.bone_mapping for armature in self.armature_nodes])
        super().__init__(id_=id_, shape_object=skinned_mesh_object, i3d=i3d, parent=parent)

    def add_shape(self):
        # Use a ChainMap to easily combine multiple bone mappings and get around any problems with multiple bones
        # named the same as a ChainMap just gets the bone from the first armature added
        self.shape_id = self.i3d.add_shape(EvaluatedMesh(self.i3d, self.blender_object), self.skinned_mesh_name,
                                           bone_mapping=self.bone_mapping, tangent=self.tangent)
        self.xml_elements['IndexedTriangleSet'] = self.i3d.shapes[self.shape_id].element

    def populate_xml_element(self):
        super().populate_xml_element()
        vertex_group_binding = self.i3d.shapes[self.shape_id].vertex_group_ids
        self.logger.debug(f"Skinned groups: {vertex_group_binding}")

        skin_bind_id = ''
        for vertex_group_id in sorted(vertex_group_binding, key=vertex_group_binding.get):
            skin_bind_id += f"{self.bone_mapping[self.blender_object.vertex_groups[vertex_group_id].name]} "
        skin_bind_id = skin_bind_id[:-1]

        self._write_attribute('skinBindNodeIds', skin_bind_id)
