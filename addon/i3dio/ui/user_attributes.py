import bpy
from bpy.types import (
    Panel,
    Operator
)

from bpy.props import (
    StringProperty,
    BoolProperty,
    EnumProperty,
    PointerProperty,
    FloatProperty,
    IntProperty,
    CollectionProperty,
)

attribute_default_name = 'Attribute'


classes = []


def register(cls):
    classes.append(cls)
    return cls


@register
class I3DUserAttributeItem(bpy.types.PropertyGroup):

    def name_update(self, context):
        attribute_list = context.active_object.i3d_user_attributes.attribute_list

        # Maintain unique user attribute names. This implementation is very rudimentary, but it is limited how many
        # attributes people are adding and naming the same exact thing. Especially since giants does not support
        # attributes with the same name anyway (on the same object)
        if len([attribute for attribute in attribute_list if attribute.name == self.name]) > 1:
            idx = 1
            while idx < 1000:
                new_name = self.name + '.' + str(idx).zfill(3)
                if not any(attribute.name == new_name for attribute in attribute_list):
                    self['name'] = new_name
                    break
                else:
                    idx += 1

    name: StringProperty(
        name="Name",
        description="Name of the user attribute",
        default='',
        update=name_update
    )
    type: EnumProperty(name='Type',
                       items=[('data_scriptCallback', 'scriptCallback', ''),
                              ('data_string', 'string', ''),
                              ('data_float', 'float', ''),
                              ('data_integer', 'integer', ''),
                              ('data_boolean', 'boolean', '')],
                       default='data_boolean')

    data_boolean: BoolProperty(default=False)
    data_integer: IntProperty(default=0, min=-199, max=200)
    data_float: FloatProperty(default=0, min=-200, max=200)
    data_string: StringProperty(default='')
    data_scriptCallback: StringProperty(default='')


@register
class I3DUserAttributes(bpy.types.PropertyGroup):
    attribute_list: CollectionProperty(type=I3DUserAttributeItem)
    active_attribute: IntProperty(name="User attribute index", default=0)


@register
class I3D_IO_UL_user_attributes(bpy.types.UIList):
    """UIList for i3d user attributes"""

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        # Code to specify custom icon
        custom_icon = 'SCRIPT'

        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.prop(item, 'name', text='', icon=custom_icon, emboss=False, translate=False)

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text="", icon=custom_icon)


@register
class I3D_IO_OT_new_user_attribute(Operator):
    """Add a new user attribute to the list"""
    bl_idname = 'i3dio_user_attribute_list.new_item'
    bl_label = "Add a new user attribute"
    bl_options = {'INTERNAL', 'UNDO'}

    def execute(self, context):
        attrs = context.object.i3d_user_attributes
        attrs.attribute_list.add().name = attribute_default_name
        attrs.active_attribute = len(attrs.attribute_list) - 1
        return {'FINISHED'}


@register
class I3D_IO_OT_delete_user_attribute(Operator):
    """Delete the selected user attribute"""
    bl_idname = "i3dio_user_attribute_list.delete_item"
    bl_label = "Delete selected user attribute"
    bl_options = {'INTERNAL', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.object.i3d_user_attributes.attribute_list

    def execute(self, context):
        attrs = context.object.i3d_user_attributes
        attrs.attribute_list.remove(attrs.active_attribute)
        attrs.active_attribute = max(0, attrs.active_attribute - 1)
        return {'FINISHED'}


@register
class I3D_IO_PT_user_attributes(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_label = "I3D User Attributes"
    bl_context = 'object'
    bl_parent_id = 'I3D_IO_PT_object_attributes'

    @classmethod
    def poll(cls, context):
        return context.object is not None

    def draw(self, context):
        layout = self.layout
        attrs = context.object.i3d_user_attributes

        row = layout.row()
        row.template_list("I3D_IO_UL_user_attributes", "The_List", attrs, "attribute_list", attrs, 'active_attribute')

        column = row.column(align=True)
        column.operator('i3dio_user_attribute_list.new_item', text='', icon='ADD')
        column.operator('i3dio_user_attribute_list.delete_item', text='', icon='REMOVE')

        if 0 <= attrs.active_attribute < len(attrs.attribute_list):
            attr = attrs.attribute_list[attrs.active_attribute]
            row = layout.row()
            row.alignment = 'RIGHT'
            row.prop(attr, 'type')
            row.prop(attr, attr.type, text='')


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Object.i3d_user_attributes = PointerProperty(type=I3DUserAttributes)


def unregister():
    del bpy.types.Object.i3d_user_attributes

    for cls in classes:
        bpy.utils.unregister_class(cls)