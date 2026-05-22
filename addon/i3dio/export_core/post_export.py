from __future__ import annotations

from typing import TYPE_CHECKING

import bpy

from .dds.motion_path_array import export_motion_path_arrays

if TYPE_CHECKING:
    from .ctx import ExportContext


def run_post_export(ctx: ExportContext, *, scope_objects: list[bpy.types.Object] | None = None) -> None:
    """Optional post-export artifacts (DDS sidecars etc)."""
    if ctx.has_feature("MOTION_PATH_ARRAYS"):
        _post_motion_path_arrays(ctx, scope_objects=scope_objects)


def _post_motion_path_arrays(ctx: ExportContext, *, scope_objects: list[bpy.types.Object] | None = None) -> None:
    rep = ctx.reporter("motion_path_array")
    if not scope_objects:
        rep.warning("Motion Path Array DDS export enabled, but no objects matched the current export scope")
        return

    summary = export_motion_path_arrays(scope_objects, depsgraph=ctx.depsgraph, logger=rep)
    rep.info(
        "Motion Path Array DDS export summary: success=%d skipped=%d failed=%d",
        summary.success,
        summary.skipped,
        summary.failed,
    )
