# This fixes reloading (Blender: System -> Reload Scripts) by purging cached submodules
# so importing this add-on loads fresh code without restarting Blender
if "_MODULES" in locals():
    import sys

    prefix = __name__ + "."
    for name in list(sys.modules):
        if name.startswith(prefix):
            del sys.modules[name]
            # Relative imports can reuse package attributes even after sys.modules is purged.
            child_name = name[len(prefix) :]
            if '.' not in child_name:
                globals().pop(child_name, None)

from . import i3d_attributes, ui

_MODULES = (
    i3d_attributes.mesh,
    i3d_attributes.light,
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
    for module in _MODULES:
        module.register()


def unregister():
    for module in reversed(_MODULES):
        module.unregister()
