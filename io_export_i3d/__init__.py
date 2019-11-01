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

TODO: check current programming

<pep8-80 compliant>
"""

import bpy

print(__file__)

bl_info = {
    "name": "GIANTS I3D Exporter Tools",
    "description": "GIANTS i3D Game Engine Import-Export.",
    "author": "GIANTS Software, Jason Oppermann",
    "version": (8, 1, 1),
    "blender": (2, 80, 0),
    "location": "File > Import-Export",
    "warning": "Unofficial Version under testing",
    "wiki_url": ("https://github.com/Tallion-07/I3d-Import-Export-for-Blender-2.8.wiki.git"),
    "tracker_url": ("https://tallion-07.github.io/I3d-Import-Export-for-Blender-2.8"),
    "support": "community",
    "category": "Import-Export"}

global DCC_PLATFORM
DCC_PLATFORM = "blender"

if "bpy" in locals():
    import importlib
    importlib.reload(i3d_ui)
    importlib.reload(dcc)
else:
    from . import i3d_ui
    from . import dcc
# ------------------------------------------------------------------------------
#   I3D Menu Class
# ------------------------------------------------------------------------------


class I3D_Menu(bpy.types.Menu):
    bl_label = "GIANTS I3D"
    bl_idname = "i3d_menu"


def draw(self, context):
    layout = self.layout
    layout.label(text="v {0}".format(bl_info["version"]))
    layout.operator("i3d.menu_export")

# ------------------------------------------------------------------------------
#   I3D Menu Draw
# ------------------------------------------------------------------------------


def draw_I3D_Menu(self, context):
    self.layout.menu(I3D_Menu.bl_idname)

# ------------------------------------------------------------------------------
#   Register
# ------------------------------------------------------------------------------


def register():
    i3d_ui.register()
    bpy.utils.register_class(I3D_Menu)
    bpy.types.INFO_HT_header.append(draw_I3D_Menu)

# ------------------------------------------------------------------------------
# UnRegister
# ------------------------------------------------------------------------------


def unregister():
    i3d_ui.unregister()
    bpy.utils.unregister_class(I3D_Menu)
    bpy.types.INFO_HT_header.remove(draw_I3D_Menu)


if __name__ == "__main__":
    register()
# ------------------------------------------------------------------------------
