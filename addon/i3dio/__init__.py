#!/usr/bin/env python3

"""             ##### BEGIN GPL LICENSE BLOCK #####.
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
<pep8-80 compliant>
"""

if "bpy" in locals():
    import importlib
    importlib.reload(i3d_ui)
    importlib.reload(i3d_exporter)
    print("Reloaded multifiles")
else:
    from . import i3d_ui
    print("Imported multifiles")

import bpy

print(__file__)

bl_info = {
    "name": "GIANTS I3D Exporter Tools",
    "author": "GIANTS Software, Jason Oppermann - Rebuild by the community",
    "description": "GIANTS i3D Game Engine Import-Export.",
    "version": (8, 1, 1),
    "blender": (2, 80, 0),
    "location": "File > Import-Export",
    "warning": "Unofficial Version under testing",
    "support": "COMMUNITY",
    "category": "Import-Export"
}


def menu_func_export(self, context):
    self.layout.operator(i3d_ui.I3D_IO_OT_export.bl_idname, text="I3D (.i3d)")


def register():
    i3d_ui.register()
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    i3d_ui.unregister()
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
