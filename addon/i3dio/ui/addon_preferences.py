import bpy
from bpy.types import AddonPreferences
from bpy.props import (StringProperty, EnumProperty)

from .. import xml_i3d


def xml_library_callback(scene, context):
    items = [
        ('element_tree', 'ElementTree', 'The standard library which comes with python. It is limited in functionality'
                                     ' and will potentially mess with formatting of your xml files. It is only kept '
                                     'around in case people have no way of installing lxml')
    ]

    if 'lxml' in xml_i3d.xml_libraries:
        items.append(('lxml', 'LXML', 'The preferred version. \n'
                                      'It is an external library with more functionality and it does not mess with the '
                                      'formatting of your files'))

    return items


def xml_library_changed(self, context):
    xml_i3d.xml_current_library = self.xml_library


class I3D_IO_AddonPreferences(AddonPreferences):
    bl_idname = 'i3dio'

    fs_data_path: StringProperty(
        name="FS Data Folder",
        subtype='DIR_PATH',
        default=""
    )

    xml_library: EnumProperty(
        name="XML Library",
        description="Which xml library to use for export/import of xml or i3d files",
        items=xml_library_callback,
        update=xml_library_changed
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'fs_data_path')
        layout.prop(self, 'xml_library')


def register():
    bpy.utils.register_class(I3D_IO_AddonPreferences)
    if 'lxml' in xml_i3d.xml_libraries:
        bpy.context.preferences.addons['i3dio'].preferences.xml_library = 'lxml'


def unregister():
    bpy.utils.unregister_class(I3D_IO_AddonPreferences)
