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
from bpy.props import (
    StringProperty,
    BoolProperty,
    EnumProperty,
    PointerProperty,
    FloatProperty
)


class I3DExportUIProperties(bpy.types.PropertyGroup):
    selection: EnumProperty(
        name="Export",
        description="Select which part of the scene to export",
        items=[
            ('ALL', "Everything", "Export everything from the scene master collection"),
            ('ACTIVE_COLLECTION', "Active Collection", "Export only the active collection and all its children")
        ],
        default='ACTIVE_COLLECTION'
    )

    keep_collections_as_transformgroups: BoolProperty(
        name="Keep Collections",
        description="Keep organisational collections as transformgroups in the i3d file. If turned off collections "
                    "will be ignored and the child objects will be added to the nearest parent in the hierarchy",
        default=True
    )


class I3DNodeTransformAttributes(bpy.types.PropertyGroup):

    clip_distance: FloatProperty(
        name="Clip Distance",
        description="Anything above this distance to the camera, wont be rendered",
        default=1000000.0,
        min=0.0
    )

    min_clip_distance: FloatProperty(
        name="Min Clip Distance",
        description="Anything below this distance to the camera, wont be rendered",
        default=0.0,
        min=0.0
    )


class I3DNodeShapeAttributes(bpy.types.PropertyGroup):

    casts_shadows: BoolProperty(
        name="Cast Shadowmap",
        description="Cast Shadowmap",
        default=False
    )

    receive_shadows: BoolProperty(
        name="Receive Shadowmap",
        description="Receive Shadowmap",
        default=False
    )


class I3DNodeLightAttributes(bpy.types.PropertyGroup):

    depth_map_bias: FloatProperty(
        name="Shadow Map Bias",
        description="Shadow Map Bias",
        default=0.0012,
        min=0.0,
        max=10.0
    )

    depth_map_slope_scale_bias: FloatProperty(
        name="Shadow Map Slope Scale Bias",
        description="Shadow Map Slope Scale Bias",
        default=2.0,
        min=-10.0,
        max=10.0
    )


classes = (I3DExportUIProperties,
           I3DNodeTransformAttributes,
           I3DNodeShapeAttributes,
           I3DNodeLightAttributes
           )


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.i3dio = PointerProperty(type=I3DExportUIProperties)
    bpy.types.Object.i3d_attributes = PointerProperty(type=I3DNodeTransformAttributes)
    bpy.types.Mesh.i3d_attributes = PointerProperty(type=I3DNodeShapeAttributes)
    bpy.types.Light.i3d_attributes = PointerProperty(type=I3DNodeLightAttributes)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.i3dio
    del bpy.types.Object.i3d_attributes
    del bpy.types.Mesh.i3d_attributes
    del bpy.types.Light.i3d_attributes
