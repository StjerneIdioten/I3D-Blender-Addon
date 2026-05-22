from __future__ import annotations

import logging
import subprocess
import sys
import time
from contextlib import nullcontext
from pathlib import Path

import bpy
from addon_utils import module_bl_info
from bpy_extras.io_utils import axis_conversion

from . import debugging, xml_i3d
from .export_core.ctx import ExportContext
from .export_core.errors import ExportUserError
from .export_core.pipeline import run_export
from .export_core.reporting import report_messages_to_operator
from .utility import get_fs_data_path

logger = logging.getLogger(__name__)

BINARIZER_TIMEOUT_IN_SECONDS = 30


def export_blend_to_i3d(operator, context: bpy.types.Context, filepath: str, axis_forward, axis_up, settings) -> dict:
    export_data: dict = {}
    # Setup logging level based on verbose_output
    log_level = logging.DEBUG if operator.verbose_output else debugging.addon_console_handler_default_level
    debugging.addon_console_handler.setLevel(log_level)

    log_ctx = nullcontext()
    if operator.log_to_file:
        filename = filepath[: -len(xml_i3d.FILE_EXT)] + debugging.export_log_file_ending
        log_ctx = debugging.export_log_file(filename)

    time_start = time.time()
    ctx = None
    success = False

    try:
        with log_ctx:
            addon_version = module_bl_info(sys.modules[__package__])["version"]
            logger.info(f"Blender version is: {bpy.app.version_string}")
            logger.info(f"I3D Exporter version is: {addon_version}")
            logger.info(f"Exporting to {filepath}")

            ctx = ExportContext.create(
                is_dev=addon_version == (0, 0, 0),
                operator=operator,
                filepath=filepath,
                depsgraph=context.evaluated_depsgraph_get(),
                scene=context.scene,
                conversion_matrix=axis_conversion(to_forward=axis_forward, to_up=axis_up).to_4x4(),
                settings=settings,
            )
            ctx.addon_pref = context.preferences.addons[__package__].preferences

            # Log export settings
            logger.info("Exporter settings:")
            for setting, value in ctx.settings.items():
                logger.info(f"  {setting}: {value}")

            if not ctx.addon_pref.fs_data_path:
                ctx.reporter("Data Path").warning(
                    "FS Data folder path is not set in addon preferences. Some features may not work correctly. See: "
                    "https://stjerneidioten.github.io/I3D-Blender-Addon/installation/setup/setup.html#fs-data-folder"
                )

            run_export(ctx, context=context)

            if operator.binarize_i3d:
                _binarize_i3d(ctx)

            success = True

    except ExportUserError as e:
        logger.warning("Export aborted: %s", e)
    except Exception as e:
        logger.exception("Export crashed due to an unexpected error: %s", e)
        if ctx is not None and ctx.is_dev:
            raise  # In dev mode, re-raise the exception for debugging
    finally:
        # Always report messages if context was created
        if ctx is not None:
            report_messages_to_operator(ctx, limit=10)
        export_data["success"] = success
        export_data["time"] = time.time() - time_start
        logger.info(f"Export took {export_data['time']:.3f} seconds")
        debugging.addon_console_handler.setLevel(debugging.addon_console_handler_default_level)

    return export_data


def _binarize_i3d(ctx: ExportContext) -> None:
    """Tries to binarize the exported I3D file"""
    rep = ctx.reporter("binarizer")
    if not (converter_path := getattr(ctx.addon_pref, "i3d_converter_path", None)):
        rep.error("No i3dConverter path set in preferences. Skipping binarization.")
        return
    converter_exe_path = Path(converter_path)
    if not converter_exe_path.exists():
        rep.error(f"i3dConverter.exe path does not exist: {converter_exe_path!r}. Skipping binarization.")
        return
    if not converter_exe_path.is_file():
        rep.error(f"i3dConverter.exe path is not a file: {converter_exe_path!r}. Skipping binarization.")
        return
    if not (game_path := get_fs_data_path(as_path=True).parent):
        rep.error("No game data path set in preferences. Skipping binarization.")
        return

    rep.info(f"Starting binarization of {ctx.filepath!r}")
    try:
        conversion_result = subprocess.run(
            args=[
                str(converter_exe_path),
                "-in",
                str(ctx.filepath),
                "-out",
                str(ctx.filepath),
                "-gamePath",
                f"{game_path}/",
            ],
            timeout=BINARIZER_TIMEOUT_IN_SECONDS,
            check=False,  # inspect stdout even on non-zero exit code
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        raw = conversion_result.stdout or ""
        lines = [ln.rstrip("\r\n") for ln in raw.splitlines() if ln.strip()]

        # Some lines could be repeated multiple times, collapse them
        collapsed: list[str] = []
        last = None
        for ln in lines:
            if ln != last:
                collapsed.append(ln)
            last = ln

        _unimportant = ("render system", "driver: null", "nullconsoledevice initialized", "i3d contains non-binary")

        def _emit(line: str) -> None:
            msg = line.rstrip()
            low = msg.lower().strip()
            if any(s in low for s in _unimportant):
                return
            if low.startswith("error:"):
                rep.error(f"  {msg}", stacklevel=3)
            elif low.startswith("warning:"):
                rep.warning(f"  {msg}", stacklevel=3)
            else:
                rep.info(f"   {msg}", stacklevel=3)

        for line in collapsed:
            _emit(line)

        if conversion_result.returncode != 0:  # Non-zero exit
            rep.error("Binarization failed. See log for details.")
            return
        rep.info(f"Finished binarization of {ctx.filepath!r}")
        rep.info("Binarization completed successfully.")

    except FileNotFoundError:
        rep.exception(f"Invalid path to i3dConverter.exe: {converter_exe_path!r}")
    except subprocess.TimeoutExpired as e:
        rep.exception(f"i3dConverter.exe timed out after {BINARIZER_TIMEOUT_IN_SECONDS} seconds. Output: {e.output!r}")
    except Exception as e:
        rep.exception(f"Unexpected error while running i3dConverter.exe: {e}")
