if "bpy" in locals():
    import importlib
    reloadable_modules = [
        'helper_functions',
        'addon_preferences',
        'exporter',
        'bit_mask_editor',
        'presets',
        'object',
        'mesh',
        'light',
        'material_templates',
        'shader_picker',
        'udim_to_mat_template',
        'user_attributes',
        'udim_picker'
    ]

    for module_name in reloadable_modules:
        if module_name in locals():
            importlib.reload(locals()[module_name])

from . import (helper_functions, addon_preferences, exporter, bit_mask_editor, object, presets, user_attributes, mesh,
               light, material_templates, shader_picker, udim_to_mat_template, udim_picker)
