from __future__ import annotations

from math import sqrt
from typing import TYPE_CHECKING

from mathutils import Vector

from ...ir import NodeKind, SourceKind

if TYPE_CHECKING:
    import bpy

    from ...ctx import ExportContext


def _bv_center_and_radius_export_local(
    ctx: ExportContext, *, node_obj: bpy.types.Object, bv_obj: bpy.types.Object
) -> tuple[Vector, float]:
    """
    Compute bvCenter/bvRadius in *export-local space* of the shape node.

    Notes:
    - Uses the 8 bbox corners, transformed into node local space and then into export space.
      This makes radius robust under unit conversion and conservative under non-uniform scales.
    """
    cm3 = ctx.conversion_matrix.to_3x3()
    inv_node = node_obj.matrix_world.inverted_safe()
    unit_scale = ctx.unit_scale

    corners_export = [(cm3 @ (inv_node @ (bv_obj.matrix_world @ Vector(c)))) * unit_scale for c in bv_obj.bound_box]
    center = sum(corners_export, Vector()) / 8.0

    # radius = max distance from center to any corner (in export-local space)
    r2 = 0.0
    for c in corners_export:
        d = c - center
        r2 = max(r2, d.length_squared)

    return center, sqrt(r2)


def resolve_bounding_volumes(ctx: ExportContext) -> None:
    # Only actual mesh objects have the bounding_volume_object property.
    # Note: source_object_type can be overridden (e.g., curves-with-geometry become 'MESH'),
    # so we check the actual object type instead.
    # Also skip derived nodes (e.g., NurbsCurve spline shapes) which don't have obj.
    for node in ctx.ir.iter_nodes(kind=NodeKind.SHAPE, source_kind=SourceKind.OBJECT, emitted_only=True):
        if node.obj.type != 'MESH':
            continue
        if (bv := node.obj.data.i3d_attributes.bounding_volume_object) is None:
            continue

        center, radius = _bv_center_and_radius_export_local(ctx, node_obj=node.obj, bv_obj=bv)

        shape = ctx.shapes.get_entry(node.shape.shape_id)
        # Explicit BV object should win (don’t "setdefault" and accidentally keep stale values).
        shape.attrs.node["bvCenter"] = center
        shape.attrs.node["bvRadius"] = float(radius)
