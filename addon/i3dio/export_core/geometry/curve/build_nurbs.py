# i3dio/export_core/geometry/curve/build_nurbs.py
"""Build NurbsCurve geometry from Blender spline data."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from ...blender.evaluated_curve import transform_curve_points
from ..mesh.its import BuiltNurbsCurve, CurveType

if TYPE_CHECKING:
    import bpy

    from ...ctx import ExportContext
    from ...resources.shapes import ShapeEntry

# Minimum control points required by i3D schema (2 points causes schema validation error)
MIN_CONTROL_POINTS = 3


def _get_curve_type(spline: "bpy.types.Spline") -> CurveType:
    """Determine the i3D curve type based on Blender spline type.

    i3D supports:
    - "linear": Linear interpolation between control points
    - "cubic": Cubic spline interpolation (Bezier/NURBS)

    Args:
        spline: The Blender spline object.

    Returns:
        The i3D curve type string.
    """
    match spline.type:
        case 'POLY':
            return "linear"
        case 'BEZIER' | 'NURBS':
            return "cubic"
        case _:
            # Fallback to cubic for unknown types
            return "cubic"


def _get_degree(spline: "bpy.types.Spline") -> int:
    """Get the degree of the spline.

    For NURBS splines, this is the order_u - 1.
    For Bezier, we use degree 3 (cubic).
    For Poly, we use degree 1 (linear).

    Args:
        spline: The Blender spline object.

    Returns:
        The spline degree.
    """
    match spline.type:
        case 'NURBS':
            # NURBS order = degree + 1
            return max(1, spline.order_u - 1)
        case 'BEZIER':
            return 3  # Bezier curves are cubic
        case 'POLY':
            return 1  # Linear
        case _:
            return 3


def _extract_control_points(spline: "bpy.types.Spline") -> np.ndarray:
    """Extract control point positions from a spline.

    Handles different spline types:
    - NURBS: Uses spline.points[].co (x, y, z, w)
    - BEZIER: Uses bezier_points[].co (handle control varies)
    - POLY: Same as NURBS (uses points)

    Args:
        spline: The Blender spline object.

    Returns:
        numpy array of shape (N, 3) with control point positions.
    """
    if spline.type == 'BEZIER':
        # For Bezier, we need the main control points (not handles)
        # Each bezier point has: handle_left, co (main point), handle_right
        points = spline.bezier_points
        if not points:
            return np.empty((0, 3), dtype=np.float32)

        # For i3D NurbsCurve, we export just the knot positions
        # The curve type "cubic" handles the interpolation
        coords = np.array([p.co[:3] for p in points], dtype=np.float32)
        return coords

    else:
        # NURBS and POLY use spline.points
        points = spline.points
        if not points:
            return np.empty((0, 3), dtype=np.float32)

        # points[].co is (x, y, z, w) - we only need xyz
        coords = np.array([p.co[:3] for p in points], dtype=np.float32)
        return coords


def _ensure_minimum_points(positions: np.ndarray, rep) -> np.ndarray:
    """Ensure the curve has at least MIN_CONTROL_POINTS control points.

    The i3D schema requires at least 3 control points. If a curve has only 2 points,
    we insert a midpoint to satisfy the schema while preserving the curve shape.

    Args:
        positions: Array of shape (N, 3) with control point positions.
        rep: Reporter for logging warnings.

    Returns:
        Array with at least MIN_CONTROL_POINTS points.
    """
    n_points = len(positions)

    if n_points >= MIN_CONTROL_POINTS:
        return positions

    if n_points == 2:
        # Insert midpoint between the two existing points
        midpoint = (positions[0] + positions[1]) / 2.0
        rep.info("Curve has only 2 control points; inserting midpoint to satisfy i3D schema requirement (min 3 points)")
        return np.array([positions[0], midpoint, positions[1]], dtype=np.float32)

    if n_points == 1:
        # Single point - duplicate it to create a degenerate curve
        rep.warning("Curve has only 1 control point; duplicating to create minimum 3 points")
        return np.array([positions[0], positions[0], positions[0]], dtype=np.float32)

    # n_points == 0 should be handled earlier
    return positions


def build_nurbs_curve(ctx: "ExportContext", entry: "ShapeEntry") -> BuiltNurbsCurve | None:
    """Build a BuiltNurbsCurve from a ShapeEntry.

    Uses the evaluated curve object to handle modifiers (Array, Mirror, etc.).

    Args:
        ctx: The export context.
        entry: The shape entry containing curve information.

    Returns:
        A BuiltNurbsCurve object, or None if building fails.
    """
    rep = ctx.reporter("build_nurbs")

    if not entry.contributors:
        rep.warning("NurbsCurve shape %r has no contributors", entry.name)
        return None

    # Get the source object and spline index from the key
    contributor = entry.contributors[0]
    obj = contributor.obj
    spline_index = entry.key.spline_index

    if spline_index is None:
        rep.warning("NurbsCurve shape %r has no spline_index in key", entry.name)
        return None

    # Use evaluated object to handle modifiers
    ev_obj = obj.evaluated_get(ctx.depsgraph)
    curve_data = ev_obj.data

    if not hasattr(curve_data, 'splines'):
        rep.warning("Object %r is not a curve", obj.name)
        return None

    splines = curve_data.splines
    if spline_index < 0 or spline_index >= len(splines):
        rep.warning(
            "Spline index %d out of range for curve %r (has %d splines)",
            spline_index,
            obj.name,
            len(splines),
        )
        return None

    spline = splines[spline_index]

    # Extract control points (in object-local space, from evaluated curve)
    control_positions = _extract_control_points(spline)
    if control_positions.size == 0:
        rep.warning("Spline %d in curve %r has no control points", spline_index, obj.name)
        return None

    # Ensure minimum control points for i3D schema compliance
    control_positions = _ensure_minimum_points(control_positions, rep)

    # Transform points to export coordinate space
    # Use evaluated object's matrix_world for correct transform after modifiers
    control_positions = transform_curve_points(
        ctx,
        control_positions,
        reference_frame=contributor.reference_frame,
        obj_matrix_world=ev_obj.matrix_world if contributor.reference_frame else None,
    )

    # Determine curve properties
    curve_type = _get_curve_type(spline)
    degree = _get_degree(spline)
    is_cyclic = spline.use_cyclic_u

    rep.debug(
        "Built NurbsCurve %r: %d points, type=%s, degree=%d, cyclic=%s",
        entry.name,
        len(control_positions),
        curve_type,
        degree,
        is_cyclic,
    )

    return BuiltNurbsCurve(
        name=entry.name,
        shape_id=entry.id,
        control_positions=control_positions,
        curve_type=curve_type,
        degree=degree,
        is_cyclic=is_cyclic,
    )
