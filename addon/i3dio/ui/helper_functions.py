"""
This module contains various small ui helper functions.
"""

from __future__ import annotations

import re

from ..i3d_attributes.resolve import UNAVAILABLE, ValueReader, make_value_reader, requirements_met


def i3d_property(layout, attributes, attribute: str, obj, *, read_value: ValueReader | None = None, **prop_kwargs):
    """Draw an I3D property using its requirements and tracking settings.

    For schema properties, obj supplies tracked Blender values. Share read_value
    across a panel draw to reuse reads. Unmet requirements disable the control;
    active tracking displays a read-only native Blender field with its own tooltip.

    prop_kwargs go to the property field, not the tracking toggle. For tracked
    fields, text overrides the separate label. The returned field layout lets
    companion controls inherit the same disabled state. Legacy properties use
    the existing drawing path, ignore these options, and return None.
    """
    if (schema := getattr(type(attributes), 'i3d_schema', None)) is None:
        _legacy_i3d_property(layout, attributes, attribute, obj)
        return

    if read_value is None:
        read_value = make_value_reader(attributes, schema, owner=obj, on_error=lambda _source, _error: None)
    definition = schema[attribute]
    enabled = requirements_met(attribute, schema, read_value)
    tracking = definition.tracking
    tracked = tracking is not None and getattr(attributes, f"{attribute}_tracking")

    row = layout.row()
    row.enabled = enabled
    field = row.row()
    if enabled and tracked:
        value = read_value(attribute)
        row.alignment = 'RIGHT'
        # The native field below has no label, so show the override here instead.
        field.label(text=prop_kwargs.pop('text', attributes.bl_rna.properties[attribute].name))
        if value is UNAVAILABLE:
            field.label(text=f"Unavailable: {tracking.member_path}", icon='ERROR')
        else:
            field.prop(obj, tracking.member_path, text='', **prop_kwargs)
            if tracking.mapping is not None:
                field.label(text=f"'{value}' in GE")
            field.label(text=f"Follows '{tracking.member_path}'")
        field.enabled = False
    else:
        field.prop(attributes, attribute, **prop_kwargs)

    if tracking is not None:
        # Keep the toggle usable if tracking fails, so the custom value can be selected.
        row.prop(
            attributes, f"{attribute}_tracking", icon='LOCKED' if tracked else 'UNLOCKED', icon_only=True, emboss=False
        )
    return field


def bit_mask_property(
    layout,
    attributes,
    attribute: str,
    obj,
    *,
    read_value: ValueReader | None = None,
    used_bits: int = 32,
    layout_mode: str = 'HORIZONTAL',
    dialog_width: int = 400,
    **prop_kwargs,
):
    """Draw a schema property with a button that opens its bit-mask editor.

    Both controls are disabled when requirements fail or tracking is active.
    used_bits, layout_mode, and dialog_width configure the editor; prop_kwargs
    configure the property field. Return their shared field layout.
    """
    field = i3d_property(layout, attributes, attribute, obj, read_value=read_value, **prop_kwargs)
    op = field.operator('i3dio.bit_mask_editor', text="", icon='THREE_DOTS')
    op.target_prop = attribute
    op.used_bits = used_bits
    op.layout_mode = layout_mode
    op.dialog_width = dialog_width
    return field


def _legacy_i3d_property(layout, attributes, attribute: str, obj):
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
                    attrib_row.label(
                        text=f"'{mapping[getattr(obj, attributes.i3d_map[attribute]['tracking']['member_path'])]}' "
                        f"in GE"
                    )

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
    return re.sub(r'(?<=[a-z0-9])([A-Z])', r' \1', template.replace('_', ' ')).title()


def detect_fs_version(path_str: str) -> str | None:
    """Extracts FS version ('19', '22', '25') from the path string, if present."""
    return next((v for v in ("19", "22", "25") if v in path_str), None)


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
