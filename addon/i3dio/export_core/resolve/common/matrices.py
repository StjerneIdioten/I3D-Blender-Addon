from __future__ import annotations

from typing import TYPE_CHECKING

import mathutils

from ...blender.bones import BoneMode
from ...ir import NodeKind, SceneNode, SourceKind

if TYPE_CHECKING:
    from ...ctx import ExportContext

_CAM_LIGHT = {NodeKind.CAMERA, NodeKind.LIGHT}
_IDENTITY = mathutils.Matrix.Identity(4)


def _node_world_export_cached(
    ctx: ExportContext, node: SceneNode, world_export_cache: dict[int, mathutils.Matrix | None]
) -> mathutils.Matrix | None:
    """World matrix in EXPORT space for object nodes, cached per resolve pass.
    Returns None for nodes that do not have an object-backed transform in this pass (e.g. bones are handled elsewhere).
    """
    if node.id in world_export_cache:
        return world_export_cache[node.id]

    # World matrix in Blender space for this node, or None if node has no transform.
    # Note: bones are handled in _bone_local_export and never need world-space here.
    w_bl: mathutils.Matrix | None = None
    if node.source_kind is SourceKind.OBJECT:
        w_bl = node.obj.matrix_world.copy()

    if w_bl is None:
        world_export_cache[node.id] = None
        return None

    out = ctx.to_export_forward(w_bl) if node.kind in _CAM_LIGHT else ctx.to_export(w_bl)
    world_export_cache[node.id] = out
    return out


def _bone_local_export(
    ctx: ExportContext,
    node: SceneNode,
    parent: SceneNode | None,
    *,
    bone_mode: BoneMode,
    world_export_cache: dict[int, mathutils.Matrix | None],
    arm_world_cache: dict[int, mathutils.Matrix],
) -> mathutils.Matrix | None:
    """
    Bone local matrix in EXPORT space (ready for serializer):

    - bone->bone: return pure armature-space relative matrix (NO axis conversion).
    - root bone: apply ONE conversion (ctx.to_export_forward).
    - if armature is collapsed or reparented: rebase under nearest emitted parent.
    """
    br = node.bone_ref
    arm_obj = br.armature_obj

    # Bone matrix in armature space (Blender space)
    bone_arm_bl = br.matrix_armature_space(bone_mode)
    if bone_arm_bl is None:
        return None

    # Case 1: bone->bone (pure armature-space relative, NO conversion)
    if parent is not None and parent.source_kind is SourceKind.BONE_REF:
        return br.matrix_armature_space_relative(parent.bone_ref, bone_mode)

    # Root bone exported as a node (single conversion)
    bone_in_arm_export = ctx.to_export_forward(bone_arm_bl)

    # Case 2: non-collapsed armature => parent is armature object node
    if parent is not None and parent.source_kind is SourceKind.OBJECT and parent.obj is arm_obj:
        return bone_in_arm_export

    # Case 3: collapsed armature / reparented => rebase under emitted parent
    parent_world_e = (
        _node_world_export_cached(ctx, parent, world_export_cache) if parent is not None else _IDENTITY
    ) or _IDENTITY

    arm_world_e = arm_world_cache.setdefault(arm_obj.as_pointer(), ctx.to_export(arm_obj.matrix_world.copy()))

    return parent_world_e.inverted_safe() @ arm_world_e @ bone_in_arm_export


def _local_matrix_export_cached(
    ctx: "ExportContext",
    node: SceneNode,
    parent: SceneNode | None,
    world_export_cache: dict[int, mathutils.Matrix | None],
    arm_world_cache: dict[int, mathutils.Matrix],
    bone_mode: BoneMode,
) -> mathutils.Matrix | None:
    """Local matrix in EXPORT space for this node, or None if node has no transform."""
    if node.source_kind is SourceKind.BONE_REF:
        return _bone_local_export(
            ctx,
            node,
            parent,
            bone_mode=bone_mode,
            world_export_cache=world_export_cache,
            arm_world_cache=arm_world_cache,
        )

    world_e = _node_world_export_cached(ctx, node, world_export_cache)
    if world_e is None:
        return None

    if parent is None:
        local_e = world_e
    else:
        parent_world_e = _node_world_export_cached(ctx, parent, world_export_cache) or _IDENTITY
        local_e = parent_world_e.inverted_safe() @ world_e

    # If parent is a camera/light, we need to adjust for the flipped z-axis in GE space
    if parent and parent.kind in _CAM_LIGHT:
        local_e = ctx.conversion_matrix_inv @ local_e
        ctx.node_reporter(node, "matrices").debug(
            "Adjusted local matrix due to parent %s axis handling", parent.kind.name
        )

    return local_e


def resolve_matrices(ctx: "ExportContext") -> None:
    """Compute local EXPORT-space matrices for all nodes and store them on the node."""
    rep = ctx.reporter("matrices")
    rep.debug("Matrix resolve start")

    world_export_cache: dict[int, mathutils.Matrix | None] = {}
    arm_world_cache: dict[int, mathutils.Matrix] = {}

    def rec(node_id: int, emitted_parent: SceneNode | None) -> None:
        node = ctx.ir.scene_nodes[node_id]
        # XML parent is the nearest emitted ancestor (emit=False nodes are transparent).
        node.matrix_local_export = _local_matrix_export_cached(
            ctx, node, emitted_parent, world_export_cache, arm_world_cache, bone_mode=BoneMode.REST
        )

        next_emitted_parent = node if node.emit else emitted_parent
        for cid in ctx.ir.children_ids(node_id):
            rec(cid, next_emitted_parent)

    for root in ctx.ir.iter_roots():
        rec(root.id, None)
    rep.debug("Matrix resolve complete")
