import addon_utils
import pathlib

import bpy
from bpy.types import AddonPreferences
from bpy.props import (StringProperty, EnumProperty)
from .. import __package__ as base_package
from .shader_parser import populate_game_shaders
from .material_templates import parse_templates


def show_popup(title: str, message: str, icon: str = 'ERROR', units: int = 10):
    def draw_popup(popup, _context):
        layout: bpy.types.UILayout = popup.layout
        layout.label(text=title, icon=icon)
        layout.separator(type="LINE")
        layout.label(text=message)
        layout.template_popup_confirm("", text="", cancel_text="Close")
    wm = bpy.context.window_manager
    wm.popover(draw_popup, ui_units_x=units)


def update_fs_data_path(self, context: bpy.types.Context) -> None:
    wm = context.window_manager
    last_path = getattr(wm, "fs_last_data_path", "")
    path = pathlib.Path(self.fs_data_path).resolve()
    wm.fs_last_data_path = self.fs_data_path

    if not path.exists():
        show_popup("Invalid Path", "The provided path does not exist", units=9)
        return
    if path.name.lower() != "data":  # Try to append "data" folder if not already present
        data_path = path / "data"
        if not data_path.exists():  # Check if "data" actually exists inside the given folder
            show_popup("Invalid Path", "Could not find 'data' folder inside provided path", units=13)
            return
        path = data_path  # Append "data" if valid
    corrected_path = str(path) + ('\\' if path.drive else '/')
    if corrected_path != last_path:  # Prevent infinite recursion by only updating if different
        self.fs_data_path = corrected_path
        populate_game_shaders()
        parse_templates(None)


class I3D_IO_AddonPreferences(AddonPreferences):
    bl_idname = base_package

    fs_data_path: StringProperty(
        name="FS Data Folder",
        subtype='DIR_PATH',
        default="",
        update=update_fs_data_path
    )

    # Blender does not automatically mark add-on preferences as "dirty" when modified through the API (via operators).
    # This means that changes made programmatically will not be saved when Blender is closed.
    # The workaround below forces Blender to recognize the preferences as modified,
    # ensuring that the I3D Converter path persists across Blender sessions.
    # Related Blender issue: https://projects.blender.org/blender/blender/issues/128505
    def update_is_dirty(self, context: bpy.types.Context) -> None:
        context.preferences.is_dirty = True

    i3d_converter_path: StringProperty(
        name="I3D Converter Path",
        description=("Path to i3dConverter.exe, required to convert raw I3D files by extracting <Shapes> data "
                     "and generating an external .shapes file for optimized mesh storage."),
        subtype='FILE_PATH',
        default="",
        update=update_is_dirty
    )

    general_tabs: EnumProperty(name="Tabs", items=[("GENERAL", "General", "")], default="GENERAL")
    converter_mode_tabs: EnumProperty(name="Tabs", items=[("AUTOMATIC", "Automatic", ""), ("MANUAL", "Manual", "")])

    def draw(self, context):
        layout = self.layout

        col = layout.column(align=True)
        row = col.row()
        row.prop(self, "general_tabs", expand=True)
        col.separator(factor=1.5)
        col.box().row().prop(self, 'fs_data_path')
        col.separator(factor=1.5)
        box = col.box()
        box.label(text="Binary I3D Converter:")

        giants_exist = any(addon.bl_info.get("name") == "GIANTS I3D Exporter Tools" for addon in addon_utils.modules())
        path = pathlib.Path(self.i3d_converter_path)
        is_path_valid = path.exists() and path.is_file()
        if not is_path_valid or (giants_exist and not self.i3d_converter_path):
            info_box = box.box()
            if not is_path_valid and self.i3d_converter_path != "":
                info_box.label(text="Invalid I3D Converter path set.", icon="ERROR")
            else:
                info_box.label(text="No I3D Converter path set.", icon="INFO")

            info_box.row().prop(self, "converter_mode_tabs", expand=True)
            if self.converter_mode_tabs == "AUTOMATIC":
                if giants_exist:
                    info_box.label(text="GIANTS I3D Exporter is installed.", icon="TRIA_RIGHT")
                    info_box.label(text="Click below to set the path automatically:")
                    row = info_box.row()
                    row.operator('i3dio.i3d_converter_path_from_giants_addon',
                                 text="Get Path from GIANTS Addon", icon="FILE_ALIAS")
                    info_box.separator()
                info_box.label(text="Automatically download and set up the I3D Converter:", icon="TRIA_RIGHT")
                row = info_box.row()
                row.operator("i3dio.download_i3d_converter", text="Download I3D Converter...", icon='INTERNET')
            else:
                info_box.label(text="Manually download and set up the I3D Converter:", icon="TRIA_RIGHT")
                info_box.label(text="1. Download the GIANTS I3D Exporter addon:")
                row = info_box.row()
                props = row.operator("wm.url_open", text="gdn.giants-software.com", icon='URL')
                props.url = "https://gdn.giants-software.com/downloads.php"

                info_box.label(text="2. Extract the .zip file.")
                info_box.label(text="3. Locate io_export_i3d/util/i3dConverter.exe.")
                info_box.label(text="4. Move it to a convenient location.")
                info_box.label(text="5. Use the file browser icon below to set the path manually.")
        row = box.row(align=True)
        row.use_property_split = True
        row.prop(self, 'i3d_converter_path', placeholder="Path to i3dConverter.exe")
        if is_path_valid:
            row.operator('i3dio.reset_i3d_converter_path', icon='X', text="")


class I3D_IO_OT_reset_i3d_converter_path(bpy.types.Operator):
    bl_idname = "i3dio.reset_i3d_converter_path"
    bl_label = "Reset I3D Converter Path"
    bl_description = "Reset the path to the I3D Converter binary"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        context.preferences.addons[base_package].preferences.i3d_converter_path = ""
        return {"FINISHED"}


class I3D_IO_OT_i3d_converter_path_from_giants_addon(bpy.types.Operator):
    bl_idname = "i3dio.i3d_converter_path_from_giants_addon"
    bl_label = "Get I3D converter path from Giants addon"
    bl_description = "Get the i3d converter path from the Giants exporter addon"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        if addon := next((addon for addon in addon_utils.modules()
                          if addon.bl_info.get("name") == "GIANTS I3D Exporter Tools"), None):
            path = str(pathlib.PurePath(addon.__file__).parent.joinpath('util/i3dConverter.exe'))
            context.preferences.addons[base_package].preferences.i3d_converter_path = path
        return {"FINISHED"}


class I3D_IO_OT_download_i3d_converter(bpy.types.Operator):
    bl_idname = "i3dio.download_i3d_converter"
    bl_label = "Download I3D Converter"
    bl_description = "Download from Giants Developer Network (Requires valid login)"
    bl_options = {'INTERNAL'}

    email: StringProperty(name="Email", default="")
    password: StringProperty(name="Password", default="", subtype="PASSWORD")

    @classmethod
    def poll(cls, context):
        cls.poll_message_set("Online access required to download the I3D Converter, "
                             "enable it in the Blender System Preferences to use this feature!")
        return bpy.app.online_access

    def execute(self, context):
        import re
        from io import BytesIO
        from requests import Session
        from zipfile import (ZipFile, BadZipfile)
        from shutil import copyfileobj

        # Attempt to login using provided credentials
        session = Session()
        request = session.post('https://gdn.giants-software.com/index.php', data={'greenstoneX':'1', 'redstoneX':self.email, 'bluestoneX':self.password})

        # Clear email and password after usage
        self.email = ""
        self.password = ""

        # Check if login was successful
        if not re.search(r'href="index\.php\?logout=true"', request.text):
            self.report({'WARNING'}, "Could not login to https://gdn.giants-software.com/index.php with provided credentials!")
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
            context.preferences.addons[base_package].preferences.i3d_converter_path = str(binary_path)
        except (BadZipfile, KeyError, OSError) as e:
            self.report({'WARNING'}, f"The Community I3D Exporter did not succesfully fetch and install the Giants I3D Converter binary! ({e})")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Fetched i3dConverter.exe from version {exporter_version} of the Giants Exporter downloaded from {download_url}")
        return {'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
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
    bpy.types.WindowManager.fs_last_data_path = StringProperty()
    bpy.utils.register_class(I3D_IO_OT_reset_i3d_converter_path)
    bpy.utils.register_class(I3D_IO_OT_i3d_converter_path_from_giants_addon)
    bpy.utils.register_class(I3D_IO_OT_download_i3d_converter)
    bpy.utils.register_class(I3D_IO_AddonPreferences)


def unregister():
    bpy.utils.unregister_class(I3D_IO_AddonPreferences)
    bpy.utils.unregister_class(I3D_IO_OT_download_i3d_converter)
    bpy.utils.unregister_class(I3D_IO_OT_i3d_converter_path_from_giants_addon)
    bpy.utils.unregister_class(I3D_IO_OT_reset_i3d_converter_path)
    del bpy.types.WindowManager.fs_last_data_path
