#!/usr/bin/env python3

"""
    ##### BEGIN GPL LICENSE BLOCK #####
  This program is free software; you can redistribute it and/or
  modify it under the terms of the GNU General Public License
  as published by the Free Software Foundation; either version 2
  of the License, or (at your option) any later version.
  This program is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU General Public License for more details.
  You should have received a copy of the GNU General Public License
  along with this program; if not, write to the Free Software Foundation,
  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
 ##### END GPL LICENSE BLOCK #####
"""

import bpy
from bpy.types import (
    Panel
)

from bpy.props import (
    PointerProperty
)

from . import i3d_properties


classes = []


def register(cls):
    classes.append(cls)
    return cls


@register
class I3D_IO_PT_transform_attributes(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_label = "I3D Transform Attributes"
    bl_context = 'object'

    @classmethod
    def poll(cls, context):
        return context.object is not None

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        obj = bpy.context.active_object

        layout.prop(obj.i3d_attributes.visibility, 'value_i3d')
        layout.prop(obj.i3d_attributes.clip_distance, 'value_i3d')
        layout.prop(obj.i3d_attributes.min_clip_distance, 'value_i3d')


@register
class I3D_IO_PT_rigid_body_attributes(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_label = 'Rigidbody'
    bl_context = 'object'
    bl_parent_id = 'I3D_IO_PT_transform_attributes'

    @classmethod
    def poll(cls, context):
        return context.object is not None

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        obj = bpy.context.active_object
        row = layout.row()
        row.prop(obj.i3d_attributes.rigid_body_type, 'name_i3d')

        if obj.i3d_attributes.rigid_body_type.name_i3d != 'disabled':
            row_compound = layout.row()
            row_compound.prop(obj.i3d_attributes.compound, 'value_i3d')

            row_compound_child = layout.row()
            row_compound_child.prop(obj.i3d_attributes.compound_child, 'value_i3d')

            if obj.i3d_attributes.rigid_body_type.name_i3d == 'static':
                row_compound.enabled = False
                row_compound_child.enabled = False
                obj.i3d_attributes.compound.property_unset('value_i3d')
                obj.i3d_attributes.compound_child.property_unset('value_i3d')
            else:
                if obj.i3d_attributes.compound.value_i3d:
                    row_compound_child.enabled = False
                elif obj.i3d_attributes.compound_child.value_i3d:
                    row_compound.enabled = False

            row = layout.row()
            row.prop(obj.i3d_attributes.collision, 'value_i3d')

            row = layout.row()
            row.prop(obj.i3d_attributes.collision_mask, 'value_i3d')

            row = layout.row()
            row.prop(obj.i3d_attributes.trigger, 'value_i3d')


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

        layout.prop(obj.i3d_attributes.casts_shadows, "value_i3d")
        layout.prop(obj.i3d_attributes.receive_shadows, "value_i3d")
        layout.prop(obj.i3d_attributes.non_renderable, "value_i3d")
        layout.prop(obj.i3d_attributes.distance_blending, "value_i3d")


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

        layout.prop(obj.i3d_attributes.depth_map_bias, "value_i3d")
        layout.prop(obj.i3d_attributes.depth_map_slope_scale_bias, "value_i3d")


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

