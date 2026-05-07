import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)
from bpy.types import Operator, Panel

ATTRIBUTE_DEFAULT_NAME = 'Attribute'


classes = []


def register(cls):
    classes.append(cls)
    return cls


@register
class I3DUserAttributeItem(bpy.types.PropertyGroup):
    def name_update(self, context):
        attrs = self.id_data.i3d_user_attributes.attribute_list
        names = {a.name for a in attrs if a.as_pointer() != self.as_pointer()}
        if (base := (self.name or ATTRIBUTE_DEFAULT_NAME).strip()) not in names:
            return
        # GE requires unique attribute names per object, so append number until it's unique
        idx = 1
        while idx < 1000:
            candidate = f"{base}.{idx:03}"
            if candidate not in names:
                self["name"] = candidate
                break
            idx += 1

    name: StringProperty(name="Name", description="Name of the user attribute", default='', update=name_update)
    type: EnumProperty(
        name='Type',
        items=[
            ('data_scriptCallback', 'scriptCallback', ''),
            ('data_string', 'string', ''),
            ('data_float', 'float', ''),
            ('data_integer', 'integer', ''),
            ('data_boolean', 'boolean', ''),
        ],
        default='data_boolean',
    )

    data_boolean: BoolProperty(default=False)
    data_integer: IntProperty(default=0, min=-200, max=200)
    data_float: FloatProperty(default=0, min=-200, max=200)
    data_string: StringProperty(default='')
    data_scriptCallback: StringProperty(default='')  # noqa: N815


@register
class I3DUserAttributes(bpy.types.PropertyGroup):
    attribute_list: CollectionProperty(type=I3DUserAttributeItem)
    active_attribute: IntProperty(name="User attribute index", default=0)


@register
class I3D_IO_UL_user_attributes(bpy.types.UIList):
    """UIList for i3d user attributes"""

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        split = layout.split(factor=0.35, align=True)
        split.prop(item, "name", text="", icon="SCRIPT", emboss=False)

        sub = split.split(factor=0.5, align=True)
        sub.prop(item, "type", text="")
        if item.type == "data_boolean":
            sub.prop(item, item.type, text=str(item.data_boolean), toggle=True)
        else:
            sub.prop(item, item.type, text="")


@register
class I3D_IO_OT_new_user_attribute(Operator):
    """Add a new user attribute to the list"""

    bl_idname = 'i3dio_user_attribute_list.new_item'
    bl_label = "Add a new user attribute"
    bl_options = {'INTERNAL', 'UNDO'}

    def execute(self, context):
        attrs = context.object.i3d_user_attributes
        attrs.attribute_list.add().name = ATTRIBUTE_DEFAULT_NAME
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
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_label = "I3D User Attributes"
    bl_context = "object"
    bl_parent_id = "I3D_IO_PT_object_attributes"

    @classmethod
    def poll(cls, context):
        return context.object is not None

    def draw(self, context):
        layout = self.layout
        attrs = context.object.i3d_user_attributes

        row = layout.row()
        row.template_list("I3D_IO_UL_user_attributes", "", attrs, "attribute_list", attrs, "active_attribute")

        column = row.column(align=True)
        column.operator(I3D_IO_OT_new_user_attribute.bl_idname, text="", icon="ADD")
        column.operator(I3D_IO_OT_delete_user_attribute.bl_idname, text="", icon="REMOVE")


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Object.i3d_user_attributes = PointerProperty(type=I3DUserAttributes)


def unregister():
    del bpy.types.Object.i3d_user_attributes

    for cls in classes:
        bpy.utils.unregister_class(cls)
