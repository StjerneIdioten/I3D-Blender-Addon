import bpy
from bl_operators.presets import AddPresetBase as BlenderAddPresetBase
from bl_ui.utils import PresetPanel as BlenderPresetPanel
from pathlib import PurePath
from .. import __package__ as base_package
from .. import __file__ as base_file_path
PRESETS_PATH = PurePath(base_file_path).parent

class PresetPanel(BlenderPresetPanel):
    # In case we need to add future common behaviour
    pass

class AddPresetBase(BlenderAddPresetBase):
    # A hack because `_is_path_readonly` only considers the builtin Blender path or extension paths as read-only and not addons
    # https://github.com/blender/blender/blob/49af320b7f2190607ebb400b47ba0a1dfa0f675e/scripts/startup/bl_operators/presets.py#L225
    # Deprecate: Once the addon is converted to an extension
    def remove(self, context, filepath):
        if PRESETS_PATH in PurePath(filepath).parents:
            self.report({'WARNING'}, f"Unable to remove {base_package} default preset")
        else:
            import os
            os.remove(filepath)

def PresetSubdirFromObjectType(object_type):
    match object_type:
        case 'EMPTY':
            subdir = 'empty'
        case 'LIGHT':
            subdir = 'light'
        case 'MESH':
            subdir = 'mesh'
        case _:
            subdir = ''
    return PresetSubdirPath(subdir)

def PresetSubdirPath(subdir: str):
    return PurePath('i3dio') / subdir

def register():
    bpy.utils.register_preset_path(PRESETS_PATH)

def unregister():
    bpy.utils.unregister_preset_path(PRESETS_PATH)
