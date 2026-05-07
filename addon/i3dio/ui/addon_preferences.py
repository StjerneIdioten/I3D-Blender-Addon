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
        update=update_is_dirty,
    )

    i3d_converter_path: StringProperty(
        name="I3D Converter Path",
        description=(
            "Path to i3dConverter.exe, required to convert raw I3D files by extracting <Shapes> data "
            "and generating an external .shapes file for optimized mesh storage."
        ),
        subtype='FILE_PATH',
        default="",
        update=update_is_dirty,
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
                box.label(
                    text="No FS Data Path set. This is required for the add-on to function properly.", icon="ERROR"
                )
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
                info_box.label(text="Note: Blender may appear frozen during download (~18MB).", icon="INFO")
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
    bl_label = "Get I3D converter path from Giants Add-on"
    bl_description = "Copy i3dConverter.exe from the GIANTS exporter add-on into the add-on bin folder"
    bl_options = {'INTERNAL'}

    MIN_VERSION = (10, 0, 0)
    ADDON_NAME = "GIANTS I3D Exporter Tools"

    def execute(self, context):
        import shutil

        latest = None
        for addon in addon_utils.modules():
            info = getattr(addon, "bl_info", {})
            if info.get("name") == self.ADDON_NAME:
                version = tuple(info.get("version", (0, 0, 0)))
                if version >= self.MIN_VERSION:
                    if not latest or version > latest[0]:
                        latest = (version, addon)
        if not latest:
            self.report({'WARNING'}, "No GIANTS I3D Exporter Tools v10+ addon found.")
            return {'CANCELLED'}
        version, addon = latest
        src = pathlib.Path(addon.__file__).parent / "util" / "i3dConverter.exe"
        if not src.exists():
            self.report({'WARNING'}, f"Converter not found at: {src}")
            return {'CANCELLED'}
        dst = ext_user_dir("bin") / "i3dConverter.exe"
        try:
            shutil.copyfile(src, dst)
        except OSError as e:
            self.report({'WARNING'}, f"Failed to copy converter: {e}")
            return {'CANCELLED'}

        context.preferences.addons[base_package].preferences.i3d_converter_path = str(dst)
        self.report({'INFO'}, f"Imported I3D Converter from GIANTS exporter v{version}")
        return {'FINISHED'}


class I3D_IO_OT_download_i3d_converter(bpy.types.Operator):
    bl_idname = "i3dio.download_i3d_converter"
    bl_label = "Download I3D Converter"
    bl_description = (
        "Download i3dConverter.exe from the Giants Developer Network.\nRequires online access.\n"
        "Note: Blender may appear frozen during download."
    )
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        cls.poll_message_set(
            "Online access required to download the I3D Converter, "
            "enable it in the Blender System Preferences to use this feature!"
        )
        return bpy.app.online_access

    def execute(self, context):
        import html as _html
        import re
        from io import BytesIO
        from shutil import copyfileobj
        from urllib.error import HTTPError, URLError
        from urllib.request import Request, urlopen
        from zipfile import BadZipFile, ZipFile

        ua = {"User-Agent": "Blender I3D IO Addon"}

        def _parse_version(version_str: str) -> tuple[int, int, int]:
            try:
                return tuple((int(p) for p in version_str.split(".")))
            except Exception:
                # If parsing fails, treat as 0.0.0 so valid versions win
                return (0, 0, 0)

        _re_exporter_table = re.compile(
            r"<h2>\s*Exporter\s*</h2>\s*(<table.*?</table>)",
            flags=re.IGNORECASE | re.DOTALL,
        )
        _re_tr = re.compile(r"<tr[^>]*>(.*?)</tr>", flags=re.IGNORECASE | re.DOTALL)
        _re_td = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", flags=re.IGNORECASE | re.DOTALL)
        _re_download_id = re.compile(r'href="download\.php\?downloadId=(\d+)"', flags=re.IGNORECASE)
        _re_version_in_name = re.compile(r"\bv(\d+\.\d+\.\d+)\b", flags=re.IGNORECASE)

        def _strip_tags(s: str) -> str:
            return _html.unescape(re.sub(r"<[^>]+>", "", s).strip())

        def _latest_blender_exporter(html: str) -> tuple[str, str, str]:
            """Returns: (download_id, exporter_version, compatibility) Prefers FS* rows over PMR rows."""
            m = _re_exporter_table.search(html)
            if not m:
                raise ValueError("Exporter table not found (page layout changed?)")

            table_html = m.group(1)
            rows = _re_tr.findall(table_html)

            found: list[tuple[str, str, str]] = []  # (download_id, version, compatibility)
            for row_html in rows:
                dm = _re_download_id.search(row_html)
                if not dm:
                    continue

                cells = [_strip_tags(c) for c in _re_td.findall(row_html)]
                if len(cells) < 2:
                    continue

                product_name = cells[0]
                compatibility = cells[1]

                if not product_name.lower().startswith("blender exporter plugins"):
                    continue

                vm = _re_version_in_name.search(product_name)
                if not vm:
                    continue

                download_id = dm.group(1)
                version = vm.group(1)
                found.append((download_id, version, compatibility))

            if not found:
                raise ValueError("No Blender Exporter rows found")

            # Only keep FS25 entries
            fs25 = [t for t in found if t[2].strip().upper().startswith("FS25") or "FS25" in t[2].strip().upper()]
            if not fs25:
                raise ValueError("No FS25 Blender Exporter entry found on GDN downloads page")

            return max(fs25, key=lambda t: _parse_version(t[1]))

        try:
            req = Request("https://gdn.giants-software.com/downloads.php", headers=ua)
            with urlopen(req, timeout=10.0) as resp:
                page_html = resp.read().decode("utf-8", errors="replace")
            download_id, exporter_version, compatibility = _latest_blender_exporter(page_html)

            zip_url = f"https://gdn.giants-software.com/download.php?downloadId={download_id}"
            req = Request(zip_url, headers=ua)
            with urlopen(req, timeout=20.0) as resp:
                zip_data = resp.read()

            with ZipFile(BytesIO(zip_data), 'r') as zf:
                exe_member = next((n for n in zf.namelist() if n.lower().endswith("i3dconverter.exe")), None)
                if not exe_member:
                    raise KeyError("i3dConverter.exe not found in ZIP archive")
                binary_path = ext_user_dir("bin") / "i3dConverter.exe"
                with zf.open(exe_member) as binary_zip, open(binary_path, "wb") as saved:
                    copyfileobj(binary_zip, saved)
        except HTTPError as e:
            self.report({'WARNING'}, f"GDN returned HTTP error {e.code}.")
            return {'CANCELLED'}
        except URLError as e:
            self.report({'WARNING'}, f"Failed to reach GDN downloads page: {e.reason}.")
            return {'CANCELLED'}
        except (BadZipFile, KeyError, OSError, ValueError) as e:
            self.report({'WARNING'}, f"Failed to install i3dConverter.exe: {e}")
            return {'CANCELLED'}
        except Exception as e:
            self.report({'WARNING'}, f"Unexpected error while fetching exporter list: {e}")
            return {'CANCELLED'}

        context.preferences.addons[base_package].preferences.i3d_converter_path = str(binary_path)
        self.report({"INFO"}, f"Installed I3D Converter (Exporter v{exporter_version}, {compatibility}).")
        return {'FINISHED'}


classes = (
    I3D_IO_OT_set_fs_data_path,
    I3D_IO_OT_reset_i3d_converter_path,
    I3D_IO_OT_i3d_converter_path_from_giants_addon,
    I3D_IO_OT_download_i3d_converter,
    I3D_IO_AddonPreferences,
)

register, unregister = bpy.utils.register_classes_factory(classes)
