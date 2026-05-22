from __future__ import annotations

from typing import TYPE_CHECKING

from ... import xml_i3d

if TYPE_CHECKING:
    from ..ctx import ExportContext


def emit_user_attributes(ctx: ExportContext, user_attrs_elem) -> None:
    rep = ctx.reporter("user_attributes")
    mapping = ctx.ir.index.user_attributes_by_node_id
    if not mapping:
        rep.debug("No user attributes to emit")
        return

    total_nodes = 0
    total_entries = 0

    for node_id in ctx.ir.node_order:
        entries = mapping.get(node_id)
        if not entries:
            continue
        total_nodes += 1
        ua_elem = xml_i3d.SubElementA(user_attrs_elem, "UserAttribute", {"nodeId": node_id})
        for entry in entries:
            xml_i3d.SubElementA(ua_elem, "Attribute", {"name": entry.name, "type": entry.type, "value": entry.value})
            total_entries += 1

    rep.debug("Emitted user attributes: nodes=%d attrs=%d", total_nodes, total_entries)
