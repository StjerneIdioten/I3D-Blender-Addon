# i3dio/export_core/geometry/built.py
"""Base types for built geometry (shapes)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ..ir import EmitAttrs


class ShapeKind(Enum):
    """Discriminator for built shape types."""

    INDEXED_TRIANGLE_SET = "IndexedTriangleSet"
    NURBS_CURVE = "NurbsCurve"


@dataclass(slots=True)
class BuiltShape:
    """Base class for all built geometry types.

    Subclasses:
        - BuiltITS: Indexed Triangle Set (meshes)
        - BuiltNurbsCurve: NURBS curves (future)
    """

    kind: ShapeKind
    name: str
    shape_id: int
    attrs: EmitAttrs = field(default_factory=EmitAttrs)
