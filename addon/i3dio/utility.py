"""
This module contains various small utility functions, that don't really belong anywhere else
"""
from __future__ import annotations
from typing import Union, List
import logging
import math
import mathutils
import bpy
from pathlib import Path
import re

logger = logging.getLogger(__name__)

BlenderObject = Union[bpy.types.Object, bpy.types.Collection]


def vector_compare(a: mathutils.Vector, b: mathutils.Vector, epsilon: float = 0.0000001) -> bool:
    """Compares two vectors elementwise, to see if they are equal

    The function will run through the elements of vector a and compare them with vector b elementwise. If the function
    reaches a set of values not within epsilon, it will return immediately.

    Args:
        a: The first vector
        b: The second vector
        epsilon: The absolute tolerance to which the elements should be within

    Returns:
        True if the vectors are elementwise equal to the precision of epsilon

    Raises:
        TypeError: If the vectors aren't vectors with equal length
    """
    if len(a) != len(b) or not isinstance(a, mathutils.Vector) or not isinstance(b, mathutils.Vector):
        raise TypeError("Both arguments must be vectors of equal length!")

    for idx in range(0, len(a)):
        if not math.isclose(a[idx], b[idx], abs_tol=epsilon):
            return False

    return True


def as_fs_relative_path(filepath: str) -> str:
    """
    Checks if a filepath is relative to the FS data directory

    Checks the addon settings for the FS installation path and compares that with the supplied filepath, to see if it
    originates from within that directory.

    Args:
        filepath (str): The filepath to check.

    Returns:
        str: The `$data`-replaced filepath if applicable, or a cleaned-up absolute path.
    """
    # Resolve the absolute, normalized path to the FS data directory (if set)
    fs_data_pref = get_fs_data_path()
    target_path = Path(bpy.path.abspath(filepath)).resolve(strict=False)
    if fs_data_pref:
        fs_data_path = Path(bpy.path.abspath(fs_data_pref)).resolve(strict=False)
        try:  # Return $data-prefixed path if inside FS data directory
            relative_to_fs = target_path.relative_to(fs_data_path)
            return (Path('$data') / relative_to_fs).as_posix()
        except ValueError:
            pass  # Not inside FS data directory
    return target_path.as_posix()


def as_export_path(filepath: str) -> str:
    """
    Resolves the export path for a file, for compatibility with Giants Editor and modding workflows.

    Priority:
      - If inside the Farming Simulator (FS) Data directory, returns a '$data/...' path.
      - If under the current .blend file's folder (or subfolders), returns a path relative to the blend file.
      - Otherwise, returns an absolute path.

    Args:
        filepath (str): The path to the file, as used or stored by/in Blender.

    Returns:
        str: The resolved export path (either $data-relative, relative to blend file, or absolute).
    """
    if filepath.startswith('$data'):
        # If the path already starts with $data, return it as is (can happen from certain shader textures)
        return filepath
    fs_path = as_fs_relative_path(filepath)
    if fs_path.startswith('$data'):
        return fs_path
    # If under blend file directory, use blend-relative path
    blend_dir = Path(bpy.data.filepath).parent.resolve()
    target_path = Path(bpy.path.abspath(filepath)).resolve(strict=False)
    try:
        rel = target_path.relative_to(blend_dir)
        return rel.as_posix()  # Relative to blend file directory
    except ValueError:
        pass  # Not inside blend file directory
    return target_path.as_posix()  # Absolute path, as a last resort


def sort_blender_objects_by_name(objects: List[BlenderObject]) -> List[BlenderObject]:
    return sorted(objects, key=lambda x: x.name)


"""
Blenders outliner does not follow a stricly lexographical ordering, but rather what is called a "natural" ordering.
This function implements the same ordering as per:
https://github.com/blender/blender/blob/b0e7a6db56caf6669b6fade1622710d70b96483e/source/blender/blenlib/intern/string.c#L727,
with the use of a regex as detailed in this answer on stackoverflow https://stackoverflow.com/a/16090640
"""


def sort_blender_objects_by_outliner_ordering(objects: List[BlenderObject]) -> List[BlenderObject]:
    return sorted(objects, key=lambda s: [int(t) if t.isdigit() else t.lower() for t in re.split('(\d+)', s.name)])


def get_fs_data_path(as_path: bool = False) -> str | Path:
    """Returns the path to the Farming Simulator data directory."""
    fs_data_path = bpy.context.preferences.addons[__package__].preferences.fs_data_path
    if as_path:
        return Path(fs_data_path)
    return fs_data_path
