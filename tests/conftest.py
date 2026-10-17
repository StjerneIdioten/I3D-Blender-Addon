"""Fixtures shared by tests running inside Blender."""

import importlib
from pathlib import Path

import bpy
import pytest

EXTENSION_MODULE = "bl_ext.user_default.i3dio"
FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def addon():
    """Enable and import the installed extension, using its real namespace."""
    bpy.ops.preferences.addon_enable(module=EXTENSION_MODULE)
    assert EXTENSION_MODULE in bpy.context.preferences.addons, f"Extension not enabled: {EXTENSION_MODULE}"
    return importlib.import_module(EXTENSION_MODULE)


@pytest.fixture
def empty_scene(addon):
    """Remove startup objects; avoid resetting preferences/extension registration."""
    for obj in tuple(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    yield bpy.context.scene
    for obj in tuple(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)


@pytest.fixture
def game_data(addon, tmp_path):
    """Supply a fake FS data directory without requiring game installation."""
    data_path = tmp_path / "data"
    data_path.mkdir()
    prefs = bpy.context.preferences.addons[addon.__name__].preferences
    previous_path = prefs.fs_data_path
    prefs.fs_data_path = str(data_path)
    try:
        yield data_path
    finally:
        prefs.fs_data_path = previous_path


@pytest.fixture
def load_blend(addon):
    """Open a committed .blend fixture by file name, for future integration tests."""

    def load(name: str):
        filepath = FIXTURES / name
        if not filepath.is_file():
            raise FileNotFoundError(filepath)
        bpy.ops.wm.open_mainfile(filepath=str(filepath), load_ui=False)
        return bpy.context.scene

    return load
