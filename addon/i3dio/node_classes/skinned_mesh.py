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
            bone_transform = self.blender_object.matrix_local
        else:
            bone_transform = self.blender_object.parent.matrix_local.inverted() @ self.blender_object.matrix_local

        conversion_matrix = self.i3d.conversion_matrix @ bone_transform @ self.i3d.conversion_matrix.inverted()

        return conversion_matrix


class SkinnedMeshRootNode(TransformGroupNode):
    def __init__(self, id_: int, armature_object: bpy.types.Armature,
                 i3d: I3D, parent: SceneGraphNode):
        self.bones: Dict[str, SkinnedMeshBoneNode] = {}
        super().__init__(id_=id_, empty_object=armature_object, i3d=i3d, parent=parent)

    def add_bone(self, bone_node: SkinnedMeshBoneNode):
        self.bones[bone_node.name] = bone_node


class SkinnedMeshShapeNode(ShapeNode):
    pass
