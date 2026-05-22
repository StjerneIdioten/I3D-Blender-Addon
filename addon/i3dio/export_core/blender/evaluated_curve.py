# i3dio/export_core/blender/evaluated_curve.py
"""Curve evaluation and coordinate transformation for export."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from mathutils import Matrix

if TYPE_CHECKING:
    from ..ctx import ExportContext


def transform_curve_points(
    ctx: "ExportContext",
    positions: np.ndarray,
    *,
    reference_frame: Matrix | None = None,
    obj_matrix_world: Matrix | None = None,
) -> np.ndarray:
    """
    Transform curve control points into export coordinate space.

    Args:
        ctx: Export context with conversion settings.
        positions: Array of shape (N, 3) with control point positions in object-local space.
        reference_frame: Optional reference frame for relative positioning (merge features).
        obj_matrix_world: Object's world matrix (required if reference_frame is used).

    Returns:
        Transformed positions in export space as (N, 3) float32 array.
    """
    if positions.size == 0:
        return positions

    # Build the full transformation matrix
    # 1. Apply reference frame if provided (for relative positioning)
    # 2. Apply conversion matrix (axis conversion)
    # 3. Apply unit scale if enabled

    conv = ctx.conversion_matrix
    if ctx.setting("apply_unit_scale", True):
        conv = Matrix.Scale(ctx.unit_scale, 4) @ ctx.conversion_matrix

    if reference_frame is not None and obj_matrix_world is not None:
        # Transform from object space to reference frame, then to export space
        full_matrix = conv @ (reference_frame.inverted() @ obj_matrix_world)
    else:
        # Just convert to export space (points are already in object-local space)
        full_matrix = conv

    # Convert to numpy-friendly format for batch transformation
    m = np.array(full_matrix.to_3x3(), dtype=np.float32)
    t = np.array(full_matrix.translation, dtype=np.float32)

    # Transform all points: result = points @ M^T + translation
    transformed = positions @ m.T + t

    return transformed.astype(np.float32)
