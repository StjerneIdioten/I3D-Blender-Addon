# i3dio/export_core/blender/bones.py
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import bpy
import mathutils


class BoneMode(Enum):
    REST = "REST"
    POSE = "POSE"


@dataclass(frozen=True, slots=True)
class BoneRef:
    """Reference to a bone within an armature object. This is stored as the IR node blender_ref for bone nodes."""

    armature_obj: bpy.types.Object
    bone_name: str

    @property
    def name(self) -> str:
        return self.bone_name

    def pose_bone(self) -> bpy.types.PoseBone | None:
        return self.armature_obj.pose.bones.get(self.bone_name) if self.armature_obj.pose is not None else None

    def data_bone(self) -> bpy.types.Bone | None:
        return self.armature_obj.data.bones.get(self.bone_name)

    def matrix_armature_space(self, mode: BoneMode) -> mathutils.Matrix | None:
        """Bone matrix in *armature object space* (Blender space, no export conversion)."""
        if mode is BoneMode.POSE:
            pb = self.pose_bone()
            return pb.matrix.copy() if pb is not None else None

        b = self.data_bone()
        return b.matrix_local.copy() if b is not None else None

    def matrix_armature_space_relative(self, parent: BoneRef | None, mode: BoneMode) -> mathutils.Matrix | None:
        """Bone->parent relative matrix in armature space. If parent missing, returns self matrix."""
        m = self.matrix_armature_space(mode)
        if m is None:
            return None

        if parent is None:
            return m

        pm = parent.matrix_armature_space(mode)
        return (pm.inverted_safe() @ m) if pm is not None else m

    def world_matrix(self, mode: BoneMode = BoneMode.POSE) -> mathutils.Matrix | None:
        """Best-effort bone world matrix in Blender space."""
        arm_w = self.armature_obj.matrix_world
        m_arm = self.matrix_armature_space(mode)
        return (arm_w @ m_arm) if m_arm is not None else None
