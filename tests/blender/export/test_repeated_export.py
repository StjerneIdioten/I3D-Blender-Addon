"""Independent exports within a single Blender session."""

import bpy


def test_repeated_export_uses_current_scene(empty_scene, export_i3d):
    obj = bpy.data.objects.new("FirstExport", None)
    empty_scene.collection.objects.link(obj)
    first = export_i3d()

    bpy.data.objects.remove(obj, do_unlink=True)
    replacement = bpy.data.objects.new("SecondExport", None)
    empty_scene.collection.objects.link(replacement)
    second = export_i3d()

    assert first.path != second.path
    assert first.root.find("Scene/TransformGroup[@name='FirstExport']") is not None
    assert second.root.find("Scene/TransformGroup[@name='FirstExport']") is None
    assert second.root.find("Scene/TransformGroup[@name='SecondExport']") is not None
