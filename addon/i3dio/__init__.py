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

from . import ui

import bpy

__version__ = "0.0.0"  # This version number is used internally, since the bl_info one can't handle dev versions...

bl_info = {
    "name": "Unofficial GIANTS I3D Exporter Tools",
    "author": "StjerneIdioten, original by GIANTS Software, Jason Oppermann",
    "description": "Exports blender projects into GIANTS I3D format for use in Giants Engine based games such as "
                   "Farming Simulator",
    "version": (0, 0, 0),  # Always (0, 0, 0) since versioning is controlled by the CI
    "blender": (4, 2, 0),
    "location": "File > Import-Export",
    "warning": "First Unofficial Alpha Version",
    "support": "COMMUNITY",
    "category": "Import-Export",
    "tracker_url": "https://github.com/StjerneIdioten/I3D-Blender-Addon/issues",
    "wiki_url": "https://stjerneidioten.github.io/I3D-Blender-Addon/"
}

def register():
    ui.helper_functions.register()
    ui.addon_preferences.register()
    ui.udim_picker.register()
    ui.shader_picker.register()
    ui.exporter.register()
    ui.presets.register()
    ui.object.register()
    ui.user_attributes.register()
    ui.mesh.register()
    ui.light.register()
    bpy.types.TOPBAR_MT_file_export.append(ui.exporter.menu_func_export)


def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(ui.exporter.menu_func_export)
    ui.exporter.unregister()
    ui.user_attributes.unregister()
    ui.presets.unregister()
    ui.object.unregister()
    ui.mesh.unregister()
    ui.light.unregister()
    ui.shader_picker.unregister()
    ui.udim_picker.unregister()
    ui.addon_preferences.unregister()
    ui.helper_functions.unregister()
