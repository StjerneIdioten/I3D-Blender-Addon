"""Check the shared isolation and export fixtures used by future Blender tests."""

import bpy
import pytest


@pytest.mark.parametrize("source", ["python", "blend"])
def test_scene_data_is_isolated(empty_scene, load_blend, source):
    assert not bpy.data.objects
    assert not bpy.data.collections
    assert not bpy.data.meshes
    assert not bpy.data.materials
    assert not bpy.data.filepath
    assert empty_scene.unit_settings.scale_length == 1.0
    assert empty_scene.frame_current == 1
    assert "i3dio_export_settings" not in empty_scene

    # Leave both programmatically created data and loaded .blend state behind.
    # Each parameter must start clean regardless of which case ran before it.
    if source == "blend":
        load_blend("export/mesh_hierarchy.blend")
    bpy.data.collections.new("LeftoverCollection")
    bpy.data.materials.new("LeftoverMaterial")
    mesh = bpy.data.meshes.new("LeftoverMesh")
    obj = bpy.data.objects.new("LeftoverObject", mesh)
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.scene.unit_settings.scale_length = 0.25
    bpy.context.scene.frame_set(42)
    bpy.context.scene["i3dio_export_settings"] = {"selection": "SELECTED_OBJECTS"}


def test_export_helper_rejects_logged_errors(addon, export_i3d, monkeypatch):
    def report_error(*args, **kwargs):
        addon.addon_logging.addon_logger.error("Simulated exporter error")
        return {"success": True, "time": 0.0}

    # An operator can finish after logging an error. The success helper must
    # reject that outcome rather than relying only on its return value.
    monkeypatch.setattr(addon.exporter, "export_blend_to_i3d", report_error)
    with pytest.raises(AssertionError, match="Simulated exporter error"):
        export_i3d()
