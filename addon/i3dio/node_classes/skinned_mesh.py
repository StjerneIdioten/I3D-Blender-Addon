"""
A lot of classes in this file is purely to have different classes for different objects that are functionally the same,
but it helps with debugging big trees and seeing the structure.
"""
from __future__ import annotations
from typing import (Union, Dict, List, Type, OrderedDict, Optional)
import mathutils
import bpy

from . import node
from .node import (TransformGroupNode, SceneGraphNode)
from .shape import (ShapeNode, EvaluatedMesh)
from ..i3d import I3D


class SkinnedMeshBoneNode(TransformGroupNode):
    def __init__(self, id_: int, bone_object: bpy.types.Bone,
                 i3d: I3D, parent: SceneGraphNode):
        super().__init__(id_=id_, empty_object=bone_object, i3d=i3d, parent=parent)

    @property
    def _transform_for_conversion(self) -> mathutils.Matrix:

        if self.blender_object.parent is None:
            # The bone is parented to the armature directly, and therefor should just use the matrix_local which is in
            # relation to the armature anyway.
            bone_transform = self.blender_object.matrix_local
        else:
            # To find the transform of the bone, we take the inverse of its parents transform in armature space and
            # multiply that with the bones transform in armature space. The new 4x4 matrix gives the position and
            # rotation in relation to the parent bone (of the head, that is)
            bone_transform = self.blender_object.parent.matrix_local.inverted() @ self.blender_object.matrix_local

        conversion_matrix = self.i3d.conversion_matrix @ bone_transform @ self.i3d.conversion_matrix.inverted()

        return conversion_matrix


class SkinnedMeshRootNode(TransformGroupNode):
    def __init__(self, id_: int, armature_object: bpy.types.Armature,
                 i3d: I3D, parent: SceneGraphNode):
        self.bones: Dict[str, SkinnedMeshBoneNode] = {}
        super().__init__(id_=id_, empty_object=armature_object, i3d=i3d, parent=parent)
        for bone in armature_object.data.bones:
            if bone.parent is None:
                self._add_bone(bone, self)

    def _add_bone(self, bone_object: bpy.types.Bone, parent: Union[SkinnedMeshBoneNode, SkinnedMeshRootNode]):
        """Recursive function for adding a bone along with all of its children"""
        self.logger.debug(f"Exporting Bone: '{bone_object.name}', head: {bone_object.head}, tail: {bone_object.tail}")
        bone_node = self.i3d.add_bone(bone_object, parent)
        self.bones[bone_object.name] = bone_node
        for child_bone in bone_object.children:
            self._add_bone(child_bone, bone_node)


class SkinnedMeshShapeNode(ShapeNode):
    pass
