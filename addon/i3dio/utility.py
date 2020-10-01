"""
This module contains various small utility functions, that don't really belong anywhere else
"""
from __future__ import annotations
from typing import Union, List
import logging
import math
import mathutils
import bpy
import os

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


def as_fs_relative_path(filepath: str):
    """Checks if a filepath is relative to the FS data directory

    Checks the addon settings for the FS installation path and compares that with the supplied filepath, to see if it
    originates from within that.

    Args:
        filepath: The filepath to check

    Returns:
        The $data replaced filepath, if applicable, or a cleaned up version of the supplied filepath

    Todo:
        This should check if the addon path is actually set to something

    Todo:
        This should be rewritten to use `pathlib <https://docs.python.org/3.7/library/pathlib.html>`_ instead
        of just strings
    """
    logger.debug(f"Original filepath: {filepath}")
    filepath_clean = os.path.normpath(bpy.path.abspath(filepath))  # normpath cleans up stuff such as '../'
    logger.debug(f"Cleaned filepath: {filepath_clean}")
    fs_data_path = os.path.normpath(
                        bpy.path.abspath(
                            bpy.context.preferences.addons[__package__].preferences.fs_data_path))
    logger.debug(f"FS data path: {fs_data_path}")
    try:
        if fs_data_path != '':
            path_to_return = '$data' + filepath_clean[filepath_clean.index(fs_data_path) + len(fs_data_path):]
            logger.debug(f"Fs relative path: {path_to_return}")
            return path_to_return
        else:
            raise ValueError
    except ValueError:
        return filepath_clean


def sort_blender_objects_by_name(objects: List[BlenderObject]) -> List[BlenderObject]:
    sorted_objects = list(objects)  # Create new list from whatever comes in, whether it is an existing list or a tuple
    sorted_objects.sort(key=lambda x: x.name)  # Sort by name
    return sorted_objects

