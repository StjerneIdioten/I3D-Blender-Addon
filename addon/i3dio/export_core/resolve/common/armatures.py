from __future__ import annotations

from typing import TYPE_CHECKING

from ...blender.bones import BoneRef
from ...ir import SourceKind

if TYPE_CHECKING:
    import bpy

    from ...ctx import ExportContext


def resolve_armatures(ctx: "ExportContext") -> None:
    """Build bone nodes for armatures and cache bone-name->node-id mappings."""
    rep = ctx.reporter("armatures")

    created_bones = 0
    for arm_node in ctx.ir.iter_nodes(source_kind=SourceKind.OBJECT, source_object_type='ARMATURE'):
        arm_obj = arm_node.blender_ref

        # Collapse armature: don't emit the armature node, but still emit its bone children.
        arm_node.emit = not arm_obj.i3d_attributes.collapse_armature

        arm_ptr = arm_node.source_ptr
        if arm_ptr is None or arm_ptr in ctx.ir.index.bone_nodes_by_armature_ptr:
            continue  # Already built once.

        bone_map: dict[str, int] = {}

        def _add_bone(bone: bpy.types.Bone, parent_id: int) -> None:
            nonlocal created_bones
            node_id = ctx.builder.add_bone(BoneRef(armature_obj=arm_obj, bone_name=bone.name), parent_id=parent_id)
            bone_map[bone.name] = node_id
            created_bones += 1
            for child in bone.children:
                _add_bone(child, node_id)

        # Only loop root bones, recursion handles children.
        for bone in arm_obj.data.bones:
            if bone.parent is None:
                _add_bone(bone, arm_node.id)

        ctx.ir.index.bone_nodes_by_armature_ptr[arm_ptr] = bone_map

    rep.debug("Armature resolve complete: created_bones=%d", created_bones)
