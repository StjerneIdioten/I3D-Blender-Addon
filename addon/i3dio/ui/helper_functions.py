"""
This module contains various small ui helper functions.
"""
from __future__ import annotations
import bpy
from bpy.types import (
    Operator
)

from bpy.props import (EnumProperty, StringProperty, BoolProperty)

classes = []


def register(cls):
    classes.append(cls)
    return cls


# @register
# class I3D_IO_OT_helper_set_tracking(Operator):
#     bl_idname = 'i3dio.helper_set_tracking'
#     bl_label = "Set tracking attribute"
#     bl_description = "Set tracking attribute"
#     bl_options = {'INTERNAL'}
#
#     attribute_type: EnumProperty(
#         items=[
#             ('obj', 'Object', ""),
#             ('data', 'Data', "")
#         ],
#         default='obj'
#     )
#
#     attribute: StringProperty()
#     state: BoolProperty()
#
#     def execute(self, context):
#         attributes = context.object.i3d_attributes
#         if self.attribute_type == 'data':
#             attributes = context.object.data.i3d_attributes
#
#         setattr(attributes, self.attribute, self.state)
#
#         return {'FINISHED'}


def i3d_property(layout, attributes, attribute: str, obj):
    i3d_map = attributes.i3d_map[attribute]
    row = layout.row()
    attrib_row = None

    # Check if this i3d attribute has a dependency on another property being a certain value
    if i3d_map.get('depends'):
        # Pre-initialize the non-tracking member
        member_value = getattr(attributes, i3d_map['depends']['name'])
        # Is this property dependent on a tracking member?
        tracking = getattr(attributes, i3d_map['depends']['name'] + '_tracking', None)
        if tracking is not None:
            # Is the tracking member currently tracking
            if tracking:
                # Get the value of the tracked member
                member_value = getattr(obj, attributes.i3d_map[i3d_map['depends']['name']]['tracking']['member_path'])
                # If there is a mapping for it, convert the tracked value
                mapping = attributes.i3d_map[i3d_map['depends']['name']]['tracking'].get('mapping')
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

        if member_value != i3d_map['depends']['value']:
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
            lab.label(text=attributes.__annotations__[attribute][1]['name'])
            attrib_row = row.row()
            if getattr(obj, attributes.i3d_map[attribute]['tracking']['member_path'], False):
                attrib_row.prop(obj, attributes.i3d_map[attribute]['tracking']['member_path'], text='')
                mapping = attributes.i3d_map[attribute]['tracking'].get('mapping')
                if mapping is not None:
                    attrib_row.label(text=f"'{mapping[getattr(obj, attributes.i3d_map[attribute]['tracking']['member_path'])]}' "
                                          f"in GE")

                attrib_row.label(text=f"Follows '{attributes.__annotations__[attribute+'_tracking'][1]['name']}'")
            else:
                lab.enabled = False

            attrib_row.enabled = False
            icon = 'LOCKED'
            row.prop(attributes, attribute + '_tracking', icon=icon, icon_only=True, emboss=False)
        # If we are not tracking a blender builtin
        else:
            row.prop(attributes, attribute)  # Just display the i3d attribute then
            if getattr(obj, attributes.i3d_map[attribute]['tracking']['member_path'], False):
                icon = 'UNLOCKED'  # Show a unlocked icon to indicate this can be locked to a blender builtin
                row.prop(attributes, attribute + '_tracking', icon=icon, icon_only=True, emboss=False)

    # This is not a tracking property, so just show a normal property
    else:
        attrib_row = row.row()
        attrib_row.prop(attributes, attribute)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)