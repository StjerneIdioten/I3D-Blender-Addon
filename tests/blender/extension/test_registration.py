"""Installed-extension registration and exposed Blender types/operators."""

import bpy


def test_extension_registration(addon):
    assert addon.__name__ in bpy.context.preferences.addons
    assert hasattr(bpy.types.Scene, "i3dio")
    assert hasattr(bpy.types.Object, "i3d_attributes")
    assert bpy.ops.export_scene.i3d.get_rna_type()
