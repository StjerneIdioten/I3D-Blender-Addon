from __future__ import annotations

from typing import TYPE_CHECKING

import bpy

from ...ir import NodeKind, set_kind, to_transform_group

if TYPE_CHECKING:
    from ...ctx import ExportContext


def curve_has_geometry(curve_data: bpy.types.Curve) -> bool:
    """Check if a curve has extrusion/bevel that creates 3D mesh-like geometry.

    When a curve has bevel depth, extrusion, or a bevel object, it should be
    exported as an evaluated mesh (IndexedTriangleSet) rather than a NurbsCurve.

    Args:
        curve_data: The Blender Curve datablock.

    Returns:
        True if the curve has geometry that should be mesh-converted.
    """
    # Bevel depth creates a tube-like profile
    if curve_data.bevel_depth > 0:
        return True

    # Extrusion creates a ribbon/extruded shape
    if curve_data.extrude > 0:
        return True

    # Custom bevel object provides a cross-section profile
    if curve_data.bevel_object is not None:
        return True

    return False


def resolve_curve_shapes(ctx: ExportContext) -> None:
    """Resolve CURVE objects into appropriate Shape nodes.

    Handles two scenarios:
    1. Simple curves (no bevel/extrusion): Create NurbsCurve shapes, one per spline.
       The parent CURVE node becomes a TransformGroup with child Shape nodes.

    2. Curves with geometry (bevel/extrusion): Export as mesh via evaluated geometry.
       These go through the normal mesh pipeline as IndexedTriangleSet.

    Note: In Blender, one Curve object can contain multiple splines.
          In i3D, each spline must be a separate Shape node.
          We use the evaluated curve to handle modifiers (Array, Mirror, etc.).
    """
    for node in ctx.ir.iter_nodes(source_object_type='CURVE', emitted_only=True):
        rep = ctx.node_reporter(node, "curve_shapes")
        obj = node.obj

        # Use evaluated object to handle modifiers (Array, Mirror, Geometry Nodes, etc.)
        ev_obj = obj.evaluated_get(ctx.depsgraph)
        curve_data = ev_obj.data

        splines = curve_data.splines
        if not splines:
            rep.warning("Curve object has no splines; exporting as TransformGroup.")
            to_transform_group(node)
            continue

        # Check if this curve has 3D geometry (bevel/extrusion)
        if curve_has_geometry(curve_data):
            # Export as evaluated mesh (IndexedTriangleSet).
            # 1. Promote the node to SHAPE (creates _shape extension)
            # 2. Set export override so link_node registers it as a mesh
            rep.debug("Curve has bevel/extrusion; exporting as evaluated mesh.")
            set_kind(node, NodeKind.SHAPE)
            node.source_object_type_override = 'MESH'
            # link_node will be called in shape_links pass and will register
            # the mesh shape. The evaluated geometry will be built in finalize phase.
            continue

        # Simple spline curve - create child Shape nodes for each spline
        rep.debug("Curve has %d spline(s); creating NurbsCurve shape(s).", len(splines))

        # Convert the parent CURVE node to a TransformGroup (container for spline shapes)
        to_transform_group(node)

        # Create a derived Shape node for each spline
        for i, spline in enumerate(splines):
            # Only support NURBS and BEZIER splines for NurbsCurve export
            # POLY splines are also supported (they're basically linear NURBS)
            if spline.type not in {'NURBS', 'BEZIER', 'POLY'}:
                rep.warning(
                    "Spline %d has unsupported type %r; skipping.",
                    i,
                    spline.type,
                )
                continue

            shape_id = ctx.shapes.get_or_add_curve(obj, spline_index=i)
            child_name = f"{node.name}_Spline{i + 1}" if len(splines) > 1 else node.name
            ctx.builder.add_derived_shape(
                name=child_name,
                parent_id=node.id,
                shape_id=shape_id,
                source_obj=obj,
            )
