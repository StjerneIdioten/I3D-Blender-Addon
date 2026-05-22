# i3dio/export_core/geometry/mesh/its.py
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

import numpy as np

from ..built import BuiltShape, ShapeKind


class MaterialKeyKind(str, Enum):
    """How triangles/subsets are grouped by material.

    - SLOT_INDEX: subset keys are material slot indices from Blender meshes
        (materialIds resolved per Scene node instance).
    - MATERIAL_ID: subset keys are resolved global export material IDs
        (used for merge modes where contributors may have different slot layouts).
    """

    SLOT_INDEX = "slot_index"
    MATERIAL_ID = "material_id"


Vec3f = np.ndarray  # (N,3) float32
Vec4f = np.ndarray  # (N,4) float32
Vec2f = np.ndarray  # (N,2) float32
ArrI = np.ndarray  # (M,) int32/uint32


@dataclass(slots=True)
class BuiltSubset:
    first_index: int
    num_indices: int
    first_vertex: int
    num_vertices: int
    material_id: int  # material key (see BuiltITS.material_kind)
    material_slot_name: str | None = None  # optional Subset@materialSlotName


@dataclass(slots=True)
class BuiltITS(BuiltShape):
    """Built Indexed Triangle Set (mesh geometry)."""

    kind: ShapeKind = field(default=ShapeKind.INDEXED_TRIANGLE_SET, init=False)

    material_kind: MaterialKeyKind = MaterialKeyKind.SLOT_INDEX

    # Required data arrays, if not filled builder need to return None
    positions: Vec3f = field(repr=False, default=None)  # (N,3) float32
    normals: Vec3f = field(repr=False, default=None)  # (N,3) float32 (mandatory)
    indices: ArrI = field(repr=False, default=None)  # (K,) int32/uint32, flattened

    subsets: list[BuiltSubset] = field(default_factory=list)

    # Optional/variable
    uvs: list[Vec2f] = field(repr=False, default_factory=list)  # 0..4, each (N,2) float32
    color: Vec4f | None = field(repr=False, default=None)  # (N,4) float32 RGBA

    g: np.ndarray | None = None
    bi: np.ndarray | None = None

    # Skinned mesh multi-weight data (per loop vertex). Both are (N,4).
    bw: np.ndarray | None = None  # float32 weights
    bi4: np.ndarray | None = None  # int32 bind indices

    @property
    def material_ids(self) -> list[int]:
        """Material keys in subset order (see material_kind)."""
        return [s.material_id for s in self.subsets]

    @property
    def vertex_count(self) -> int:
        return int(self.positions.shape[0])

    @property
    def triangle_count(self) -> int:
        return int(self.indices.shape[0] // 3)


CurveType = Literal["linear", "cubic"]


@dataclass(slots=True)
class BuiltNurbsCurve(BuiltShape):
    """Built NURBS curve shape."""

    kind: ShapeKind = field(default=ShapeKind.NURBS_CURVE, init=False)

    control_positions: Vec3f = field(repr=False, default=None)  # (N,3) float32
    curve_type: CurveType = "cubic"
    degree: int = 3
    is_cyclic: bool = False

    @property
    def point_count(self) -> int:
        return int(self.control_positions.shape[0])
