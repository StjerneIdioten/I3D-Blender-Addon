from __future__ import annotations

from typing import TYPE_CHECKING

from ....utility import strip_sorting_prefix
from ...ir import SceneNode

if TYPE_CHECKING:
    from ...ctx import ExportContext


def finalize_name_for_node(ctx: "ExportContext", node: SceneNode) -> None:
    if not (sep := ctx.setting("object_sorting_prefix", ":")) or not node.name:
        return
    before = node.name
    after = strip_sorting_prefix(before, sep)
    if before != after:
        ctx.node_reporter(node, "names").debug("New name: %r -> %r (sep=%r)", before, after, sep)
        node.name = after
