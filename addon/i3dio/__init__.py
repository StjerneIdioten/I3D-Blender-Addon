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

from . import ui, xml_i3d

import bpy

__version__ = "0.0.0"  # This version number is used internally, since the bl_info one can't handle dev versions...

bl_info = {
    "name": "Unofficial GIANTS I3D Exporter Tools",
    "author": "StjerneIdioten, original by GIANTS Software, Jason Oppermann",
    "description": "Exports blender projects into GIANTS I3D format for use in Giants Engine based games such as "
                   "Farming Simulator",
    "version": (0, 0, 0),  # Always (0, 0, 0) since versioning is controlled by the CI
    "blender": (2, 90, 0),
    "location": "File > Import-Export",
    "warning": "First Unofficial Alpha Version",
    "support": "COMMUNITY",
    "category": "Import-Export",
    "tracker_url": "https://github.com/StjerneIdioten/I3D-Blender-Addon/issues",
    "wiki_url": "https://stjerneidioten.github.io/I3D-Blender-Addon/"
}


def register():

    try:
        import lxml
    except ImportError as e:
        print("lxml was not found")
        import os
        import ctypes
        if ctypes.windll.shell32.IsUserAnAdmin():
            print("Blender is run as administrator")
            import subprocess
            import sys
            python_exe = bpy.app.binary_path_python
            result = subprocess.run(['echo', 'yes', '|', python_exe, '-m', 'pip', 'install', '-r',
                                     f'{os.path.dirname(os.path.realpath(__file__))}\\requirements.txt'],
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, shell=True)
            try:
                import lxml
            except ImportError as e:
                raise ImportError('lxml is still not installed') from e
            else:
                print("lxml is now installed")
                # TODO: See if it is even necessary to import xml_i3d beforehand, maybe reload can be avoided
                import importlib
                importlib.reload(xml_i3d)  # We need to reload this library so it now has access to lxml
        else:
            print('You must run blender as administrator to be able to install lxml!')
    else:
        print("lxml is already installed")

    ui.addon_preferences.register()
    ui.udim_picker.register()
    ui.shader_picker.register()
    ui.exporter.register()
    ui.object.register()
    ui.user_attributes.register()
    ui.mesh.register()
    ui.light.register()

    bpy.types.TOPBAR_MT_file_export.append(ui.exporter.menu_func_export)


def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(ui.exporter.menu_func_export)
    ui.exporter.unregister()
    ui.user_attributes.unregister()
    ui.object.unregister()
    ui.mesh.unregister()
    ui.light.unregister()
    ui.shader_picker.unregister()
    ui.udim_picker.unregister()
    ui.addon_preferences.unregister()

