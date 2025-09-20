from pathlib import Path
import logging
import bpy
from bpy.types import Operator
from bpy.props import EnumProperty

from .. import debugging
from ..motion_path_array_collect import MotionPathArray
from ..dds_writer import write_dds_dx10


def export_motion_path_array(obj: bpy.types.Object, depsgraph: bpy.types.Depsgraph,
                             logger=debugging.addon_logger) -> tuple[str, str]:
    """Exports DDS for an object with motion path array enabled.
    - logger: optional logging.Logger for info/error output
    Returns True on success, False otherwise.
    """
    array_builder = MotionPathArray(obj, depsgraph)
    gathered_array = array_builder.gather_data()

    filepath = obj.i3d_motion_path_array.filepath
    name = obj.name
    if gathered_array is None or not filepath:
        msg = f"[{name}] Skipped: No data or filepath."
        logger.info(msg)
        return 'SKIP', msg

    if not filepath.endswith('.dds'):
        filepath += '.dds'
    try:
        filepath = bpy.path.abspath(filepath)
        # ensure directory exists
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        write_dds_dx10(filepath, gathered_array)
        msg = f"[{name}] Exported successfully to {filepath}"
        logger.info(msg)
        return 'SUCCESS', msg
    except Exception as e:
        msg = f"[{name}] Failed to write DDS: {e}"
        logger.error(msg)
        return 'FAIL', msg


class I3D_IO_OT_motion_path_array(Operator):
    bl_idname = "i3dio.motion_path_array"
    bl_label = "Motion Path Array"
    bl_description = (
        "Triggers the export of Motion Path Array DDS textures for objects configured within the scene. "
        "Does not open a file browser, as file paths are defined per-object."
    )
    bl_options = {'UNDO'}

    selection: EnumProperty(
        name="Export Scope",
        items=[
            ("ALL", "All Objects", "Export all objects in the scene"),
            ("ACTIVE_COLLECTION", "Active Collection", "Export objects in the active collection"),
            ("SELECTED_OBJECTS", "Selected Objects", "Export only selected objects"),
        ],
        default='ALL'
    )

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

        success_count = 0
        skip_count = 0
        fail_count = 0

        for obj in objects:
            if not obj.i3d_motion_path_array.enabled:
                continue
            status, message = export_motion_path_array(obj, depsgraph=context.view_layer.depsgraph)

            match status:
                case 'SUCCESS':
                    success_count += 1
                case 'FAIL':
                    fail_count += 1
                    self.report({'ERROR'}, f"Failed to export {obj.name}: {message}")
                case 'SKIP':
                    skip_count += 1

        if fail_count > 0:
            self.report({'ERROR'}, f"Export finished with {fail_count} error(s). Check the console for details.")
            return {'CANCELLED'}

        if success_count == 0:
            self.report({'WARNING'}, f"No DDS textures were exported. ({skip_count} skipped). Check configuration.")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Export successful: {success_count} file(s) written, {skip_count} skipped.")
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, confirm_text="Export")

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
