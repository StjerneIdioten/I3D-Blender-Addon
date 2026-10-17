"""Small, deterministic regression checks for existing exporter utilities."""

from mathutils import Vector


def test_isclose_value(addon):
    utility = addon.utility
    assert utility.isclose_value(1.0, 1.0000001)
    assert not utility.isclose_value(1.0, 1.01)
    assert utility.isclose_value(Vector((1, 2, 3)), (1, 2, 3))
    assert not utility.isclose_value((1, 2), (1, 2, 3))
    assert not utility.isclose_value(True, 1)


def test_fs_path_resolution(addon, game_data):
    utility = addon.utility
    result = utility.fs_builtin_to_disk_path(r"$data\shaders\example.xml")
    assert result == game_data / "shaders" / "example.xml"
    assert utility.is_fs_builtin_path("$data/shaders/example.xml")
    assert not utility.is_fs_builtin_path("$database/shaders/example.xml")
