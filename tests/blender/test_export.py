"""Export a minimal real scene and inspect the raw I3D XML."""

import xml.etree.ElementTree as ET

import bpy


def test_empty_object_raw_i3d_export(addon, empty_scene, game_data, tmp_path):
    obj = bpy.data.objects.new("SmokeTestRoot", None)
    empty_scene.collection.objects.link(obj)

    output = tmp_path / "smoke.i3d"
    bpy.ops.export_scene.i3d(
        filepath=str(output),
        selection="ALL",
        binarize_i3d=False,
        copy_files=False,
        log_to_file=False,
        verbose_output=False,
    )

    assert output.is_file(), "The exporter did not produce an I3D file"
    root = ET.parse(output).getroot()
    assert root.tag == "i3D"
    scene = root.find("Scene")
    assert scene is not None
    assert any(element.get("name") == "SmokeTestRoot" for element in scene.iter())
