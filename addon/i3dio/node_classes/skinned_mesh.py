"""
A lot of classes in this file is purely to have different classes for different objects that are functionally the same,
but it helps with debugging big trees and seeing the structure.
"""
from __future__ import annotations
from typing import (Union, Dict, List, Type, OrderedDict, Optional)
from collections import ChainMap
import mathutils
import bpy

from . import node
from .node import (TransformGroupNode, SceneGraphNode)
from .shape import (ShapeNode, EvaluatedMesh)
from ..i3d import I3D
from .. import xml_i3d

import math


class SkinnedMeshBoneNode(TransformGroupNode):
    def __init__(self, id_: int, bone_object: bpy.types.Bone,
                 i3d: I3D, parent: SceneGraphNode):
        super().__init__(id_=id_, empty_object=bone_object, i3d=i3d, parent=parent)

    def _convert_to_i3d_space(self, matrix: mathutils.Matrix) -> mathutils.Matrix:
        conversion_matrix: mathutils.Matrix = self.i3d.conversion_matrix
        return conversion_matrix @ matrix @ conversion_matrix.inverted()

    @property
    def _transform_for_conversion(self) -> mathutils.Matrix:
        if self.blender_object.parent and isinstance(self.blender_object.parent, bpy.types.Bone):
            # When a bone is parented to another bone, the bone's matrix_local is in relation to the parent bone.
            # No need for the conversion matrix here since the bones are already in the correct orientation.
            parent_bone_transform = self.blender_object.parent.matrix_local
            return parent_bone_transform.inverted() @ self.blender_object.matrix_local

        # Initialize default identity matrix for armature transform
        armature_transform = mathutils.Matrix.Identity(4)

        custom_parent = None

        # Check if the bone has a 'Child Of' constraint and retrieve its target as the custom parent, if it exists
        if isinstance(self.parent.blender_object, bpy.types.Object):
            custom_parent = SkinnedMeshRootNode._get_new_bone_parent(self.parent.blender_object, self.blender_object)

        # Get the armature object only if the bone is not parented to another bone
        if custom_parent or (not self.blender_object.parent and self.i3d.settings['collapse_armatures']):
            armature_obj = self.parent.blender_object
            self.logger.debug(f"the armature object: {armature_obj.name}")
            armature_transform = self._convert_to_i3d_space(armature_obj.matrix_local)

        # Get the bone's transformation in armature space
        bone_transform = self._convert_to_i3d_space(self.blender_object.matrix_local)

        # Giants Engine expects bones to point along the Z-axis, just like how Blender shows them visually.
        # But when a bone is directly connected to the armature (a root bone), Blender internally treats it as pointing
        # along the Y-axis. This difference needs to be fixed by rotating the bone -90 degrees around the X-axis.
        # Bones connected to other bones already work correctly and don’t need this adjustment.
        rot_fix = mathutils.Matrix.Rotation(math.radians(-90.0), 4, 'X')
        translation = bone_transform.to_translation()
        bone_transform = rot_fix @ bone_transform.to_3x3().to_4x4()
        bone_transform.translation = translation

        # If a custom parent exists, calculate bone transformation relative to the parent
        if custom_parent:
            self.logger.debug(f"has a custom parent: {custom_parent.name} from child of constraint")
            # For a 'Child Of' constraint targeting a regular object rather than another bone, the bone’s
            # final transformation depends on that object’s global position in the scene. Since this object
            # may lie deep within another hierarchy, `matrix_local` alone isn’t sufficient. Instead, we use
            # `matrix_world` to get the object’s fully resolved global transform before converting it into I3D space.
            custom_parent_transform = self._convert_to_i3d_space(custom_parent.matrix_world)
            return custom_parent_transform.inverted() @ armature_transform @ bone_transform

        # Default behavior for bones with no custom parent
        # For bones parented directly to the armature, matrix_local already represents their transform
        # relative to the armature, so no additional adjustments are needed.
        if self.i3d.settings['collapse_armatures']:
            # collapse_armatures deletes the armature object in the I3D, so we need to mutliply the armature matrix
            # into the root bone since the bone essentially replaces the armature object
            return armature_transform @ bone_transform
        # If there's no custom parent, and we're not collapsing armatures, the bone's local transform
        # is already correct relative to the armature. Just return it as-is.
        return bone_transform


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

        for bone in armature_object.data.bones:
            if bone.parent is None:
                self._add_bone(bone, self)

    def add_i3d_mapping_to_xml(self):
        """Wont export armature mapping, if 'collapsing armatures' is enabled
        """
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
    def _find_node_by_blender_object(root_nodes, target_object):
        """Recursively find a node in the scene graph by its Blender object."""
        for root_node in root_nodes:
            if root_node.blender_object == target_object:
                return root_node
            if child_result := SkinnedMeshRootNode._find_node_by_blender_object(root_node.children, target_object):
                return child_result
        return None

    @staticmethod
    def _get_new_bone_parent(armature_object: bpy.types.Armature,
                             bone: bpy.types.Bone) -> Optional[Union[bpy.types.Object, bpy.types.Bone]]:
        """Return the target object or bone of the first 'Child Of' constraint for a bone."""
        pose_bone = armature_object.pose.bones.get(bone.name)
        if not pose_bone:
            return None

        child_of_constraint = next((constraint for constraint in pose_bone.constraints
                                    if constraint.type == 'CHILD_OF'), None)
        if child_of_constraint and child_of_constraint.target:
            return child_of_constraint.target
        return None

    def update_bone_parent(self, parent):
        """Update the parent of each bone based on constraints or fallback to default behavior."""
        for bone in self.bones:
            new_parent_target = self._get_new_bone_parent(self.blender_object, bone)
            effective_parent = self._find_node_by_blender_object(self.i3d.scene_root_nodes, new_parent_target) \
                if new_parent_target else parent

            # Skip reparenting if the bone's parent is another bone in the same armature
            if bone.parent != self:
                continue

            self.logger.debug(f"Bone {bone.name} set parent to: "
                              f"{effective_parent.name if effective_parent else 'Root'}")

            # Remove bone from current parent
            if bone in self.children:
                self.children.remove(bone)
                self.element.remove(bone.element)

            # Add bone to new parent if found
            if effective_parent:
                bone.parent = parent
                effective_parent.add_child(bone)
                effective_parent.element.append(bone.element)
            else:
                # If no valid parent is found, add to the root
                bone.parent = None
                self.i3d.scene_root_nodes.append(bone)
                self.i3d.xml_elements['Scene'].append(bone.element)


class SkinnedMeshShapeNode(ShapeNode):
    def __init__(self, id_: int, skinned_mesh_object: bpy.types.Object, i3d: I3D,
                 parent: [SceneGraphNode or None] = None):
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
