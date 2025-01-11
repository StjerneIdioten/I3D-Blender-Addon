"""
A lot of classes in this file is purely to have different classes for different objects that are functionally the same,
but it helps with debugging big trees and seeing the structure.
"""
from __future__ import annotations
from typing import (Union, Dict, List)
from collections import ChainMap
import mathutils
import bpy

from .node import (TransformGroupNode, SceneGraphNode)
from .shape import (ShapeNode, EvaluatedMesh)
from ..i3d import I3D
from .. import xml_i3d

import math


class SkinnedMeshBoneNode(TransformGroupNode):
    def __init__(self, id_: int, bone_object: bpy.types.Bone,
                 i3d: I3D, parent: SceneGraphNode, is_child_of: bool = False):
        self.is_child_of = is_child_of
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

        if self.is_child_of:
            # Bone is parented to a CHILD_OF constraint target, collapse_armature doesn't matter here
            # Multiply the bone's local transform with the inverse of the parent object's world matrix
            # to correctly position it relative to its new parent
            parent_matrix = self._matrix_to_i3d_space(self.parent.blender_object.matrix_world)
            return parent_matrix.inverted() @ bone_matrix

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
        is_child_of = False

        # Try to find pose bone for the bone object
        if pose_bone := self.blender_object.pose.bones.get(bone_object.name):
            processed_objects = self.i3d.processed_objects

            # Check if pose pose bone has a CHILD_OF constraint
            child_of = next((c for c in pose_bone.constraints if c.type == 'CHILD_OF'), None)
            if child_of and child_of.target:
                target = child_of.target
                if target not in processed_objects:
                    # Target object has not been processed yet, defer the constraint
                    self.logger.debug(f"Deferring CHILD_OF constraint for {bone_object.name} -> {target}")
                    self.i3d.deferred_constraints.append((bone_object, target, None))
                    return
                else:
                    # Use the target object if no subtarget is specified
                    self.logger.debug(f"Bone {bone_object} is child of {target}")
                    parent = processed_objects[target]
                    is_child_of = True

        self.bones.append(self.i3d.add_bone(bone_object, parent, is_child_of=is_child_of))
        current_bone = self.bones[-1]
        self.bone_mapping[bone_object.name] = current_bone.id

        for child_bone in bone_object.children:
            self._add_bone(child_bone, current_bone)

    def update_bone_parent(self, parent):
        for bone in self.bones:
            if bone.parent == self:
                self.element.remove(bone.element)
                self.children.remove(bone)
                if parent is not None:
                    bone.parent = parent
                    parent.add_child(bone)
                    parent.element.append(bone.element)
                else:
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
