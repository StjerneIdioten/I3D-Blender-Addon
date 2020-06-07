import bpy
from bpy.types import (
    Panel
)

from bpy.props import (
    PointerProperty
)

from . import properties


classes = []


def register(cls):
    classes.append(cls)
    return cls


@register
class I3D_IO_PT_object_attributes(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_label = "I3D Object Attributes"
    bl_context = 'object'

    @classmethod
    def poll(cls, context):
        return context.object is not None

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        obj = bpy.context.active_object

        layout.prop(obj.i3d_attributes, 'visibility')
        layout.prop(obj.i3d_attributes, 'clip_distance')
        layout.prop(obj.i3d_attributes, 'min_clip_distance')

@register
class I3D_IO_PT_rigid_body_attributes(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_label = 'Rigidbody'
    bl_context = 'object'
    bl_parent_id = 'I3D_IO_PT_object_attributes'

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.type == 'MESH'

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        obj = bpy.context.active_object
        row = layout.row()
        row.prop(obj.i3d_attributes, 'rigid_body_type')

        if obj.i3d_attributes.rigid_body_type != 'disabled':
            row_compound = layout.row()
            row_compound.prop(obj.i3d_attributes, 'compound')

            row_compound_child = layout.row()
            row_compound_child.prop(obj.i3d_attributes, 'compound_child')

            if obj.i3d_attributes.rigid_body_type == 'static':
                row_compound.enabled = False
                row_compound_child.enabled = False
                obj.i3d_attributes.property_unset('compound')
                obj.i3d_attributes.property_unset('compound_child')
            else:
                if obj.i3d_attributes.compound:
                    row_compound_child.enabled = False
                elif obj.i3d_attributes.compound_child:
                    row_compound.enabled = False

            row = layout.row()
            row.prop(obj.i3d_attributes, 'collision')

            row = layout.row()
            row.prop(obj.i3d_attributes, 'collision_mask')

            row = layout.row()
            row.prop(obj.i3d_attributes, 'trigger')
        else:
            # Reset all properties if rigidbody is disabled (This is easier than doing conditional export for now.
            # Since properties that are defaulted, wont get exported)
            obj.i3d_attributes.property_unset('compound')
            obj.i3d_attributes.property_unset('compound_child')
            obj.i3d_attributes.property_unset('collision')
            obj.i3d_attributes.property_unset('collision_mask')
            obj.i3d_attributes.property_unset('trigger')


@register
class I3D_IO_PT_merge_group_attributes(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_label = 'Merge Group'
    bl_context = 'object'
    bl_parent_id = 'I3D_IO_PT_object_attributes'

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.type == 'MESH'

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        obj = bpy.context.active_object

        row = layout.row()
        row.prop(obj.i3d_merge_group, 'is_root')
        if obj.i3d_merge_group.group_id is '':  # Defaults to a default initialized placeholder
            row.enabled = False

        row = layout.row()
        row.prop(obj.i3d_merge_group, 'group_id')


@register
class I3D_IO_PT_shape_attributes(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_label = "I3D Shape Attributes"
    bl_context = 'data'

    @classmethod
    def poll(cls, context):
        if context.object is not None:
            return context.object.type == 'MESH'

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        obj = bpy.context.active_object.data

        layout.prop(obj.i3d_attributes, "casts_shadows")
        layout.prop(obj.i3d_attributes, "receive_shadows")
        layout.prop(obj.i3d_attributes, "non_renderable")
        layout.prop(obj.i3d_attributes, "distance_blending")
        layout.prop(obj.i3d_attributes, "cpu_mesh")


@register
class I3D_IO_PT_light_attributes(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_label = "I3D Light Attributes"
    bl_context = 'data'

    @classmethod
    def poll(cls, context):
        if context.object is not None:
            return context.object.type == 'LIGHT'

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        obj = bpy.context.active_object.data

        layout.prop(obj.i3d_attributes, "depth_map_bias")
        layout.prop(obj.i3d_attributes, "depth_map_slope_scale_bias")


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

