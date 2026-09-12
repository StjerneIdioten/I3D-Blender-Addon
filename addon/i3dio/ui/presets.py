from pathlib import PurePath
from typing import TYPE_CHECKING

import bpy
from bl_ui.utils import PresetPanel as BlenderPresetPanel

from .. import __file__ as base_file_path

if TYPE_CHECKING:
    from ..i3d_attributes.schema import I3DSchema

PRESETS_PATH = PurePath(base_file_path).parent


def schema_preset_values(attributes_path: str, schema: 'I3DSchema') -> list[str]:
    """Save exported properties together with their choice of value source."""
    paths = []
    for name, definition in schema.exported():
        paths.append(f"{attributes_path}.{name}")
        if definition.tracking is not None:
            paths.append(f"{attributes_path}.{name}_tracking")
    return paths


class PresetPanel(BlenderPresetPanel):
    # Same fix as https://projects.blender.org/blender/blender/commit/4f15c247052b6db49b5226b6c473bdb7b2be6293
    # because python registered properties, don't trigger redraws
    def __del__(self):
        # Sometimes context.area is null when this destructor is called
        if bpy.context.area:
            bpy.context.area.tag_redraw()


def PresetSubdir():  # noqa: N802
    return PurePath('i3dio')


def register():
    bpy.utils.register_preset_path(PRESETS_PATH)


def unregister():
    bpy.utils.unregister_preset_path(PRESETS_PATH)
