from __future__ import annotations

import math
from typing import TYPE_CHECKING

from ...utility import isclose_value
from ...xml_i3d import SubElementA, write_attribute
from .xml_attrs import write_child_elements, write_node_attributes

if TYPE_CHECKING:
    from ..ctx import ExportContext
    from ..ir import SceneNode


def _write_transform(ctx: ExportContext, elem, node: SceneNode) -> None:
    """Writes node.matrix_local_export (already in EXPORT space) into XML attributes."""
    matrix_local_export = node.matrix_local_export
    if matrix_local_export is None:
        return
    # Translation (scaled)
    t = matrix_local_export.to_translation()
    if not isclose_value(t, (0.0, 0.0, 0.0)):
        t_scaled = (t.x * ctx.unit_scale, t.y * ctx.unit_scale, t.z * ctx.unit_scale)
        write_attribute(elem, "translation", t_scaled)

    # Rotation (degrees)
    r = matrix_local_export.to_euler("XYZ")
    if not isclose_value(r, (0.0, 0.0, 0.0)):
        r_deg = (math.degrees(r.x), math.degrees(r.y), math.degrees(r.z))
        write_attribute(elem, "rotation", r_deg)

    # Scale
    if matrix_local_export.is_negative:
        ctx.node_reporter(node).warning(
            "Negative scale detected (not supported by GIANTS Engine); scale will be omitted (defaults to 1 1 1)."
        )
        return

    s = matrix_local_export.to_scale()
    if not isclose_value(s, (1.0, 1.0, 1.0)):
        write_attribute(elem, "scale", (s.x, s.y, s.z))


def emit_scene(ctx: ExportContext, scene_elem) -> None:
    rep = ctx.reporter("emit_scene")

    def emit_node(node_id: int, parent_elem) -> None:
        node = ctx.ir.scene_nodes[node_id]
        next_parent = parent_elem
        if node.emit:
            elem = SubElementA(parent_elem, node.kind.value, {"name": node.name, "nodeId": node.id})
            write_node_attributes(elem=elem, node=node)
            write_child_elements(parent_elem=elem, emit_attrs=node.attrs)
            _write_transform(ctx, elem, node)
            next_parent = elem

        for child_id in ctx.ir.emitted_child_ids(node_id):
            emit_node(child_id, next_parent)

    roots = ctx.ir.emitted_child_ids(None)
    rep.info("Emitting scene with %d root nodes", len(roots))
    for root_id in roots:
        emit_node(root_id, scene_elem)
