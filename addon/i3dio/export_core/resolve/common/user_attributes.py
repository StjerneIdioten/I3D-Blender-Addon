from __future__ import annotations

from typing import TYPE_CHECKING

from ...ir import SourceKind, UserAttributeEntry

if TYPE_CHECKING:
    from ...ctx import ExportContext


def resolve_user_attributes(ctx: ExportContext) -> None:
    rep = ctx.reporter("user_attributes")
    out = ctx.ir.index.user_attributes_by_node_id

    total_entries = 0
    total_nodes = 0

    for node in ctx.ir.iter_nodes(emitted_only=True, source_kind=SourceKind.OBJECT):
        entries: list[UserAttributeEntry] = []
        for item in node.obj.i3d_user_attributes.attribute_list:
            entries.append(
                UserAttributeEntry(name=item.name, type=item.type.replace("data_", ""), value=getattr(item, item.type))
            )

        if entries:
            out[node.id] = entries
            total_nodes += 1
            total_entries += len(entries)

    rep.debug("Collected user attributes: nodes=%d attrs=%d", total_nodes, total_entries)
