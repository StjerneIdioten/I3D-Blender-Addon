from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import bpy

from ... import debugging
from .motion_path_array_collect import LogSink, collect_motion_path_array
from .writer import write_dds_dx10


@dataclass(frozen=True, slots=True)
class MotionPathArrayExportSummary:
    success: int = 0
    skipped: int = 0
    failed: int = 0


def export_motion_path_array(
    obj: bpy.types.Object, *, depsgraph: bpy.types.Depsgraph, logger: LogSink | None = None
) -> tuple[str, str]:
    """Export Motion Path Array DDS for a single object.

    Returns:
        (status, message) where status is one of: SUCCESS, SKIP, FAIL.
    """
    if logger is None:
        logger = debugging.ContextAdapter(
            debugging.get_logger("export"), {"object_name": obj.name, "prefix": "motion_path_array"}
        )

    gathered_array = collect_motion_path_array(obj, depsgraph=depsgraph, logger=logger)

    name = obj.name
    filepath = obj.i3d_motion_path_array.filepath
    if gathered_array is None or not filepath:
        msg = f"[{name}] Skipped: No data or filepath."
        logger.info(msg)
        return "SKIP", msg

    if not filepath.lower().endswith(".dds"):
        filepath += ".dds"

    try:
        abs_path = bpy.path.abspath(filepath)
        Path(abs_path).parent.mkdir(parents=True, exist_ok=True)
        write_dds_dx10(abs_path, gathered_array)
        msg = f"[{name}] Exported Motion Path Array to {abs_path}"
        logger.info(msg)
        return "SUCCESS", msg
    except Exception as e:
        logger.exception("[%s] Failed to write DDS: %s", name, e)
        msg = f"[{name}] Failed to write DDS: {e}"
        return "FAIL", msg


def export_motion_path_arrays(
    objects: Iterable[bpy.types.Object], *, depsgraph: bpy.types.Depsgraph, logger: LogSink | None = None
) -> MotionPathArrayExportSummary:
    """Export Motion Path Array DDS for all enabled objects in an iterable."""
    success = skipped = failed = 0

    for obj in objects:
        if not obj.i3d_motion_path_array.enabled:
            continue

        status, _msg = export_motion_path_array(obj, depsgraph=depsgraph, logger=logger)
        if status == "SUCCESS":
            success += 1
        elif status == "FAIL":
            failed += 1
        else:
            skipped += 1

    return MotionPathArrayExportSummary(success=success, skipped=skipped, failed=failed)
