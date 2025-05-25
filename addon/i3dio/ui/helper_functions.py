"""
This module contains various small ui helper functions.
"""
from __future__ import annotations
from pathlib import Path
import re
import bpy


classes = []


def register(cls):
    classes.append(cls)
    return cls


def i3d_property(layout, attributes, attribute: str, obj):
    i3d_map = attributes.i3d_map[attribute]
    row = layout.row()
    attrib_row = None

    # Check if this i3d attribute has a dependency on another property being a certain value
    if i3d_map.get('depends'):

        # Get list of depending values
        dependants = i3d_map['depends']

        for dependant in dependants:
            # Pre-initialize the non-tracking member
            member_value = getattr(attributes, dependant['name'])
            # Is this property dependent on a tracking member?
            tracking = getattr(attributes, dependant['name'] + '_tracking', None)
            if tracking is not None:
                # Is the tracking member currently tracking
                if tracking:
                    # Get the value of the tracked member
                    member_value = getattr(obj, attributes.i3d_map[dependant['name']]['tracking']['member_path'])
                    # If there is a mapping for it, convert the tracked value
                    mapping = attributes.i3d_map[dependant['name']]['tracking'].get('mapping')
                    icon = 'LOCKED'
                    if mapping is not None:
                        member_value = mapping[member_value]
                else:
                    icon = 'UNLOCKED'
                # else:
                #     attribute_type = 'obj'
                #     if not isinstance(obj, bpy.types.Object):
                #         attribute_type = 'data'
                #     bpy.ops.i3dio.helper_set_tracking(attribute_type='data', attribute=attribute, state=False)

            if member_value != dependant['value']:
                attrib_row = row.row()
                attrib_row.prop(attributes, attribute)
                attrib_row.enabled = False
                if getattr(attributes, attribute + '_tracking', None) is not None:
                    attrib_row.prop(attributes, attribute + '_tracking', icon=icon, icon_only=True, emboss=False)
                return

    # Is this a property, which can track one of the blender builtins?
    tracking = getattr(attributes, attribute + '_tracking', None)
    if tracking is not None:
        # If we are indeed tracking a blender builtin
        if tracking:
            row.alignment = 'RIGHT'
            # Display the name of the property
            lab = row.column()
            lab.label(text=attributes.i3d_map[attribute]['name'])
            attrib_row = row.row()
            if getattr(obj, attributes.i3d_map[attribute]['tracking']['member_path'], None) is not None:
                attrib_row.prop(obj, attributes.i3d_map[attribute]['tracking']['member_path'], text='')
                mapping = attributes.i3d_map[attribute]['tracking'].get('mapping')
                if mapping is not None:
                    attrib_row.label(text=f"'{mapping[getattr(obj, attributes.i3d_map[attribute]['tracking']['member_path'])]}' "
                                          f"in GE")

                attrib_row.label(text=f"Follows '{attributes.i3d_map[attribute]['tracking']['member_path']}")
            else:
                lab.enabled = False

            attrib_row.enabled = False
            icon = 'LOCKED'
            row.prop(attributes, attribute + '_tracking', icon=icon, icon_only=True, emboss=False)
        # If we are not tracking a blender builtin
        else:
            row.prop(attributes, attribute)  # Just display the i3d attribute then
            if getattr(obj, attributes.i3d_map[attribute]['tracking']['member_path'], None) is not None:
                icon = 'UNLOCKED'  # Show a unlocked icon to indicate this can be locked to a blender builtin
                row.prop(attributes, attribute + '_tracking', icon=icon, icon_only=True, emboss=False)

    # This is not a tracking property, so just show a normal property
    else:
        attrib_row = row.row()
        attrib_row.prop(attributes, attribute)


def humanize_template(template: str) -> str:
    """Converts a template name to a human-readable format."""
    return re.sub(r'(?<=[a-z0-9])([A-Z])', r' \1', template).title()


def detect_fs_version(path: Path) -> int | None:
    """Extracts FS version ('19', '22', '25') from the path, if present."""
    return next((v for v in ("19", "22", "25") if v in path.name or v in str(path)), None)


def is_version_compatible(old_ver: str | None, current_ver: str | None) -> bool:
    """Check if the old shader version is compatible with the current version (only relevant for vehicleShader).
    Compatibility rules:
    - Version 19 and 22 are compatible with 22.
    - Version 25 is only compatible with 25.
    """
    if old_ver == current_ver:
        return True
    if current_ver == "22" and old_ver in ("19", "22"):
        return True
    return False


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
