"""
NOTE: reloading is handled centrally in the root add-on __init__.py by purging
cached submodules. This file should stay import-only to keep reload behavior
predictable.
"""

from . import (
    addon_preferences,
    bit_mask_editor,
    collision_data,
    dds_exporter,
    exporter,
    helper_functions,
    light,
    material_templates,
    mesh,
    object,
    presets,
    shader_parser,
    shader_picker,
    udim_picker,
    udim_to_mat_template,
    user_attributes,
)

__all__ = [
    "addon_preferences",
    "bit_mask_editor",
    "collision_data",
    "dds_exporter",
    "exporter",
    "helper_functions",
    "light",
    "material_templates",
    "mesh",
    "object",
    "presets",
    "shader_parser",
    "shader_picker",
    "udim_picker",
    "udim_to_mat_template",
    "user_attributes",
]
