# i3dio/export_core/geometry/mesh/build_its.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

from ...resources.shapes import ShapeEntry, ShapeMode
from .extract_contrib import ItsContributorStream, extract_contrib_its
from .its import BuiltITS, BuiltSubset, MaterialKeyKind
from .subsets import build_indices_and_subsets

if TYPE_CHECKING:
    from ...ctx import ExportContext


@dataclass(slots=True)
class _MergedArrays:
    """Accumulator for merging multiple contributor streams into final arrays."""

    total_verts: int
    total_tris: int
    max_uvs: int
    want_color: bool
    want_g: bool
    want_bi: bool
    want_skin: bool

    # Pre-allocated output arrays
    positions: np.ndarray = field(init=False)
    normals: np.ndarray = field(init=False)
    uvs: list[np.ndarray] = field(init=False)
    color: np.ndarray | None = field(init=False)
    g: np.ndarray | None = field(init=False)
    bi: np.ndarray | None = field(init=False)
    bw: np.ndarray | None = field(init=False)
    bi4: np.ndarray | None = field(init=False)
    tri_loops: np.ndarray = field(init=False)
    tri_mat_id: np.ndarray = field(init=False)

    _v_offset: int = field(init=False, default=0)
    _t_offset: int = field(init=False, default=0)

    def __post_init__(self) -> None:
        n, t = self.total_verts, self.total_tris
        self.positions = np.empty((n, 3), dtype=np.float32)
        self.normals = np.empty((n, 3), dtype=np.float32)
        self.uvs = [np.empty((n, 2), dtype=np.float32) for _ in range(self.max_uvs)]
        self.color = np.empty((n, 4), dtype=np.float32) if self.want_color else None
        self.g = np.empty((n,), dtype=np.float32) if self.want_g else None
        self.bi = np.empty((n,), dtype=np.int32) if self.want_bi else None
        self.bw = np.empty((n, 4), dtype=np.float32) if self.want_skin else None
        self.bi4 = np.empty((n, 4), dtype=np.int32) if self.want_skin else None
        self.tri_loops = np.empty((t, 3), dtype=np.int32)
        self.tri_mat_id = np.empty((t,), dtype=np.int32)

    def add_stream(self, s: ItsContributorStream) -> None:
        """Merge one contributor stream into the accumulated arrays."""
        lc, tc = s.loop_count, s.tri_loops.shape[0]
        vs = slice(self._v_offset, self._v_offset + lc)

        # Core vertex data
        self.positions[vs] = s.positions
        self.normals[vs] = s.normals

        # UVs: pad with last layer or zeros
        for i, uv_out in enumerate(self.uvs):
            uv_out[vs] = s.uvs[i] if i < len(s.uvs) else (s.uvs[-1] if s.uvs else 0.0)

        # Optional per-vertex attributes
        if self.color is not None:
            self.color[vs] = s.color if s.color is not None else 0.0
        if self.g is not None:
            self.g[vs] = s.generic if s.generic is not None else 0.0
        if self.bi is not None:
            self.bi[vs] = s.bind_idx if s.bind_idx is not None else 0
        if self.bw is not None and self.bi4 is not None:
            if s.blend_weights is not None and s.blend_indices is not None:
                self.bw[vs], self.bi4[vs] = s.blend_weights, s.blend_indices
            else:
                self.bw[vs], self.bi4[vs] = 0.0, 0

        # Triangle data (offset loop indices)
        ts = slice(self._t_offset, self._t_offset + tc)
        self.tri_loops[ts] = s.tri_loops + np.int32(self._v_offset)
        self.tri_mat_id[ts] = s.tri_mat_id

        self._v_offset += lc
        self._t_offset += tc


def build_indexed_triangle_set(ctx: ExportContext, entry: ShapeEntry) -> BuiltITS | None:
    """Build an IndexedTriangleSet from shape entry contributors."""
    if not entry.contributors:
        return None

    # Start with SLOT_INDEX for NORMAL shapes (supports per-instance material overrides).
    # Other modes use MATERIAL_ID directly (merged geometry with different slot layouts).
    material_kind = MaterialKeyKind.SLOT_INDEX if entry.mode == ShapeMode.NORMAL else MaterialKeyKind.MATERIAL_ID

    # Extract mesh data from all contributors
    streams = [
        s
        for contrib in entry.contributors
        if (
            s := extract_contrib_its(
                ctx,
                contrib,
                want_g=entry.want_generic_value01,
                want_bi=entry.want_bind_index,
                want_skin=entry.want_skin_weights,
                material_kind=material_kind,
            )
        )
        is not None
    ]
    if not streams:
        ctx.reporter("build_its").warning("No valid contributors for IndexedTriangleSet shape %r", entry.name)
        return None

    # If any contributor cannot defer material resolution (e.g. Geometry Nodes materials),
    # switch to MATERIAL_ID mode since those contributors already resolved materials immediately.
    if material_kind == MaterialKeyKind.SLOT_INDEX and any(s.cannot_defer_material_resolution for s in streams):
        ctx.reporter("build_its").debug(
            "Shape %r requires immediate material resolution; using MATERIAL_ID mode", entry.name
        )
        material_kind = MaterialKeyKind.MATERIAL_ID

    # Ensure generic attribute is enabled if detected in any stream (when NORMAL shape have e.g. Geometry Nodes)
    if entry.mode == ShapeMode.NORMAL and any(s.generic is not None for s in streams):
        entry.enable_generic_value01()

    total_verts = sum(s.loop_count for s in streams)
    total_tris = sum(s.tri_loops.shape[0] for s in streams)
    if total_verts <= 0 or total_tris <= 0:
        return None

    # Merge all streams into unified arrays
    merged = _MergedArrays(
        total_verts=total_verts,
        total_tris=total_tris,
        max_uvs=min(max((len(s.uvs) for s in streams), default=0), 4),
        want_color=any(s.color is not None for s in streams),
        want_g=entry.want_generic_value01,
        want_bi=entry.want_bind_index,
        want_skin=entry.want_skin_weights,
    )
    for s in streams:
        merged.add_stream(s)

    # Build indices grouped by material
    indices, subsets = build_indices_and_subsets(merged.tri_loops, merged.tri_mat_id, total_verts)
    if indices.size == 0 or indices.size % 3 != 0:
        return None

    # Deduplicate vertices to reduce file size and memory usage
    positions, normals, uvs, color, g, bi, bw, bi4, indices = _deduplicate_vertices(
        merged.positions,
        merged.normals,
        merged.uvs,
        merged.color,
        merged.g,
        merged.bi,
        merged.bw,
        merged.bi4,
        indices,
    )

    # Update subset vertex ranges after deduplication
    for subset in subsets:
        subset.num_vertices = positions.shape[0]

    # Resolve material slot names on subsets
    _resolve_subset_slot_names(ctx, entry, subsets, material_kind)

    return BuiltITS(
        name=entry.name,
        shape_id=entry.id,
        material_kind=material_kind,
        positions=positions,
        normals=normals,
        indices=indices,
        subsets=subsets,
        uvs=uvs,
        color=color,
        g=g,
        bi=bi,
        bw=bw,
        bi4=bi4,
        attrs=entry.attrs,
    )


def _deduplicate_vertices(
    positions: np.ndarray,
    normals: np.ndarray,
    uvs: list[np.ndarray],
    color: np.ndarray | None,
    g: np.ndarray | None,
    bi: np.ndarray | None,
    bw: np.ndarray | None,
    bi4: np.ndarray | None,
    indices: np.ndarray,
) -> tuple[
    np.ndarray,
    np.ndarray,
    list[np.ndarray],
    np.ndarray | None,
    np.ndarray | None,
    np.ndarray | None,
    np.ndarray | None,
    np.ndarray | None,
    np.ndarray,
]:
    """
    Deduplicate vertices by welding identical attribute combinations.

    Creates a structured array containing all vertex attributes, uses np.unique()
    to find unique vertices, and remaps triangle indices accordingly.

    Returns deduplicated (positions, normals, uvs, color, g, bi, bw, bi4, indices).
    """
    vcount = positions.shape[0]

    # Build dtype for vertex comparison
    dtype_fields = [
        ("position", "(3,)f4"),
        ("normal", "(3,)f4"),
    ]
    for i in range(len(uvs)):
        dtype_fields.append((f"uv{i}", "(2,)f4"))
    if color is not None:
        dtype_fields.append(("color", "(4,)f4"))
    if g is not None:
        dtype_fields.append(("g", "f4"))
    if bi is not None:
        dtype_fields.append(("bi", "i4"))
    if bw is not None and bi4 is not None:
        dtype_fields.append(("bw", "(4,)f4"))
        dtype_fields.append(("bi4", "(4,)i4"))

    vertex_dtype = np.dtype(dtype_fields)

    # Pack all vertex attributes into structured array
    packed = np.empty(vcount, dtype=vertex_dtype)
    packed["position"] = positions
    packed["normal"] = normals
    for i, uv in enumerate(uvs):
        packed[f"uv{i}"] = uv
    if color is not None:
        packed["color"] = color
    if g is not None:
        packed["g"] = g
    if bi is not None:
        packed["bi"] = bi
    if bw is not None and bi4 is not None:
        packed["bw"] = bw
        packed["bi4"] = bi4

    # Find unique vertices and inverse mapping
    unique_verts, inverse_indices = np.unique(packed, return_inverse=True)

    # Remap triangle indices
    new_indices = inverse_indices[indices]

    # Unpack deduplicated attributes
    new_positions = unique_verts["position"]
    new_normals = unique_verts["normal"]
    new_uvs = [unique_verts[f"uv{i}"] for i in range(len(uvs))]
    new_color = unique_verts["color"] if color is not None else None
    new_g = unique_verts["g"] if g is not None else None
    new_bi = unique_verts["bi"] if bi is not None else None
    new_bw = unique_verts["bw"] if bw is not None and bi4 is not None else None
    new_bi4 = unique_verts["bi4"] if bw is not None and bi4 is not None else None

    return new_positions, new_normals, new_uvs, new_color, new_g, new_bi, new_bw, new_bi4, new_indices


def _resolve_subset_slot_names(
    ctx: ExportContext, entry: ShapeEntry, subsets: list[BuiltSubset], material_kind: MaterialKeyKind
) -> None:
    """Set material_slot_name on each subset based on material resolution mode."""
    if material_kind == MaterialKeyKind.MATERIAL_ID:
        for subset in subsets:
            try:
                subset.material_slot_name = ctx.materials.get_entry(subset.material_id).get_slot_name()
            except KeyError:
                subset.material_slot_name = None
    else:
        signature = entry.key.slot_name_signature or ()
        for subset in subsets:
            i = subset.material_id
            subset.material_slot_name = signature[i] if 0 <= i < len(signature) else None
