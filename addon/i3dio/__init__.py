# This fixes reloading (Blender: System -> Reload Scripts) by purging cached submodules
# so importing this add-on loads fresh code without restarting Blender
if "bpy" in locals():
    import sys

    prefix = __name__ + "."
    for name in list(sys.modules):
        if name.startswith(prefix):
            del sys.modules[name]

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


def unregister():
    for module in reversed(_UI_MODULES):
        module.unregister()
