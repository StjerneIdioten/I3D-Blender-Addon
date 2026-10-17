"""Verify that a committed Blender 4.5 scene can be loaded by the fixture helper."""

import bpy


def test_saved_blend_fixture(load_blend):
    scene = load_blend("basic_scene.blend")
    obj = scene.objects.get("FixtureRoot")

    assert obj is not None
    assert obj.type == "EMPTY"
    assert tuple(obj.location) == (1.0, 2.0, 3.0)
    assert bpy.ops.export_scene.i3d.get_rna_type()
