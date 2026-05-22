from __future__ import annotations

from typing import TYPE_CHECKING

import mathutils

from ..common.matrices import BoneMode, _local_matrix_export_cached

if TYPE_CHECKING:
    from ...ctx import ExportContext
    from ...ir import SceneNode


def compute_local_matrices_for_current_frame(ctx: "ExportContext") -> dict[int, mathutils.Matrix | None]:
    """Compute local EXPORT-space matrices for the *current* scene frame.

    This mirrors resolve_matrices() but returns a dict instead of mutating SceneNode.matrix_local_export.

    Important: hierarchy semantics match the serializer: local matrices are relative to the nearest emitted parent.
    """

    world_cache: dict[int, mathutils.Matrix | None] = {}
    arm_world_cache: dict[int, mathutils.Matrix] = {}

    out: dict[int, mathutils.Matrix | None] = {}

    def rec(node_id: int, emitted_parent: "SceneNode | None") -> None:
        node = ctx.ir.scene_nodes[node_id]
        out[node_id] = _local_matrix_export_cached(
            ctx, node, emitted_parent, world_cache, arm_world_cache, bone_mode=BoneMode.POSE
        )

        next_emitted_parent = node if node.emit else emitted_parent
        for child_id in ctx.ir.children_ids(node_id):
            rec(child_id, next_emitted_parent)

    for root in ctx.ir.iter_roots():
        rec(root.id, None)

    return out
