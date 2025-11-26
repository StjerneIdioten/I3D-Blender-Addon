import pathlib

import addon_utils
import bpy
from bpy.props import EnumProperty, StringProperty
from bpy.types import AddonPreferences

from .. import __package__ as base_package
from ..utility import ext_user_dir
from .bit_mask_editor import get_bitmask_flags
from .collision_data import populate_collision_cache
from .material_templates import parse_templates
from .shader_parser import populate_game_shaders


class I3D_IO_AddonPreferences(AddonPreferences):
    bl_idname = base_package

    # Blender does not automatically mark add-on preferences as "dirty" when modified through the API (via operators).
    # This means that changes made programmatically will not be saved when Blender is closed.
    # The workaround below forces Blender to recognize the preferences as modified,
    # ensuring that the assigned property persists across Blender sessions.
    # Related Blender issue: https://projects.blender.org/blender/blender/issues/128505
    def update_is_dirty(self, context: bpy.types.Context) -> None:
        context.preferences.is_dirty = True

    fs_data_path: StringProperty(
        name="FS Data Folder",
        description=(
            "Path to the Farming Simulator data folder.\n"
            "This is required for the add-on to function properly, as it provides access to game assets."
        ),
        default="",
        update=update_is_dirty
    )

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

        box = col.box()
        data_path = pathlib.Path(self.fs_data_path)
        is_data_path_valid = data_path.exists() and data_path.is_dir() and data_path.name.lower() == "data"
        if not is_data_path_valid or not self.fs_data_path:
            if not self.fs_data_path:
                box.label(text="No FS Data Path set. This is required for the add-on to function properly.",
                          icon="ERROR")
            elif not data_path.exists():
                box.label(text="The specified path does not exist.", icon="ERROR")
            elif not data_path.is_dir():
                box.label(text="The specified path is not a directory.", icon="ERROR")
            elif data_path.name.lower() != "data":
                box.label(text="Path must point directly to the game's 'data' folder.", icon="ERROR")
            else:
                box.label(text="Invalid FS Data Path.", icon="ERROR")
        row = box.row(align=True)
        row.prop(self, 'fs_data_path')
        row.operator("i3dio.set_fs_data_path", text="", icon='FILE_FOLDER')

        col.separator(factor=1.5)
        box = col.box()
        box.label(text="I3D Converter (i3dConverter.exe):")

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
                    info_box.label(text="GIANTS I3D Exporter add-on detected.", icon="CHECKMARK")
                    info_box.label(text="Use its bundled i3dConverter.exe path:")
                    row = info_box.row()
                    row.operator(
                        'i3dio.i3d_converter_path_from_giants_addon',
                        text="Use Path from GIANTS Add-on",
                        icon="FILE_ALIAS",
                    )
                    info_box.separator()
                info_box.label(text="Automatically download and set up the I3D Converter:", icon="TRIA_RIGHT")
                row = info_box.row()
                row.operator("i3dio.download_i3d_converter", text="Download / Update from GDN...", icon='INTERNET')
            else:
                info_box.label(text="Manually download and set up the I3D Converter:", icon="TRIA_RIGHT")
                info_box.label(text="1. Open the GDN downloads page:")
                row = info_box.row()
                props = row.operator("wm.url_open", text="gdn.giants-software.com", icon='URL')
                props.url = "https://gdn.giants-software.com/downloads.php"

                info_box.label(text="2. Download the GIANTS Blender Exporter .zip for your FS version.")
                info_box.label(text="3. Extract the .zip file.")
                info_box.label(text="4. Locate io_export_i3d/util/i3dConverter.exe.")
                info_box.label(text="5. Move it to a convenient location.")
                info_box.label(text="6. Use the file browser below to set the path manually.")
        row = box.row(align=True)
        row.use_property_split = True
        row.prop(self, 'i3d_converter_path', placeholder="Path to i3dConverter.exe")
        if is_path_valid:
            row.operator('i3dio.reset_i3d_converter_path', icon='X', text="")


class I3D_IO_OT_set_fs_data_path(bpy.types.Operator):
    bl_idname = "i3dio.set_fs_data_path"
    bl_label = "Set FS Data Path"
    bl_description = "Set the path to the Farming Simulator data folder"
    bl_options = {'INTERNAL', 'UNDO'}
    directory: StringProperty(name="FS Data Folder", subtype='DIR_PATH')

    def execute(self, context):
        path = pathlib.Path(self.directory).resolve()

        if not path.exists():
            self.report({'ERROR'}, "The provided path does not exist")
            return {"CANCELLED"}
        if path.name.lower() != "data":  # Check if the last folder is named "data"
            data_path = path / "data"
            if not data_path.exists():
                self.report({'ERROR'}, "Could not find 'data' folder inside provided path")
                return {"CANCELLED"}
            path = data_path

        corrected_path = str(path) + ('\\' if path.drive else '/')
        context.preferences.addons[base_package].preferences.fs_data_path = corrected_path
        self.report({'INFO'}, f"FS Data Path set to: {corrected_path}")
        populate_game_shaders()
        parse_templates(None)
        populate_collision_cache()
        get_bitmask_flags()
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


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

    MIN_VERSION = (10, 0, 0)
    ADDON_NAME = "GIANTS I3D Exporter Tools"

    def execute(self, context):
        latest = None
        for addon in addon_utils.modules():
            info = getattr(addon, "bl_info", {})
            if info.get("name") == self.ADDON_NAME:
                version = tuple(info.get("version", (0, 0, 0)))
                if version >= self.MIN_VERSION:
                    if not latest or version > latest[0]:
                        latest = (version, addon)
        if not latest:
            self.report({"WARNING"}, "No GIANTS I3D Exporter Tools v10+ addon found.")
            return {"CANCELLED"}
        addon = latest[1]
        path = pathlib.Path(addon.__file__).parent.joinpath('util/i3dConverter.exe')
        if not path.exists():
            self.report({"WARNING"}, f"Converter not found at: {path}")
            return {"CANCELLED"}

        context.preferences.addons[base_package].preferences.i3d_converter_path = str(path)
        self.report({"INFO"}, f"Found converter from version {latest[0]} at: {path}")
        return {"FINISHED"}


DOWNLOADS_URL = 'https://gdn.giants-software.com/downloads.php'
PATTERN_EXPORTER_TEXT = r'Blender Exporter Plugins v[0-9]+\.[0-9]+\.[0-9]+'
PATTERN_EXPORTER = (
    r'href="download\.php\?downloadId=([0-9]+)">'
    r'Blender Exporter Plugins v([0-9]+\.[0-9]+\.[0-9]+) '
    r'\(([^)]+)\)'
)
LOGIN_URL = 'https://gdn.giants-software.com/index.php'

class I3D_IO_OT_download_i3d_converter(bpy.types.Operator):
    bl_idname = "i3dio.download_i3d_converter"
    bl_label = "Download I3D Converter"
    bl_description = (
        "Download i3dConverter.exe from the Giants Developer Network.\n"
        "The downloads page is usually public, but GDN account credentials can be used if login is required."
    )
    bl_options = {'INTERNAL'}

    email: StringProperty(name="GDN Email", default="")
    password: StringProperty(name="GDN Password", default="", subtype="PASSWORD")

    _login_required: bool = False

    @classmethod
    def poll(cls, context):
        cls.poll_message_set("Online access required to download the I3D Converter, "
                             "enable it in the Blender System Preferences to use this feature!")
        return bpy.app.online_access

    def _probe_login_required(self):
        import re

        from requests import Session

        session = Session()
        try:
            resp = session.get(DOWNLOADS_URL, timeout=3.0)
        except Exception:
            # Any error, assume login is required
            return True
        if re.search(PATTERN_EXPORTER_TEXT, resp.text):
            # Exporter text visible, page likely does not require login
            return False
        return True

    def execute(self, context):
        import re
        from io import BytesIO
        from shutil import copyfileobj
        from zipfile import BadZipfile, ZipFile

        from requests import Session

        email = (self.email or "").strip()
        password = (self.password or "").strip()
        self.email = ""
        self.password = ""

        session = Session()

        def fetch_latest_exporter() -> list[tuple[str, str, str]]:
            """Return list[(download_id, version, game)] for Blender exporters."""
            request = session.get(DOWNLOADS_URL)
            matches = re.findall(PATTERN_EXPORTER, request.text)
            fs_matches = [m for m in matches if m[2].startswith("Farming Simulator")]
            return fs_matches or matches

        def pick_latest_exporter(matches: list[tuple[str, str, str]]) -> tuple[str, str, str]:
            """Given list[(download_id, version, game)], return the latest by version."""
            def parse_version(v: str) -> tuple[int, int, int]:
                try:
                    major, minor, patch = (int(p) for p in v.split("."))
                    return major, minor, patch
                except Exception:
                    # If parsing fails, treat as 0.0.0 so valid versions win
                    return (0, 0, 0)

            # Determine latest version among the filtered matches
            latest_version = max(matches, key=lambda item: parse_version(item[1]))[1]
            # Return first entry matching that version
            for m in matches:
                if m[1] == latest_version:
                    return m
            return matches[0]  # Fallback, should not happen

        result = fetch_latest_exporter()
        if not result and email and password:
            request = session.post(LOGIN_URL, data={'greenstoneX': '1', 'redstoneX': email, 'bluestoneX': password})

            if not re.search(r'href="index\.php\?logout=true"', request.text):
                self.report(
                    {'WARNING'},
                    "Could not log in to Giants Developer Network (GDN). "
                    "Make sure you enter your account email and password from "
                    "https://gdn.giants-software.com/."
                )
                return {'CANCELLED'}
            result = fetch_latest_exporter()

        if not result:
            if getattr(self, "_login_required", False) and not (email and password):
                self.report(
                    {'WARNING'},
                    "The GDN downloads page likely requires login. "
                    "Please run this again and enter your GDN email & password."
                )
            else:
                self.report({'WARNING'}, "Could not find the GIANTS Blender Exporter download link.")
            return {'CANCELLED'}

        download_id, exporter_version, game_name = pick_latest_exporter(result)
        download_url = f"https://gdn.giants-software.com/download.php?downloadId={download_id}"
        request = session.get(download_url)

        try:
            zipfile = ZipFile(BytesIO(request.content), 'r')
            binary_path = ext_user_dir("bin") / "i3dConverter.exe"
            with zipfile.open("io_export_i3d/util/i3dConverter.exe") as binary_zip, open(binary_path, "wb") as saved:
                copyfileobj(binary_zip, saved)

            context.preferences.addons[base_package].preferences.i3d_converter_path = str(binary_path)
        except (BadZipfile, KeyError, OSError) as e:
            self.report({'WARNING'}, f"Failed to fetch/install the GIANTS I3D Converter: {e}")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Installed I3D Converter (v{exporter_version}, {game_name}).")
        return {'FINISHED'}

    def invoke(self, context, event):
        bin_path = ext_user_dir("bin") / 'i3dConverter.exe'
        if bin_path.exists():
            context.preferences.addons[base_package].preferences.i3d_converter_path = str(bin_path)
            self.report({"INFO"}, f"Existing i3dConverter.exe found at: {bin_path}")
            return {'FINISHED'}
        self._login_required = self._probe_login_required()
        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, _context):
        layout = self.layout
        box = layout.box()

        if getattr(self, "_login_required", False):
            box.label(
                text="GDN downloads may require login.",
                icon='INFO',
            )
            box.label(text="Enter your GDN account details:")
            box.prop(self, "email")
            box.prop(self, "password")
        else:
            box.label(text="Click OK to download.")

        row = box.row()
        row.alignment = "CENTER"
        row.label(text="Blender UI will appear frozen during file download (~18MB)", icon="ERROR")


classes = (
    I3D_IO_OT_set_fs_data_path,
    I3D_IO_OT_reset_i3d_converter_path,
    I3D_IO_OT_i3d_converter_path_from_giants_addon,
    I3D_IO_OT_download_i3d_converter,
    I3D_IO_AddonPreferences,
)

register, unregister = bpy.utils.register_classes_factory(classes)
