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
    PointerProperty
)


class I3DExportUIProperties(bpy.types.PropertyGroup):
    selection: EnumProperty(
        name="Export",
        description="Select which part of the scene to export",
        items=[
            ('ALL', "Everything", "Export everything from the scene master collection"),
            ('ACTIVE_COLLECTION', "Active Collection", "Export only the active collection and all its children"),
            ('SELECTED_OBJECTS', "Selected Objects", "Export only the selected objects")
        ]
    )


classes = (I3DExportUIProperties,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.i3dio = PointerProperty(type=I3DExportUIProperties)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.i3dio
