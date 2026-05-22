import logging

import bpy

from .. import debugging
from ..export_core.dds.motion_path_array import export_motion_path_arrays


class I3D_IO_OT_motion_path_array(bpy.types.Operator):
    bl_idname = "i3dio.motion_path_array"
    bl_label = "Motion Path Array"
    bl_description = (
        "Triggers the export of Motion Path Array DDS textures for objects configured within the scene. "
        "Does not open a file browser, as file paths are defined per-object."
    )
    bl_options = {'UNDO'}

    selection: bpy.props.EnumProperty(
        name="Export Scope",
        items=[
            ("ALL", "All Objects", "Export all objects in the scene"),
            ("ACTIVE_COLLECTION", "Active Collection", "Export objects in the active collection"),
            ("SELECTED_OBJECTS", "Selected Objects", "Export only selected objects"),
        ],
        default='ALL',
    )

    def execute(self, context):
        match self.selection:
            case "ALL":
                objects = context.scene.objects
            case "ACTIVE_COLLECTION":
                objects = context.view_layer.active_layer_collection.collection.objects
            case "ACTIVE_OBJECT":
                objects = [context.active_object] if context.active_object is not None else []
            case "SELECTED_OBJECTS":
                objects = context.selected_objects
            case _:
                objects = []

        if not objects:
            self.report({'ERROR'}, "No objects to export")
            return {'CANCELLED'}

        debugging.addon_console_handler.setLevel(logging.DEBUG)

        summary = export_motion_path_arrays(
            objects,
            depsgraph=context.evaluated_depsgraph_get(),
            logger=debugging.addon_logger,
        )

        if summary.failed:
            self.report({"ERROR"}, f"Export finished with {summary.failed} error(s). Check the console for details.")
            return {"CANCELLED"}

        if summary.success == 0:
            self.report(
                {"WARNING"}, f"No DDS textures were exported. ({summary.skipped} skipped). Check configuration."
            )
            return {"CANCELLED"}

        self.report({"INFO"}, f"Export successful: {summary.success} file(s) written, {summary.skipped} skipped.")
        return {"FINISHED"}

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
