"""Numeric comparisons used by the exporter, including Blender vector values."""

from mathutils import Vector


def test_isclose_value(addon):
    utility = addon.utility
    assert utility.isclose_value(1.0, 1.0000001)
    assert not utility.isclose_value(1.0, 1.01)
    assert utility.isclose_value(Vector((1, 2, 3)), (1, 2, 3))
    assert not utility.isclose_value((1, 2), (1, 2, 3))
    assert not utility.isclose_value(True, 1)
