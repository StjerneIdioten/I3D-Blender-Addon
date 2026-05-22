# i3dio/export_core/blender/evaluated_mesh.py
from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

import bpy
from mathutils import Matrix

if TYPE_CHECKING:
    from ..ctx import ExportContext


@contextmanager
def temporary_disable_armature_modifiers(ctx: ExportContext, objs: set[bpy.types.Object]):
    """Context manager to temporarily disable armature modifiers on the given objects."""
    changed: list[tuple[bpy.types.Modifier, bool]] = []
    try:
        for obj in objs:
            for mod in obj.modifiers:
                if mod.type == "ARMATURE":
                    changed.append((mod, mod.show_viewport))
                    mod.show_viewport = False

        # Force re-evaluation so evaluated_get/to_mesh sees the new modifier states
        ctx.depsgraph.update()
        yield
    finally:
        for mod, old in changed:
            try:
                mod.show_viewport = old
            except Exception:
                pass
        ctx.depsgraph.update()


def evaluated_mesh_for_export(
    ctx: ExportContext, obj: bpy.types.Object, *, reference_frame: Matrix | None = None
) -> tuple[bpy.types.Object, bpy.types.Mesh]:
    """
    Create a temporary mesh for export:
    - optionally evaluated (modifiers)
    - optionally moved into a reference_frame
    - converted to export axis space
    - optionally scaled by ctx.unit_scale (to match node translation scaling)
    """
    setting = ctx.setting
    rep = ctx.object_reporter(obj, "evaluated_mesh")

    if setting("apply_modifiers", True):
        ev_obj = obj.evaluated_get(ctx.depsgraph)
        mesh = ev_obj.to_mesh(preserve_all_data_layers=False, depsgraph=ctx.depsgraph)
        rep.debug("is exported with modifiers applied")
    else:
        ev_obj = obj
        mesh = ev_obj.to_mesh(preserve_all_data_layers=False)
        rep.debug("is exported without modifiers applied")

    # Optional "reference frame" placement (used for merge features)
    if reference_frame is not None:
        mesh.transform(reference_frame.inverted() @ ev_obj.matrix_world)

    # Convert to export space, and scale consistently with node translation scaling.
    conv = ctx.conversion_matrix
    if setting("apply_unit_scale", True):
        conv = Matrix.Scale(ctx.unit_scale, 4) @ ctx.conversion_matrix
    mesh.transform(conv)
    if conv.is_negative:
        mesh.flip_normals()
        rep.debug("Conversion matrix has negative scale; flipped normals")

    mesh.calc_loop_triangles()
    return ev_obj, mesh


def free_evaluated_mesh(ev_obj: bpy.types.Object) -> None:
    try:
        ev_obj.to_mesh_clear()
    except Exception:
        pass
