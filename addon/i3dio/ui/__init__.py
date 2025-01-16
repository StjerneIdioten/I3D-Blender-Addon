if "bpy" in locals():
    import importlib
    reloadable_modules = [
        'helper_functions',
        'addon_preferences',
        'exporter',
        'presets',
        'object',
        'mesh',
        'light',
        'shader_picker',
        'user_attributes',
        'udim_picker'
    ]

    for module_name in reloadable_modules:
        if module_name in locals():
            importlib.reload(locals()[module_name])

from . import (helper_functions, addon_preferences, exporter, presets, object, user_attributes, mesh, light,
               shader_picker, udim_picker)
