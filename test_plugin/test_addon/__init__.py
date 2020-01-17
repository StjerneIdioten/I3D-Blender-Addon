#!/usr/bin/env python3

if "bpy" in locals():
    import importlib
    importlib.reload(test_op)
    importlib.reload(test_panel)
    print("Reloaded multifiles")
else:
    from . import test_op, test_panel
    print("Imported multifiles")

import bpy

print(__file__)

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

bl_info = {
    "name": "Test_addon",
    "author": "StjerneIdioten",
    "description": "Simple test addon",
    "blender": (2, 80, 0),
    "location": "View3D",
    "warning": "",
    "category": "Generic"
}

classes = (test_op.TEST_ADDON_OT_center, test_panel.TEST_ADDON_PT_center)

register, unregister = bpy.utils.register_classes_factory(classes)


