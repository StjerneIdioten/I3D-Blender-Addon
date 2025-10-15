import bpy
from bl_ui.utils import PresetPanel as BlenderPresetPanel
from pathlib import PurePath
from .. import __file__ as base_file_path
PRESETS_PATH = PurePath(base_file_path).parent

class PresetPanel(BlenderPresetPanel):
    # Same fix as https://projects.blender.org/blender/blender/commit/4f15c247052b6db49b5226b6c473bdb7b2be6293
    # because python registered properties, don't trigger redraws
    def __del__(self):
        # Sometimes context.area is null when this destructor is called 
        if bpy.context.area:
            bpy.context.area.tag_redraw()

def PresetSubdir():
    return PurePath('i3dio')

def register():
    bpy.utils.register_preset_path(PRESETS_PATH)

def unregister():
    bpy.utils.unregister_preset_path(PRESETS_PATH)
