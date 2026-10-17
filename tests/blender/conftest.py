"""Fixtures shared by tests running inside Blender."""

import importlib
import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from itertools import count
from pathlib import Path

import bpy
import pytest

EXTENSION_MODULE = "bl_ext.user_default.i3dio"
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@dataclass(frozen=True)
class ExportResult:
    """Files and parsed XML produced by one call to the export helper."""

    path: Path
    root: ET.Element
    log_path: Path


@pytest.fixture(scope="session")
def addon():
    """Enable and import the installed extension, using its real namespace."""
    bpy.ops.preferences.addon_enable(module=EXTENSION_MODULE)
    assert EXTENSION_MODULE in bpy.context.preferences.addons, f"Extension not enabled: {EXTENSION_MODULE}"
    return importlib.import_module(EXTENSION_MODULE)


@pytest.fixture(autouse=True)
def blender_state(addon):
    """Reset all scene data around each test, preserving extension registration/preferences."""
    bpy.ops.wm.read_homefile(use_empty=True, use_factory_startup=True)
    try:
        yield
    finally:
        bpy.ops.wm.read_homefile(use_empty=True, use_factory_startup=True)


@pytest.fixture
def empty_scene(blender_state):
    """Return the fresh scene created for this test."""
    return bpy.context.scene


@pytest.fixture
def game_data(addon, tmp_path):
    """Configure a synthetic installation with data/ and sibling shared/ directories."""
    game_root = tmp_path / "game"
    data_path = game_root / "data"
    data_path.mkdir(parents=True)
    (game_root / "shared").mkdir()
    # addon is the imported extension root, not this test module's package.
    prefs = bpy.context.preferences.addons[addon.__package__].preferences
    previous_path = prefs.fs_data_path
    previous_converter = prefs.i3d_converter_path
    prefs.fs_data_path = str(data_path)
    prefs.i3d_converter_path = ""
    try:
        yield data_path
    finally:
        prefs.fs_data_path = previous_path
        prefs.i3d_converter_path = previous_converter


@pytest.fixture
def game_file(game_data):
    """Write original test content relative to the synthetic installation root."""
    game_root = game_data.parent.resolve()

    def write(relative_path: str | Path, content: str | bytes) -> Path:
        filepath = (game_root / relative_path).resolve()
        if not filepath.is_relative_to(game_root):
            raise ValueError("Game fixtures must stay inside the synthetic installation")
        filepath.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            filepath.write_bytes(content)
        else:
            filepath.write_text(content, encoding="utf-8")
        return filepath

    return write


@pytest.fixture
def addon_log(addon, caplog):
    """Expose addon logs to pytest even though its logger does not propagate to root."""
    logger = addon.addon_logging.addon_logger
    logger.addHandler(caplog.handler)
    try:
        yield caplog
    finally:
        logger.removeHandler(caplog.handler)


@pytest.fixture
def export_i3d(addon, game_data, addon_log, tmp_path):
    """Export the current scene to a new raw I3D file and return its XML and paths.

    Keyword arguments override operator defaults for individual tests. This helper
    is for successful exports; failure tests can call the operator directly.
    """
    sequence = count(1)

    def export(**options):
        output = tmp_path / f"export_{next(sequence)}.i3d"
        settings = {
            "selection": "ALL",
            "binarize_i3d": False,
            "copy_files": False,
            "log_to_file": True,
            "verbose_output": False,
        }
        settings.update(options)
        log_path = output.with_name(f"{output.stem}{addon.addon_logging.EXPORT_LOG_SUFFIX}")
        first_record = len(addon_log.records)
        logger = addon.addon_logging.addon_logger
        previous_level = addon.addon_logging.addon_console_handler.level
        try:
            status = bpy.ops.export_scene.i3d(filepath=str(output), **settings)
        finally:
            addon.addon_logging.addon_console_handler.setLevel(previous_level)

        errors = [
            record.getMessage()
            for record in addon_log.records[first_record:]
            if record.levelno >= logging.ERROR
            and (record.name == logger.name or record.name.startswith(f"{logger.name}."))
        ]
        assert not errors, f"Export logged errors ({log_path}):\n" + "\n".join(errors)
        assert status == {'FINISHED'}, f"Export returned {status}; see {log_path}"
        assert output.is_file(), f"The exporter did not produce {output}; see {log_path}"
        root = ET.parse(output).getroot()
        assert root.tag == "i3D", f"Unexpected root element in {output}: {root.tag}"
        assert root.find("Scene") is not None, f"No Scene element in {output}"
        return ExportResult(path=output, root=root, log_path=log_path)

    return export


@pytest.fixture
def load_blend(blender_state):
    """Open a committed .blend scene; blender_state resets it after the test."""

    def load(name: str):
        filepath = FIXTURES / name
        if not filepath.is_file():
            raise FileNotFoundError(filepath)
        bpy.ops.wm.open_mainfile(filepath=str(filepath), load_ui=False)
        return bpy.context.scene

    return load
