from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import bpy

from .... import utility
from ...resources.files import _MODHUB_FOLDER, FileEntry

if TYPE_CHECKING:
    from ...ctx import ExportContext
    from ...reporting import Reporter


def resolve_files(ctx: "ExportContext") -> None:
    """Resolve all registered file paths and copy them if requested."""
    rep = ctx.reporter("files")
    rep.info("Finalizing %d registered files", len(ctx.files))
    for entry in ctx.files.entries():
        _resolve_entry(ctx, rep, entry)
    rep.info("File finalization complete")


def _resolve_entry(ctx: "ExportContext", rep: Reporter, entry: FileEntry) -> None:
    """Resolve a registered file path for export."""
    rep.debug("Resolving file %r of kind %r", entry.blender_path, entry.kind)

    source_path = utility.as_source_path(entry.blender_path)

    # FS builtin: $data prefix, never copied
    if source_path is None:
        rep.warning(
            (
                "Could not resolve path for %r. "
                "If this is a $data path, check that the FS data path is configured correctly."
            ),
            entry.blender_path,
        )
    elif not source_path.exists():
        rep.warning(
            "Resolved source file %r does not exist. The exported I3D may reference a missing file.", source_path
        )

    entry.resolved_path = utility.as_export_path(entry.blender_path)

    if utility.is_fs_builtin_path(entry.resolved_path):
        rep.info("Resolved as FS $data path: %r", entry.resolved_path)
        return

    if ctx.setting("copy_files", False):
        _copy_entry(ctx, rep, entry, source_path)
        return

    rep.info("Resolved filepath: %s", entry.resolved_path)
    if entry.resolved_path.is_absolute():
        rep.warning("File %r is outside the blend file folder; using absolute path in I3D.", entry.blender_path)


def _copy_entry(ctx: "ExportContext", rep: Reporter, entry: FileEntry, source_path: Path | None) -> None:
    """Copy the file to the export location if it's not an FS builtin, and update entry.resolved_path accordingly."""
    rep.info("File is not an FS builtin and will be copied")

    if source_path is None:
        rep.warning("Cannot copy %r because the source path could not be resolved", entry.blender_path)
        return

    if not source_path.exists():
        rep.warning("File %r does not exist, cannot copy", source_path)
        return

    paths = _resolve_copy_paths(ctx, rep, entry, source_path)
    if paths is None:
        return
    resolved_path, write_path_full = paths

    entry.resolved_path = resolved_path

    source_path = source_path.resolve(strict=False)
    write_path_full = write_path_full.resolve(strict=False)

    if write_path_full == source_path:
        rep.debug("Source and destination paths are the same, no need to copy")
        return

    if ctx.setting("overwrite_files", False) or not write_path_full.exists():
        write_path_full.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy(source_path, write_path_full)
        except shutil.SameFileError:
            pass  # Ignore if source and destination is the same file
        else:
            rep.info("Copied to %r", write_path_full)
    else:
        rep.debug("File already in correct path relative to i3d file and overwrite is turned off")


def _resolve_copy_paths(
    ctx: "ExportContext",
    rep: Reporter,
    entry: FileEntry,
    source_path: Path,
) -> tuple[Path, Path] | None:
    """Return:
    - resolved_path: path written to the I3D file
    - write_path_full: actual destination path on disk
    """
    i3d_folder = ctx.i3d_folder
    file_name, file_extension = _file_name_and_ext(entry.blender_path)
    export_filename = f"{file_name}{file_extension}"

    file_structure = ctx.setting("file_structure", "MODHUB")

    match file_structure:
        case "FLAT":
            rep.debug("Will be copied using the 'FLAT' hierarchy structure")
            resolved_path = Path(export_filename)

        case "MODHUB":
            rep.debug("Will be copied using the 'MODHUB' hierarchy structure")
            modhub_folder = _MODHUB_FOLDER.get(entry.kind, "")
            if not modhub_folder:
                rep.warning("No MODHUB folder registered for file kind %r. File will be copied flat.", entry.kind)

            resolved_path = Path(modhub_folder) / export_filename if modhub_folder else Path(export_filename)

        case "BLENDER":
            rep.debug("Will be copied using the 'BLENDER' hierarchy structure")

            blend_dir = Path(bpy.data.filepath).parent.resolve(strict=False)

            try:
                relative_file_path = Path(os.path.relpath(source_path, blend_dir))
            except ValueError:
                rep.debug("File is on another drive than the .blend file. Defaulting to absolute path and no copying.")
                entry.resolved_path = source_path
                return None

            blender_relative_distance_limit = 3
            parent_steps = sum(1 for part in relative_file_path.parts if part == "..")

            if parent_steps > blender_relative_distance_limit:
                rep.debug(
                    "File exists more than %d folders away from .blend file. "
                    "Defaulting to absolute path and no copying.",
                    blender_relative_distance_limit,
                )
                entry.resolved_path = source_path
                return None

            resolved_path = relative_file_path

        case _:
            rep.debug("Unknown file_structure=%r; defaulting to 'MODHUB'", file_structure)

            modhub_folder = _MODHUB_FOLDER.get(entry.kind, "")
            resolved_path = Path(modhub_folder) / export_filename if modhub_folder else Path(export_filename)

    return resolved_path, i3d_folder / resolved_path


def _file_name_and_ext(blender_path: str) -> tuple[str, str]:
    return bpy.path.display_name_from_filepath(blender_path), Path(blender_path).suffix
