# i3dio/export_core/geometry/mesh/material_resolve.py
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import bpy
import numpy as np

if TYPE_CHECKING:
    from ...ctx import ExportContext


@dataclass(slots=True)
class SlotResolve:
    slot_ids: np.ndarray  # (S,) int32
    slot_has_mat: np.ndarray  # (S,) bool
    fallback_id: int | None


@dataclass(slots=True)
class MaterialSource:
    """Result of determining which materials to use for export."""

    materials: list[bpy.types.Material | None]
    needs_immediate_resolve: bool  # True if materials differ from original object


def get_materials_for_export(
    obj: bpy.types.Object,
    ev_obj: bpy.types.Object,
    mesh: bpy.types.Mesh,
    max_material_index: int,
) -> MaterialSource:
    """Determine which materials to use and whether they differ from original.

    Args:
        obj: Original Blender object
        ev_obj: Evaluated object (includes Geometry Nodes results)
        mesh: Evaluated mesh from to_mesh()
        max_material_index: Highest material index referenced by triangles

    Returns:
        MaterialSource with materials list and whether immediate resolution is needed.

    Why this matters:
        finalize_shape_material_ids uses the ORIGINAL object's material_slots.
        If Geometry Nodes added/changed materials, those only exist on the
        evaluated object. We detect this and force immediate resolution.
    """
    # Original object's materials (what finalize_shape_material_ids will see)
    orig_mats = [s.material for s in obj.material_slots] if obj.material_slots else []

    # Evaluated object's materials (includes Geometry Nodes results)
    eval_mats = [s.material for s in ev_obj.material_slots] if ev_obj.material_slots else []

    # Mesh materials (fallback, e.g. for curves converted to mesh)
    mesh_mats = list(mesh.materials) if mesh.materials else []

    # Prefer evaluated slots, fall back to mesh.materials
    if eval_mats and any(m is not None for m in eval_mats):
        materials = eval_mats
    elif mesh_mats:
        materials = mesh_mats
    else:
        materials = []

    # Detect if we need immediate resolution (can't defer to finalize):
    # 1. Original has no materials but evaluated does
    # 2. Evaluated has more materials than original
    # 3. Triangle indices exceed original's slot count
    # 4. Materials at same indices are different
    orig_has_any = orig_mats and any(m is not None for m in orig_mats)
    eval_has_any = materials and any(m is not None for m in materials)

    needs_immediate = False
    if eval_has_any and not orig_has_any:
        needs_immediate = True
    elif len(materials) > len(orig_mats):
        needs_immediate = True
    elif max_material_index >= len(orig_mats):
        needs_immediate = True
    elif orig_mats and materials:
        # Check if materials at same indices differ
        for i in range(min(len(orig_mats), len(materials))):
            if orig_mats[i] is not materials[i]:
                needs_immediate = True
                break

    return MaterialSource(materials=materials, needs_immediate_resolve=needs_immediate)


def resolve_slots(ctx: ExportContext, slot_materials: list[bpy.types.Material | None]) -> SlotResolve:
    valid = [m for m in slot_materials if m is not None]
    fallback_id = None
    if not valid:
        fallback_id = ctx.materials.get_default_id()
    elif len(valid) == 1:
        fallback_id = ctx.materials.get_or_add(valid[0])
    default_id = ctx.materials.get_default_id()

    slot_ids = np.empty(len(slot_materials), dtype=np.int32)
    slot_has_mat = np.zeros(len(slot_materials), dtype=bool)

    for i, mat in enumerate(slot_materials):
        if mat is not None:
            slot_has_mat[i] = True
            slot_ids[i] = ctx.materials.get_or_add(mat)
        else:
            slot_ids[i] = fallback_id if fallback_id is not None else default_id

    return SlotResolve(slot_ids=slot_ids, slot_has_mat=slot_has_mat, fallback_id=fallback_id)
