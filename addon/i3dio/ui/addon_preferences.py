import bpy
from bpy.types import AddonPreferences
from bpy.props import (StringProperty)


class I3D_IO_AddonPreferences(AddonPreferences):
    bl_idname = 'i3dio'

    fs_data_path: StringProperty(
        name="FS Data Folder",
        subtype='DIR_PATH',
        default=""
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'fs_data_path')


def register():
    bpy.utils.register_class(I3D_IO_AddonPreferences)


def unregister():
    bpy.utils.unregister_class(I3D_IO_AddonPreferences)
