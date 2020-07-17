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
"""

# This fixes reloading, by deleting the module references and thus forcing a reload
if "bpy" in locals():
    import sys
    for module in list(sys.modules):
        if __name__ in module:
            del sys.modules[module]

from . import (
    properties,
    ui_attributes,
    ui_export,
    ui_shader_picker
)

import bpy

bl_info = {
    "name": "Unofficial GIANTS I3D Exporter Tools",
    "author": "StjerneIdioten, original by GIANTS Software, Jason Oppermann",
    "description": "Exports blender projects into GIANTS I3D format for use in Giants Engine based games such as "
                   "Farming Simulator",
    "version": (1, 0, 0),
    "blender": (2, 83, 0),
    "location": "File > Import-Export",
    "warning": "First Unofficial Alpha Version",
    "support": "COMMUNITY",
    "category": "Import-Export",
    "tracker_url": "https://github.com/StjerneIdioten/I3D-Blender-Addon/issues",
    "wiki_url": "https://github.com/StjerneIdioten/I3D-Blender-Addon/wiki"
}


# File -> Export item
def menu_func_export(self, context):
    print(locals())
    self.layout.operator(ui_export.I3D_IO_OT_export.bl_idname, text="I3D (.i3d)")


def register():
    properties.register()
    ui_attributes.register()
    ui_shader_picker.register()
    ui_export.register()
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    ui_export.unregister()
    ui_shader_picker.unregister()
    ui_attributes.unregister()
    properties.unregister()

