# This fixes reloading (Blender: System -> Reload Scripts) by purging cached submodules
# so importing this add-on loads fresh code without restarting Blender
if "bpy" in locals():
    import sys

    prefix = __name__ + "."
    for name in list(sys.modules):
        if name.startswith(prefix):
            del sys.modules[name]

import bpy

from . import ui

_UI_MODULES = (
    ui.addon_preferences,
    ui.udim_picker,
    ui.shader_parser,
    ui.material_templates,
    ui.shader_picker,
    ui.udim_to_mat_template,
    ui.exporter,
    ui.dds_exporter,
    ui.collision_data,
    ui.bit_mask_editor,
    ui.presets,
    ui.object,
    ui.user_attributes,
    ui.mesh,
    ui.light,
)


def register():
    for module in _UI_MODULES:
        module.register()
    bpy.types.TOPBAR_MT_file_export.append(ui.exporter.menu_func_export)


def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(ui.exporter.menu_func_export)
    for module in reversed(_UI_MODULES):
        module.unregister()
