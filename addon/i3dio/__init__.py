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

# Reimport modules when refreshing blender to show changes
if "bpy" in locals():
    import importlib
    if 'i3d_properties' in locals():
        importlib.reload(i3d_properties)
    if 'i3d_ui' in locals():
        importlib.reload(i3d_ui)
    if 'i3d_ui_attributes' in locals():
        importlib.reload(i3d_ui_attributes)
    if 'i3d_exporter' in locals():
        importlib.reload(i3d_exporter)
    print("Reloaded multifiles")
else:
    from . import i3d_ui, i3d_ui_attributes, i3d_properties
    print("Imported multifiles")

import bpy

print(__file__)

bl_info = {
    "name": "Unofficial GIANTS I3D Exporter Tools",
    "author": "StjerneIdioten, original by GIANTS Software, Jason Oppermann",
    "description": "Exports blender projects into GIANTS I3D format for use in Giants Engine based games such as "
                   "Farming Simulator",
    "version": (1, 0, 0),
    "blender": (2, 82, 0),
    "location": "File > Import-Export",
    "warning": "First Unofficial Alpha Version",
    "support": "COMMUNITY",
    "category": "Import-Export",
    "tracker_url": "https://github.com/StjerneIdioten/I3D-Blender-Addon/issues",
    "wiki_url": "https://github.com/StjerneIdioten/I3D-Blender-Addon/wiki"
}


# File -> Export item
def menu_func_export(self, context):
    self.layout.operator(i3d_ui.I3D_IO_OT_export.bl_idname, text="I3D (.i3d)")


def register():
    i3d_properties.register()
    i3d_ui_attributes.register()
    i3d_ui.register()
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    i3d_ui.unregister()
    i3d_ui_attributes.unregister()
    i3d_properties.unregister()

