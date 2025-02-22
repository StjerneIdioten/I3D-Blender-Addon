import bpy
from bl_operators.presets import AddPresetBase as BlenderAddPresetBase
from bl_ui.utils import PresetPanel as BlenderPresetPanel
from pathlib import PurePath
from .. import __package__ as base_package
from .. import __file__ as base_file_path
PRESETS_PATH = PurePath(base_file_path).parent

class PresetPanel(BlenderPresetPanel):
    # Same fix as https://projects.blender.org/blender/blender/commit/4f15c247052b6db49b5226b6c473bdb7b2be6293 because python registered properties,
    # don't trigger redraws
    def __del__(self):
        # Sometimes context.area is null when this destructor is called 
        if bpy.context.area:
            bpy.context.area.tag_redraw()

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

def PresetSubdir():
    return PurePath('i3dio')

def register():
    bpy.utils.register_preset_path(PRESETS_PATH)

def unregister():
    bpy.utils.unregister_preset_path(PRESETS_PATH)
