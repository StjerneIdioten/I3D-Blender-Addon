"""Synthetic game files and the extension preferences used by the test harness."""

import bpy
import pytest


def test_game_data_uses_extension_preferences(addon, game_data):
    assert addon.__package__ == addon.__name__
    prefs = bpy.context.preferences.addons[addon.__package__].preferences
    assert bpy.context.preferences.addons[addon.__package__].module == addon.__package__
    assert prefs.fs_data_path == str(game_data)
    assert prefs.i3d_converter_path == ""
    assert addon.utility.get_fs_data_path() == str(game_data)
    assert game_data.is_dir()
    assert (game_data.parent / "shared").is_dir()


def test_game_file_writes_text_and_bytes(game_data, game_file):
    xml = '<Fixture description="Original test content" />'
    data_file = game_file("data/shaders/test.xml", xml)
    shared_file = game_file("shared/nested/test.bin", b"\x00\x01\x02")

    assert data_file == game_data / "shaders" / "test.xml"
    assert data_file.read_text(encoding="utf-8") == xml
    assert shared_file == game_data.parent / "shared" / "nested" / "test.bin"
    assert shared_file.read_bytes() == b"\x00\x01\x02"


@pytest.mark.parametrize("path_kind", ["relative", "absolute"])
def test_game_file_rejects_paths_outside_installation(game_data, game_file, tmp_path, path_kind):
    outside = tmp_path / "outside.xml"
    path = "../outside.xml" if path_kind == "relative" else outside
    with pytest.raises(ValueError, match="inside the synthetic installation"):
        game_file(path, "must not be written")
    assert not outside.exists()
