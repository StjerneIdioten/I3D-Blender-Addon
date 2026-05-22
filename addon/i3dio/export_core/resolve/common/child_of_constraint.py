from __future__ import annotations

from typing import TYPE_CHECKING

from ...ir import SourceKind

if TYPE_CHECKING:
    from ...ctx import ExportContext


def resolve_bone_childof(ctx: ExportContext) -> None:
    """Resolve Child Of constraints by reparenting nodes as needed."""
    rep = ctx.reporter("child_of_constraint")

    def _is_ancestor(ancestor_id: int, node_id: int | None) -> bool:
        """True if ancestor_id is in node_id's parent chain."""
        while node_id is not None:
            if node_id == ancestor_id:
                return True
            node_id = ctx.ir.scene_nodes[node_id].parent_id
        return False

    reparented = 0
    missing_targets = 0

    for bone_node in ctx.ir.iter_nodes(source_kind=SourceKind.BONE_REF):
        bone_ref = bone_node.blender_ref
        if (pbone := bone_ref.pose_bone()) is None:
            continue
        if (childof := next((c for c in pbone.constraints if c.type == 'CHILD_OF' and c.target), None)) is None:
            continue

        target_obj = childof.target
        obj_rep = ctx.object_reporter(target_obj, "child_of_constraint")
        node_ids = ctx.ir.index.node_id_by_blender_ptr.get(target_obj.as_pointer())
        if not node_ids:
            obj_rep.warning(
                "Child Of constraint target %r is not part of the export; cannot reparent bone %r.",
                target_obj.name,
                bone_ref.name,
                code="child_of_target_not_exported",
            )
            missing_targets += 1
            continue

        target_node_id = node_ids[0]  # Use first node if multiple.

        if target_node_id == bone_node.id or _is_ancestor(bone_node.id, target_node_id):
            obj_rep.warning(
                "Child Of constraint target %r would create a cycle when reparenting bone %r; skipping.",
                target_obj.name,
                bone_ref.name,
                code="child_of_cycle_detected",
            )
            continue
        ctx.ir.attach(bone_node.id, target_node_id)
        reparented += 1

    rep.debug("Child Of constraint resolve complete: reparented=%d, missing_targets=%d", reparented, missing_targets)
