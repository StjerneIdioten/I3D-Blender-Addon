"""
This module contains various small utility functions, that don't really belong anywhere else
"""

from __future__ import annotations

import math
import os
import re
from numbers import Real
from pathlib import Path
from typing import Any

import bpy
import mathutils
from idprop.types import IDPropertyArray

BlenderObject = bpy.types.Object | bpy.types.Collection

FLOAT_EXPORT_TOLERANCE = 1e-6
_EXPORT_SEQUENCE_TYPES = (
    tuple,
    list,
    mathutils.Vector,
    mathutils.Color,
    mathutils.Euler,
    mathutils.Quaternion,
    bpy.types.bpy_prop_array,
    IDPropertyArray,
)


def _is_number(value: object) -> bool:
    """Return True for real numeric values, but not bools."""
    return isinstance(value, Real) and not isinstance(value, bool)  # bool is a subclass of int


def _as_export_tuple(value: object) -> tuple[Any, ...] | None:
    """Convert supported export sequences to tuples for componentwise comparison."""
    if isinstance(value, _EXPORT_SEQUENCE_TYPES):
        return tuple(value)
    return None


def _isclose_item(a: object, b: object, *, abs_tol: float = FLOAT_EXPORT_TOLERANCE, rel_tol: float = 0.0) -> bool:
    a_is_number = _is_number(a)
    b_is_number = _is_number(b)
    if a_is_number and b_is_number:
        return math.isclose(float(a), float(b), abs_tol=abs_tol, rel_tol=rel_tol)
    if a_is_number or b_is_number:
        return False  # One is a number and the other isn't
    return a == b  # Fallback to equality for non-numeric items


def isclose_value(a: object, b: object, *, abs_tol: float = FLOAT_EXPORT_TOLERANCE, rel_tol: float = 0.0) -> bool:
    """Compare export/default values using a target-format-friendly tolerance.
    Intended for default-value/export checks, not geometric distance checks.
    Rules:
    - Numeric values are compared with math.isclose().
    - Supported vector-like values are compared componentwise.
    - Non-numeric values fall back to normal equality.
    """
    a_seq = _as_export_tuple(a)
    b_seq = _as_export_tuple(b)
    if a_seq is None and b_seq is None:
        return _isclose_item(a, b, abs_tol=abs_tol, rel_tol=rel_tol)

    if a_seq is None or b_seq is None:
        return False  # One is a sequence and the other isn't

    if len(a_seq) != len(b_seq):
        return False  # Sequences of different lengths are not close

    return all(_isclose_item(x, y, abs_tol=abs_tol, rel_tol=rel_tol) for x, y in zip(a_seq, b_seq))


def ext_user_dir(subpath: str = "", create: bool = True) -> Path:
    """
    Returns the extension's per-user writable directory (or a subdir).
    Creates missing directories when create=True.
    """
    return Path(bpy.utils.extension_path_user(__package__, path=subpath, create=create))


def normalize_path_separators(filepath: str | Path) -> str:
    """Normalizes slashes for export-style path checks."""
    return str(filepath).replace("\\", "/")


def is_fs_builtin_path(filepath: str | Path) -> bool:
    """
    Returns True if the path uses the Farming Simulator '$data' prefix.
    This only checks path syntax. It does not check whether the file exists.
    """
    path_str = normalize_path_separators(filepath)
    return path_str == "$data" or path_str.startswith("$data/")


def fs_builtin_to_disk_path(filepath: str | Path) -> Path | None:
    """
    Converts a '$data/...' path to a real disk path using the configured FS data path.
    Returns None if the supplied path is not a '$data' path or if the FS data path is not configured.
    """
    if not is_fs_builtin_path(filepath):
        return None
    if not (fs_data_path := get_fs_data_path()):
        return None
    relative_path = normalize_path_separators(filepath).removeprefix("$data").lstrip("/")
    return Path(bpy.path.abspath(fs_data_path)).resolve(strict=False) / relative_path


def as_source_path(filepath: str | Path) -> Path | None:
    """
    Resolves a Blender/user path to the actual disk path used for validation/copying.
    - '$data/...' paths are resolved through the configured FS data path.
    - Blender relative paths like '//textures/foo.dds' are resolved with bpy.path.abspath.
    - Absolute paths stay absolute.

    Returns None if the source cannot be resolved, e.g. '$data' path but no FS data path is configured.
    """
    if is_fs_builtin_path(filepath):
        return fs_builtin_to_disk_path(filepath)
    return Path(bpy.path.abspath(str(filepath))).resolve(strict=False)


def as_fs_relative_path(filepath: str | Path) -> Path:
    """
    Checks if a filepath is relative to the FS data directory

    Checks the addon settings for the FS installation path and compares that with the supplied filepath, to see if it
    originates from within that directory.

    Args:
        filepath (str | Path): The filepath to check.
    Returns:
        Path: The `$data`-replaced path if applicable, or a cleaned-up absolute path.
    """
    if is_fs_builtin_path(filepath):
        return Path(normalize_path_separators(filepath))
    # Resolve the absolute, normalized path to the FS data directory (if set)
    fs_data_pref = get_fs_data_path()
    target_path = Path(bpy.path.abspath(str(filepath))).resolve(strict=False)
    if fs_data_pref:
        fs_data_path = Path(bpy.path.abspath(str(fs_data_pref))).resolve(strict=False)
        try:  # Return $data-prefixed path if inside FS data directory
            relative_to_fs = target_path.relative_to(fs_data_path)
            return Path('$data') / relative_to_fs
        except ValueError:
            pass  # Not inside FS data directory
    return target_path


def as_export_path(filepath: str | Path) -> Path:
    """
    Resolves the export path for a file, for compatibility with Giants Editor and modding workflows.

    Priority:
      - If inside the Farming Simulator (FS) Data directory, returns a '$data/...' path.
      - If under the current .blend file's folder (or subfolders), returns a path relative to the blend file.
      - Otherwise, returns an absolute path.

    Args:
        filepath (str | Path): The path to the file, as used or stored by/in Blender.
    Returns:
        Path: The resolved path, either as a relative path (to the blend file) or an absolute path.
    """
    if is_fs_builtin_path(filepath):
        # Already $data-prefixed (can happen from certain shader textures)
        return Path(normalize_path_separators(filepath))

    # Check if inside FS data directory
    if (fs_path := as_fs_relative_path(filepath)).parts and fs_path.parts[0] == '$data':
        return fs_path

    # Try to make path relative to the .blend file
    blend_dir = Path(bpy.data.filepath).parent.resolve()
    target_path = Path(bpy.path.abspath(str(filepath))).resolve(strict=False)
    try:
        # NOTE: Path.relative_to (pathlib) does not support paths outside its base location before Python 3.12
        # https://docs.python.org/3.12/library/pathlib.html#pathlib.PurePath.relative_to
        # Blender will remain on Python 3.11 until 2026 https://vfxplatform.com/ so use os.path.relpath until then
        return Path(os.path.relpath(str(target_path), str(blend_dir)))
    except ValueError:
        return target_path  # Happens if on another drive


def sort_blender_objects_by_outliner_ordering(objects: list[BlenderObject]) -> list[BlenderObject]:
    """
    Blenders outliner does not follow a stricly lexographical ordering, but rather what is called a "natural" ordering.
    This function implements the same ordering as per:
    https://github.com/blender/blender/blob/b0e7a6db56caf6669b6fade1622710d70b96483e/source/blender/blenlib/intern/string.c#L727
    with the use of a regex as detailed in this answer on stackoverflow https://stackoverflow.com/a/16090640
    """
    _split_num = re.compile(r'(\d+)')
    return sorted(objects, key=lambda s: [int(t) if t.isdigit() else t.lower() for t in _split_num.split(s.name)])


def get_fs_data_path(as_path: bool = False) -> str | Path:
    """Returns the path to the Farming Simulator data directory."""
    fs_data_path = bpy.context.preferences.addons[__package__].preferences.fs_data_path
    if as_path:
        return Path(fs_data_path)
    return fs_data_path
