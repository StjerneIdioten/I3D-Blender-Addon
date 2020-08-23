import bpy
from bpy.props import (
    StringProperty
)

from bpy_extras.io_utils import (
    ExportHelper,
    orientation_helper
)

from bpy.types import (
    Operator,
    Panel
)

from .. import (
        exporter,
        xml_i3d
)


classes = []


def register(cls):
    classes.append(cls)
    return cls


@register
@orientation_helper(axis_forward='-Z', axis_up='Y')
class I3D_IO_OT_export(Operator, ExportHelper):
    """Save i3d file"""
    bl_idname = "export_scene.i3d"
    bl_label = "Export I3D"
    bl_options = {'PRESET'}  # 'PRESET' enables the preset dialog for saving settings as preset

    filename_ext = xml_i3d.file_ending
    filter_glob: StringProperty(default=f"*{xml_i3d.file_ending}",
                                options={'HIDDEN'},
                                maxlen=255,
                                )

    # Add remaining properties from original addon as they get implemented

    def execute(self, context):
        status = exporter.export_blend_to_i3d(self.filepath, self.axis_forward, self.axis_up)
        if status:
            self.report({'INFO'}, f"I3D Export Successful! It took {status['time']:.3f} seconds")
        else:
            self.report({'ERROR'}, "I3D Export Failed! Check console/log for error(s)")
        return {'FINISHED'}
    
    def draw(self, context):
        pass


@register
class I3D_IO_PT_export_main(Panel):
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOL_PROPS'
    bl_label = ""
    bl_parent_id = 'FILE_PT_operator'
    bl_options = {'HIDE_HEADER'}

    @classmethod
    def poll(cls, context):
        sfile = context.space_data
        operator = sfile.active_operator

        return operator.bl_idname == 'EXPORT_SCENE_OT_i3d'

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        sfile = context.space_data
        operator = sfile.active_operator

        layout.prop(bpy.context.scene.i3dio, 'selection')


@register
class I3D_IO_PT_export_options(Panel):
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOL_PROPS'
    bl_label = "Export Options"
    bl_parent_id = 'FILE_PT_operator'

    @classmethod
    def poll(cls, context):
        sfile = context.space_data
        operator = sfile.active_operator

        return operator.bl_idname == 'EXPORT_SCENE_OT_i3d'

    def draw(self, context):
        layout = self.layout

        sfile = context.space_data
        operator = sfile.active_operator

        row = layout.row()
        row.prop(bpy.context.scene.i3dio, 'keep_collections_as_transformgroups')

        row = layout.row()
        row.prop(bpy.context.scene.i3dio, 'apply_modifiers')

        row = layout.row()
        row.prop(bpy.context.scene.i3dio, 'apply_unit_scale')

        box = layout.box()
        row = box.row()
        row.label(text='Object types to export')
        column = box.column()
        column.props_enum(bpy.context.scene.i3dio, 'object_types_to_export')

        box = layout.box()
        row = box.row()
        row.label(text='Features to enable')
        column = box.column()
        column.props_enum(bpy.context.scene.i3dio, 'features_to_export')
        row = box.row()
        row.prop(bpy.context.scene.i3dio, 'armature_as_root')

        layout.prop(operator, "axis_forward")
        layout.prop(operator, "axis_up")


@register
class I3D_IO_PT_export_files(Panel):
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOL_PROPS'
    bl_label = "File Options"
    bl_parent_id = 'FILE_PT_operator'

    @classmethod
    def poll(cls, context):
        sfile = context.space_data
        operator = sfile.active_operator

        return operator.bl_idname == 'EXPORT_SCENE_OT_i3d'

    def draw(self, context):
        layout = self.layout

        sfile = context.space_data
        operator = sfile.active_operator

        row = layout.row()
        row.prop(bpy.context.scene.i3dio, 'copy_files')
        row = layout.row()
        row.prop(bpy.context.scene.i3dio, 'overwrite_files')
        row.enabled = bpy.context.scene.i3dio.copy_files

        row = layout.row()
        row.enabled = bpy.context.scene.i3dio.copy_files
        row.alignment = 'RIGHT'
        row.prop(bpy.context.scene.i3dio, 'file_structure', )

        box = layout.box()
        row = box.row()
        row.label(text='I3D Mapping Mode')
        column = box.column()
        column.props_enum(bpy.context.scene.i3dio, 'i3d_mapping_overwrite_mode')


@register
class I3D_IO_PT_export_shape(Panel):
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOL_PROPS'
    bl_label = "Shape"
    bl_parent_id = 'FILE_PT_operator'

    @classmethod
    def poll(cls, context):
        sfile = context.space_data
        operator = sfile.active_operator

        return operator.bl_idname == "EXPORT_SCENE_OT_i3d"

    def draw(self, context):
        layout = self.layout

        sfile = context.space_data
        operator = sfile.active_operator

        row = layout.row()


@register
class I3D_IO_PT_export_misc(Panel):
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOL_PROPS'
    bl_label = "Miscellaneous"
    bl_parent_id = 'FILE_PT_operator'

    @classmethod
    def poll(cls, context):
        sfile = context.space_data
        operator = sfile.active_operator

        return operator.bl_idname == "EXPORT_SCENE_OT_i3d"

    def draw(self, context):
        layout = self.layout

        sfile = context.space_data
        operator = sfile.active_operator

        row = layout.row()


@register
class I3D_IO_PT_export_debug(Panel):
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOL_PROPS'
    bl_label = "Debug Options"
    bl_parent_id = 'FILE_PT_operator'

    @classmethod
    def poll(cls, context):
        sfile = context.space_data
        operator = sfile.active_operator

        return operator.bl_idname == 'EXPORT_SCENE_OT_i3d'

    def draw(self, context):
        layout = self.layout

        sfile = context.space_data
        operator = sfile.active_operator

        row = layout.row()
        layout.prop(bpy.context.scene.i3dio, 'verbose_output')
        layout.prop(bpy.context.scene.i3dio, 'log_to_file')


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)