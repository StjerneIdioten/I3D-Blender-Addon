"""Raw I3D output for Blender Empty objects."""

import bpy


def test_empty_object_raw_i3d_export(empty_scene, export_i3d):
    obj = bpy.data.objects.new("SmokeTestRoot", None)
    empty_scene.collection.objects.link(obj)

    result = export_i3d()
    assert result.root.find("Scene/TransformGroup[@name='SmokeTestRoot']") is not None
    assert result.log_path.is_file()
