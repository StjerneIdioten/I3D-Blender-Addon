# This fixes reloading, by deleting the module references and thus forcing a reload
if "bpy" in locals():
    import sys
    for module in list(sys.modules):
        if __name__ in module:
            del sys.modules[module]

from . import ui

import bpy

def register():
    ui.helper_functions.register()
    ui.addon_preferences.register()
    ui.udim_picker.register()
    ui.shader_parser.register()
    ui.material_templates.register()
    ui.shader_picker.register()
    ui.udim_to_mat_template.register()
    ui.exporter.register()
    ui.dds_exporter.register()
    ui.collision_data.register()
    ui.bit_mask_editor.register()
    ui.presets.register()
    ui.object.register()
    ui.user_attributes.register()
    ui.mesh.register()
    ui.light.register()
    bpy.types.TOPBAR_MT_file_export.append(ui.exporter.menu_func_export)


def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(ui.exporter.menu_func_export)
    ui.exporter.unregister()
    ui.dds_exporter.unregister()
    ui.user_attributes.unregister()
    ui.bit_mask_editor.unregister()
    ui.presets.unregister()
    ui.object.unregister()
    ui.collision_data.unregister()
    ui.mesh.unregister()
    ui.light.unregister()
    ui.udim_to_mat_template.unregister()
    ui.shader_picker.unregister()
    ui.shader_parser.unregister()
    ui.material_templates.unregister()
    ui.udim_picker.unregister()
    ui.addon_preferences.unregister()
    ui.helper_functions.unregister()
