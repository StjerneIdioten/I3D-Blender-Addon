import logging
import bpy
from bpy.types import Operator
from bpy.props import StringProperty, EnumProperty
from bpy_extras.io_utils import ExportHelper

from .. import debugging
from ..motion_path_array_collect import gather_motion_path_array_data
from ..dds_writer import write_dds_dx10


def export_motion_path_array(obj: bpy.types.Object, logger=debugging.addon_logger, report_func=None) -> bool:
    """Exports DDS for an object with motion path array enabled.
    - logger: optional logging.Logger for info/error output
    - report_func: optional function (type, msg) for Blender operator reporting
    Returns True on success, False otherwise.
    """
    arr = gather_motion_path_array_data(obj)
    filepath = obj.i3d_motion_path_array.filepath
    name = getattr(obj, "name", "Object")
    if arr is not None and filepath:
        if not filepath.endswith('.dds'):
            filepath += '.dds'
        try:
            write_dds_dx10(filepath, arr)
            msg = f"[{name}] Exported Motion Path Array DDS to {filepath}"
            if logger:
                logger.info(msg)
            if report_func:
                report_func({'INFO'}, msg)
            return True
        except Exception as e:
            msg = f"[{name}] Failed to write DDS: {e}"
            if logger:
                logger.error(msg)
            if report_func:
                report_func({'ERROR'}, msg)
            return False
    else:
        msg = f"[{name}] Skipped DDS export: No array data or filepath set."
        if logger:
            logger.warning(msg)
        if report_func:
            report_func({'ERROR'}, msg)
        return False


class I3D_IO_OT_motion_path_array(Operator, ExportHelper):
    bl_idname = "export_scene.motion_path_array"
    bl_label = "Export Motion Path Array"
    bl_options = {'UNDO'}

    filepath = "Defined per Object and not here"
    filename_ext = ".dds"
    filter_glob: StringProperty(default="*.dds", options={'HIDDEN'}, maxlen=255)

    selection: EnumProperty(
        name="Export Scope",
        items=[
            ("ALL", "All Objects", "Export all objects in the scene"),
            ("ACTIVE_COLLECTION", "Active Collection", "Export objects in the active collection"),
            ("SELECTED_OBJECTS", "Selected Objects", "Export only selected objects"),
        ],
        default='ALL'
    )

    def invoke(self, context, event):
        self.filepath = "Defined per Object and not here"
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        match self.selection:
            case 'ALL':
                objects = context.scene.objects
            case 'ACTIVE_COLLECTION':
                objects = context.view_layer.active_layer_collection.collection.objects
            case 'SELECTED_OBJECTS':
                objects = context.selected_objects

        if not objects:
            self.report({'ERROR'}, "No objects to export")
            return {'CANCELLED'}

        debugging.addon_console_handler.setLevel(logging.DEBUG)

        any_exported = False
        for obj in objects:
            if not obj.i3d_motion_path_array.enabled:
                continue
            ok = export_motion_path_array(obj, report_func=self.report)
            any_exported = any_exported or ok
        if not any_exported:
            self.report({'ERROR'}, "No DDS textures exported")
            return {'CANCELLED'}
        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, "selection")


def menu_func_export(self, context):
    self.layout.operator(I3D_IO_OT_motion_path_array.bl_idname, text="Export Motion Path Array (.dds)")


classes = (I3D_IO_OT_motion_path_array,)
_register, _unregister = bpy.utils.register_classes_factory(classes)


def register():
    _register()
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    _unregister()
