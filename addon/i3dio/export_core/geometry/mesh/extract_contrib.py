# i3dio/export_core/geometry/mesh/extract_contrib.py
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import bpy
import numpy as np

from ...blender.evaluated_mesh import evaluated_mesh_for_export, free_evaluated_mesh
from ...resources.shapes import ShapeContributor
from .its import MaterialKeyKind
from .material_resolve import get_materials_for_export, resolve_slots

if TYPE_CHECKING:
    from ...ctx import ExportContext


@dataclass(slots=True)
class ItsContributorStream:
    """Intermediate per-mesh vertex/triangle data extracted from Blender."""

    obj_name: str
    loop_count: int

    positions: np.ndarray  # (L,3) float32
    normals: np.ndarray  # (L,3) float32
    uvs: list[np.ndarray]  # 0..4 each (L,2) float32

    color: np.ndarray | None  # (L,4) float32 RGBA (only present if extracted)

    tri_loops: np.ndarray  # (T,3) int32, loop indices
    tri_mat_id: np.ndarray  # (T,) int32, material key per tri

    # Generic value: per-loop array (from attribute or broadcast scalar) None means "not wanted/not present"
    generic: np.ndarray | None

    bind_idx: int | None

    # Skinned mesh: (L,4)
    blend_weights: np.ndarray | None = None  # (L,4) float32
    blend_indices: np.ndarray | None = None  # (L,4) int32

    # True if we cannot safely defer SLOT_INDEX material resolution to finalize.
    # In that case we force MaterialKeyKind.MATERIAL_ID immediately.
    cannot_defer_material_resolution: bool = False


def extract_contrib_its(
    ctx: ExportContext,
    contrib: ShapeContributor,
    want_g: bool,
    want_bi: bool,
    want_skin: bool,
    *,
    material_kind: MaterialKeyKind = MaterialKeyKind.SLOT_INDEX,
) -> ItsContributorStream | None:
    obj = contrib.obj
    if not isinstance(obj, bpy.types.Object):
        return None

    # Note: We don't check obj.data type here because curves-with-geometry
    # (bevel/extrusion) will evaluate to a mesh via to_mesh().

    ev_obj, mesh = evaluated_mesh_for_export(ctx, obj, reference_frame=contrib.reference_frame)

    try:
        num_loops = len(mesh.loops)
        num_triangles = len(mesh.loop_triangles)
        if num_loops == 0 or num_triangles == 0:
            return None

        len_verts = len(mesh.vertices)

        # ---- loop -> vertex positions ----
        loop_vert_idx = np.empty(num_loops, dtype=np.int32)
        mesh.loops.foreach_get("vertex_index", loop_vert_idx)

        vert_co = np.empty((len_verts, 3), dtype=np.float32)
        mesh.vertices.foreach_get("co", vert_co.ravel())
        positions = vert_co[loop_vert_idx]  # (L,3)

        # ---- loop normals ----
        normals = np.empty((num_loops, 3), dtype=np.float32)
        mesh.loops.foreach_get("normal", normals.ravel())

        # ---- uvs (0..4) ----
        uv_layers = list(mesh.uv_layers)
        if ctx.setting("alphabetic_uvs", False):
            uv_layers.sort(key=lambda ul: ul.name.casefold())
        uv_layers = uv_layers[:4]

        uvs: list[np.ndarray] = []
        for ul in uv_layers:
            uv = np.empty((num_loops, 2), dtype=np.float32)
            ul.data.foreach_get("uv", uv.ravel())
            uvs.append(uv)

        # ---- triangles as loop indices ----
        tri_loops = np.empty((num_triangles, 3), dtype=np.int32)
        mesh.loop_triangles.foreach_get("loops", tri_loops.ravel())

        # ---- triangle -> polygon -> material slot index ----
        tri_poly = np.empty(num_triangles, dtype=np.int32)
        mesh.loop_triangles.foreach_get("polygon_index", tri_poly)

        poly_mat = np.empty(len(mesh.polygons), dtype=np.int32)
        mesh.polygons.foreach_get("material_index", poly_mat)

        tri_mat_idx = poly_mat[tri_poly]  # (T,) slot indices from mesh

        # ---- Determine material source ----
        # finalize_shape_material_ids uses the ORIGINAL object's slots. If evaluated object
        # has different materials (e.g. from Geometry Nodes), we must resolve immediately.
        max_mat_idx = int(tri_mat_idx.max()) if tri_mat_idx.size > 0 else 0
        mat_source = get_materials_for_export(obj, ev_obj, mesh, max_mat_idx)

        # If materials differ from original, force MATERIAL_ID mode to resolve now.
        effective_material_kind = MaterialKeyKind.MATERIAL_ID if mat_source.needs_immediate_resolve else material_kind

        # ---- material keys per tri ----
        tri_mat_key = _resolve_tri_material_keys(
            ctx, obj, tri_mat_idx, mat_source.materials, effective_material_kind, num_triangles
        )

        # ---- vertex colors ----
        color = None
        if mesh.color_attributes:
            layer = mesh.color_attributes.active_color or mesh.color_attributes[0]
            is_point = layer.domain == "POINT"
            src_len = len_verts if is_point else num_loops
            colors_srgb = np.empty((src_len, 4), dtype=np.float32)
            layer.data.foreach_get("color_srgb", colors_srgb.ravel())
            color = colors_srgb[loop_vert_idx] if is_point else colors_srgb

        # ---- generic value (attribute auto-detect OR scalar from contributor) ----
        generic = _extract_generic(
            mesh, num_loops, len_verts, loop_vert_idx, want_g=want_g, scalar_fallback=contrib.generic_value01
        )

        # ---- Merge Group bind idx ----
        bind_idx = int(contrib.bind_index or 0) if want_bi else None

        # ---- skin weights (optional) ----
        blend_weights = None
        blend_indices = None
        if want_skin:
            if vmap := contrib.skin_vgroup_to_bind_index or {}:
                blend_weights, blend_indices = _extract_skin_weights(mesh, loop_vert_idx, vmap)

        return ItsContributorStream(
            obj_name=obj.name,
            loop_count=num_loops,
            positions=positions,
            normals=normals,
            uvs=uvs,
            color=color,
            tri_loops=tri_loops,
            tri_mat_id=tri_mat_key,
            generic=generic,
            bind_idx=bind_idx,
            blend_weights=blend_weights,
            blend_indices=blend_indices,
            cannot_defer_material_resolution=mat_source.needs_immediate_resolve,
        )

    finally:
        free_evaluated_mesh(ev_obj)


def _extract_skin_weights(
    mesh: bpy.types.Mesh, loop_vert_idx: np.ndarray, vmap: dict[int, int]
) -> tuple[np.ndarray, np.ndarray]:
    """Top-4 normalized weights per vertex, expanded to loops."""
    len_verts = len(mesh.vertices)
    bw_v = np.zeros((len_verts, 4), dtype=np.float32)
    bi_v = np.zeros((len_verts, 4), dtype=np.int32)

    for vi, v in enumerate(mesh.vertices):
        items: list[tuple[int, float]] = []
        for g in v.groups:
            bidx = vmap.get(int(g.group))
            if bidx is None:
                continue
            w = float(g.weight)
            if w > 0.0:
                items.append((int(bidx), w))

        if not items:
            continue

        # Keep highest weights, deterministic tie-break by bind index.
        items.sort(key=lambda it: (-it[1], it[0]))
        items = items[:4]

        total = sum(w for _, w in items)
        if total <= 0.0:
            continue

        inv_total = 1.0 / total
        for slot, (bidx, w) in enumerate(items):
            bi_v[vi, slot] = bidx
            bw_v[vi, slot] = w * inv_total

    return bw_v[loop_vert_idx], bi_v[loop_vert_idx]


def _resolve_tri_material_keys(
    ctx: ExportContext,
    obj: bpy.types.Object,
    tri_mat_idx: np.ndarray,
    slot_materials: list[bpy.types.Material | None],
    material_kind: MaterialKeyKind,
    num_triangles: int,
) -> np.ndarray:
    """Resolve per-triangle material keys, warning about invalid slot references."""
    # Validate slot indices and warn about issues
    valid_mask: np.ndarray | None = None
    if slot_materials:
        slot_count = len(slot_materials)
        valid_mask = (tri_mat_idx >= 0) & (tri_mat_idx < slot_count)

        if (bad := int(np.count_nonzero(~valid_mask))) > 0:
            ctx.object_reporter(obj, "materials").warning(
                "%d triangles reference out-of-bounds material slots; using fallback/default material",
                bad,
                code="materials_slot_index_out_of_bounds",
            )

        # Check for empty slots among valid indices
        slots_is_none = np.fromiter((m is None for m in slot_materials), dtype=np.bool_, count=slot_count)
        if np.any(valid_mask) and np.any(slots_is_none):
            empty_bad = int(np.count_nonzero(slots_is_none[tri_mat_idx[valid_mask]]))
            if empty_bad:
                ctx.object_reporter(obj, "materials").warning(
                    "%d triangles reference empty material slots; using fallback/default material",
                    empty_bad,
                    code="materials_slot_is_empty",
                )

    # SLOT_INDEX: keep raw slot indices (per-node materialIds mapping happens later)
    if material_kind == MaterialKeyKind.SLOT_INDEX:
        return tri_mat_idx if slot_materials else np.zeros(num_triangles, dtype=np.int32)

    # MATERIAL_ID: resolve to global IDs so different slot layouts merge correctly
    res = resolve_slots(ctx, slot_materials=slot_materials)
    fallback_id = res.fallback_id if res.fallback_id is not None else ctx.materials.get_default_id()

    if not slot_materials:
        return np.full(num_triangles, fallback_id, dtype=np.int32)

    tri_mat_key = np.empty(num_triangles, dtype=np.int32)
    valid = valid_mask if valid_mask is not None else (tri_mat_idx >= 0) & (tri_mat_idx < len(slot_materials))
    tri_mat_key[valid] = res.slot_ids[tri_mat_idx[valid]]
    tri_mat_key[~valid] = fallback_id
    return tri_mat_key


def _extract_generic(
    mesh: bpy.types.Mesh,
    num_loops: int,
    len_verts: int,
    loop_vert_idx: np.ndarray,
    *,
    want_g: bool,
    scalar_fallback: float | None,
) -> np.ndarray | None:
    """
    Extract generic value per loop.

    Priority:
    1. If mesh has a 'generic' float attribute (geometry nodes) -> use it
    2. Elif want_g and scalar_fallback is set -> broadcast scalar to all loops
    3. Else -> None (no generic channel)
    """
    # Check for geometry nodes 'generic' attribute (auto-detect)
    if (generic_attr := mesh.attributes.get("generic")) is not None and generic_attr.data_type == 'FLOAT':
        is_point = generic_attr.domain == "POINT"
        src_len = len_verts if is_point else num_loops
        values = np.empty(src_len, dtype=np.float32)
        generic_attr.data.foreach_get("value", values)
        return values[loop_vert_idx] if is_point else values

    # Fallback to scalar (MergeChildren provides this)
    if want_g and scalar_fallback is not None:
        return np.full(num_loops, scalar_fallback, dtype=np.float32)

    return None
