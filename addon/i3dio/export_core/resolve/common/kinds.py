from __future__ import annotations

from typing import TYPE_CHECKING

from ...ir import NodeKind, SourceKind, set_kind, to_transform_group

if TYPE_CHECKING:
    from ...ctx import ExportContext
    from ...ir import SceneNode

_OBJECT_TYPE_TO_KIND: dict[str, NodeKind] = {
    "CAMERA": NodeKind.CAMERA,
    "LIGHT": NodeKind.LIGHT,
    "MESH": NodeKind.SHAPE,
    "CURVE": NodeKind.TRANSFORM_GROUP,  # Resolved properly later, but if more than 1 spline, CURVE ob will be parent
    "FONT": NodeKind.SHAPE,
    "EMPTY": NodeKind.TRANSFORM_GROUP,
    # ARMATURE intentionally not here -> TG
}


def resolve_kind_for_node(ctx: ExportContext, node: SceneNode) -> None:
    """
    Resolve a traversed OBJECT node's kind.
    Traversal produces "UNRESOLVED" nodes so the hierarchy is built first and specialized later.
    """
    if node.kind is not NodeKind.UNRESOLVED or node.source_kind is not SourceKind.OBJECT:
        return  # already resolved or not an OBJECT

    obj_type_raw = node.source_object_type or 'EMPTY'
    if (allowed := ctx.setting("object_types_to_export", ())) and obj_type_raw not in allowed:
        to_transform_group(node)
        return  # Object type excluded by settings, keep as TG to preserve hierarchy.

    obj_type_eff = node.effective_source_object_type or obj_type_raw
    set_kind(node, _OBJECT_TYPE_TO_KIND.get(obj_type_eff, NodeKind.TRANSFORM_GROUP))

    if ctx.is_dev:
        assert node.kind is not NodeKind.UNRESOLVED, "Failed to resolve kind for node %r" % (node,)
