"""Farming Simulator built-in path recognition and resolution."""

import bpy


def test_fs_path_resolution(addon, game_data):
    utility = addon.utility
    result = utility.fs_builtin_to_disk_path(r"$data\shaders\example.xml")
    assert result == game_data / "shaders" / "example.xml"
    assert utility.is_fs_builtin_path("$data/shaders/example.xml")
    assert not utility.is_fs_builtin_path("$database/shaders/example.xml")


def test_fs_path_requires_configured_data_directory(addon, monkeypatch):
    prefs = bpy.context.preferences.addons[addon.__package__].preferences
    monkeypatch.setattr(prefs, "fs_data_path", "")

    assert addon.utility.fs_builtin_to_disk_path("$data/shaders/example.xml") is None
