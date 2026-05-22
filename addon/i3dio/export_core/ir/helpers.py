# i3dio/export_core/ir/helpers.py
from __future__ import annotations

from .model import NodeKind, ReferenceNodeExt, SceneNode, ShapeSceneExt


def clear_shape_binding(node: SceneNode) -> None:
    """Remove any Shape extension data from the node."""
    node._shape = None


def set_kind(node: SceneNode, kind: NodeKind) -> None:
    """
    Set node.kind and keep extension data consistent.

    This is the main guardrail that keeps the rest of the exporter deterministic:
    once kinds are resolved, code can assume that matching extensions exist and
    stale data is cleared when the kind changes.
    """
    if node.kind is kind:
        return
    node.kind = kind
    match kind:
        case NodeKind.SHAPE:
            node._shape = node._shape or ShapeSceneExt()
            node._ref = None
        case NodeKind.REFERENCE_NODE:
            node._ref = node._ref or ReferenceNodeExt()
            node._shape = None
        case _:
            node._shape = None
            node._ref = None


def to_transform_group(node: SceneNode) -> None:
    set_kind(node, NodeKind.TRANSFORM_GROUP)
