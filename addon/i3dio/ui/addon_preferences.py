import addon_utils
import pathlib

import bpy
from bpy.types import AddonPreferences
from bpy.props import (StringProperty, EnumProperty, BoolProperty)

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

    i3d_converter_path: StringProperty(
        name="Path To Binary I3D Converter",
        description="Path to the i3dConverter.exe",
        subtype='FILE_PATH',
        default=""
    )

    general_tabs: EnumProperty(name="Tabs", items=[("GENERAL", "General", "")], default="GENERAL")
    converter_mode_tabs: EnumProperty(name="Tabs", items=[("MANUAL", "Manual", ""), ("AUTOMATIC", "Automatic", "")], default="MANUAL")

    def draw(self, context):
        layout = self.layout

        col = layout.column(align=True)
        row = col.row()
        row.prop(self, "general_tabs", expand=True)

        box = col.box()
        row = box.row()
        row.prop(self, 'xml_library')

        row = box.row()
        row.prop(self, 'fs_data_path')

        c_box = box.box()
        c_box.label(text="Binary I3D Converter")
        
        row = c_box.row()
        row.prop(self, 'converter_mode_tabs', expand=True)

        match self.converter_mode_tabs:
            case 'MANUAL':
                row = c_box.row(align=True)
                row.prop(self, 'i3d_converter_path')
                if(next((True for addon in addon_utils.modules() if addon.bl_info.get("name") == "GIANTS I3D Exporter Tools"), False)):
                    row.operator('i3dio.i3d_converter_path_from_giants_addon', text="", icon="EVENT_G")
                row.operator("i3dio.download_i3d_converter", text="", icon='WORLD_DATA')
            case 'AUTOMATIC':
                #row = c_box.row()
                #row.operator("i3dio.download_i3d_converter", text="Manage Automatic Download")
                pass


class I3D_IO_OT_i3d_converter_path_from_giants_addon(bpy.types.Operator):
    bl_idname = "i3dio.i3d_converter_path_from_giants_addon"
    bl_label = "Get I3D converter path from Giants addon"
    bl_description = "Get the i3d converter path from the Giants exporter addon"
    bl_options = {'INTERNAL'}
    
    def execute(self, context):
        for addon in addon_utils.modules():
            if addon.bl_info.get("name") == "GIANTS I3D Exporter Tools":
                bpy.context.preferences.addons['i3dio'].preferences.i3d_converter_path = str(pathlib.PurePath(addon.__file__).parent.joinpath('util/i3dConverter.exe'))
                break
        return {"FINISHED"}


class I3D_IO_OT_download_i3d_converter(bpy.types.Operator):
    bl_idname = "i3dio.download_i3d_converter"
    bl_label = "Download I3D Converter"
    bl_description = "Download from Giants Developer Network (Requires valid login)"
    bl_options = {'INTERNAL'}

    email: StringProperty(name="Email", default="")
    password: StringProperty(name="Password", default="", subtype="PASSWORD")

    def execute(self, context):
        import re
        from io import BytesIO
        from requests import Session
        from zipfile import (ZipFile, BadZipfile)
        from shutil import copyfileobj

        # Attempt to login using provided credentials
        session = Session()
        request = session.post('https://gdn.giants-software.com/index.php', data={'greenstoneX':'1', 'redstoneX':self.email, 'bluestoneX':self.password})

        ## Clear email and password after usage
        self.email = ""
        self.password = ""

        # Check if login was successful
        if '<li id="topmenu1"><a href="index.php?logout=true" accesskey="1" title="">Logout</a></li>' not in request.text:
            self.report({'WARNING'}, f"Could not login to https://gdn.giants-software.com/index.php with provided credentials!")
            return {'CANCELLED'}
        
        # Get download page
        request = session.get('https://gdn.giants-software.com/downloads.php')

        # Find the download IDs for the all Giants Blender Exporters (As long as Giants names them the same way)
        result = re.findall(r'href="download.php\?downloadId=([0-9]+)">Blender Exporter Plugins v([0-9]+.[0-9]+.[0-9]+)', request.text)

        # Assume the first found is the newest
        download_id, exporter_version = result[0]

        # Request download of Giants I3D Exporter
        download_url = f'https://gdn.giants-software.com/download.php?downloadId={download_id}'
        request = session.get(download_url)
        
        try:
            # Create in-memory zipfile from downloaded content
            zipfile = ZipFile(BytesIO(request.content), 'r')
            # Find path to this exporter addon
            binary_path = 'i3dConverter.exe'
            for addon in addon_utils.modules():
                if addon.bl_info.get("name") == "Unofficial GIANTS I3D Exporter Tools":
                    binary_path = pathlib.PurePath(addon.__file__).parent.joinpath(binary_path)
            # Extract I3D Converter Binary from zipfile and save to disk
            with zipfile.open('io_export_i3d/util/i3dConverter.exe') as zipped_binary, open(binary_path, 'wb') as saved_binary:
                copyfileobj(zipped_binary, saved_binary)
            # Set I3D Converter Binary path to newly downloaded converter
            bpy.context.preferences.addons['i3dio'].preferences.i3d_converter_path = str(binary_path)
        except (BadZipfile, KeyError, OSError) as e:
            self.report({'WARNING'}, f"The Community I3D Exporter did not succesfully fetch and install the Giants I3D Converter binary! ({e})")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Fetched i3dConverter.exe from version {exporter_version} of the Giants Exporter downloaded from {download_url}")
        return {'FINISHED'}

    def invoke(self, context, event):
        wm = bpy.context.window_manager
        # Width increased to fit the warning about the download freezing the UI
        return wm.invoke_props_dialog(self, width=350)
        
    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.prop(self, "email")
        row = layout.row()
        row.prop(self, "password")
        row = layout.row()
        row.alignment = "CENTER"
        row.label(text="Blender UI will appear frozen during file download (~15MB) ", icon="ERROR")


def register():
    bpy.utils.register_class(I3D_IO_OT_i3d_converter_path_from_giants_addon)
    bpy.utils.register_class(I3D_IO_OT_download_i3d_converter)
    bpy.utils.register_class(I3D_IO_AddonPreferences)
    
    if 'lxml' in xml_i3d.xml_libraries:
        bpy.context.preferences.addons['i3dio'].preferences.xml_library = 'lxml'


def unregister():
    bpy.utils.unregister_class(I3D_IO_AddonPreferences)
    bpy.utils.unregister_class(I3D_IO_OT_download_i3d_converter)
    bpy.utils.unregister_class(I3D_IO_OT_i3d_converter_path_from_giants_addon)
