from __future__ import annotations
from typing import Union
import logging
import math
import mathutils
import bpy

logger = logging.getLogger(__name__)

BlenderObject = Union[bpy.types.Object, bpy.types.Collection]


def vector_compare(a: mathutils.Vector, b: mathutils.Vector, epsilon=0.0000001) -> bool:
    if len(a) != len(b) or not isinstance(a, mathutils.Vector) or not isinstance(b, mathutils.Vector):
        raise TypeError("Both arguments must be vectors of equal length!")

    for idx in range(0, len(a)):
        if not math.isclose(a[idx], b[idx], abs_tol=epsilon):
            return False

    return True


def as_fs_relative_path(filepath: str):
    """If the filepath is relative to the fs dir, then return it with $ referring to the fs data dir
    else return the path"""
    relative_filter = 'Farming Simulator 19'
    try:
        return '$' + filepath[filepath.index(relative_filter) + len(relative_filter) + 1: len(filepath)]
    except ValueError:
        return filepath


