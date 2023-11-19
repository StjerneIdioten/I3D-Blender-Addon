import bpy

from bpy.props import (
    StringProperty,
    BoolProperty,
    EnumProperty,
    PointerProperty
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
class I3DExportUIProperties(bpy.types.PropertyGroup):
    selection: EnumProperty(
        name="Export",
        description="Select which part of the scene to export",
        items=[
            ('ALL', "Everything", "Export everything from the scene master collection"),
            ('ACTIVE_COLLECTION', "Active Collection", "Export only the active collection and all its children"),
            ('ACTIVE_OBJECT', "Active Object", "Export only the active object and its children"),
            ('SELECTED_OBJECTS', "Selected Objects", "Export all of the selected objects")
        ],
        default='SELECTED_OBJECTS'
    )

    binarize_i3d: BoolProperty(
        name="Binarize i3d",
        description="Binarizes i3d after Export. "
                    "Needs to have path to 3dConverter.exe set in Addon Preferences",
        default=False
    )

    keep_collections_as_transformgroups: BoolProperty(
        name="Keep Collections",
        description="Keep organisational collections as transformgroups in the i3d file. If turned off collections "
                    "will be ignored and the child objects will be added to the nearest parent in the hierarchy",
        default=True
    )

    apply_modifiers: BoolProperty(
        name="Apply Modifiers",
        description="Apply modifiers on objects before exporting mesh (Non destructive)",
        default=True
    )

    apply_unit_scale: BoolProperty(
        name="Apply Unit Scale",
        description="Apply the unit scale setting to the exported mesh and transform data",
        default=True
    )

    alphabetic_uvs: BoolProperty(
        name="Alphabetic UV's",
        description="UV's will be exported in  alphabetic order instead of list order "
                    "(To get around not having reordering of UV's in blender)",
        default=False
    )

    object_types_to_export: EnumProperty(
        name="Object types",
        description="Select which objects should be included in the exported",
        items=(
            ('EMPTY', "Empty", "Export empties"),
            ('CAMERA', "Camera", "Export cameras"),
            ('LIGHT', "Light", "Export lights"),
            ('MESH', "Mesh", "Export meshes"),
            ('ARMATURE', "Armatures", "Export armatures, used for skinned meshes")
        ),
        options={'ENUM_FLAG'},
        default={'EMPTY', 'CAMERA', 'LIGHT', 'MESH', 'ARMATURE'},
    )

    features_to_export: EnumProperty(
        name="Features",
        description="Select which features should be enabled for the export",
        items=(
            ('MERGE_GROUPS', "Merge Groups", "Export merge groups"),
            ('SKINNED_MESHES', "Skinned Meshes", "Bind meshes to the bones of an armature in i3d. If disabled, "
                                                 "the armature and bone structure will still be exported, "
                                                 "but the meshes wont be bound to it")
        ),
        options={'ENUM_FLAG'},
        default={'MERGE_GROUPS', 'SKINNED_MESHES'},
    )

    collapse_armatures: BoolProperty(
        name="Collapse Armatures",
        description="If enabled the armature itself will get exported as a transformgroup, "
                    "where all its bones are organized as children. "
                    "If not then the armatures parent will be used",
        default=True
    )

    copy_files: BoolProperty(
        name="Copy Files",
        description="Copies the files to have them together with the i3d file. Structure is determined by 'File "
                    "Structure' parameter. If turned off files are referenced by their absolute path instead."
                    "Files from the FS data folder are always converted to relative $data\\shared\\path\\to\\file.",
        default=True
    )

    overwrite_files: BoolProperty(
        name="Overwrite Files",
        description="Overwrites files if they already exist, currently it is only evaluated for material files!",
        default=True
    )

    file_structure: EnumProperty(
        name="File Structure",
        description="Determine the file structure of the copied files",
        items=(
            ('FLAT', "Flat", "The hierarchy is flattened, everything is in the same folder as the i3d"),
            ('BLENDER', "Blender", "The hierarchy is mimiced from around the blend file"),
            ('MODHUB', "Modhub", "The hierarchy is setup according to modhub guidelines, sorted by filetype")
        ),
        default='MODHUB'
    )

    verbose_output: BoolProperty(
        name="Verbose Output",
        description="Print out info to console",
        default=True
    )

    log_to_file: BoolProperty(
        name="Generate logfile",
        description="Generates a log file in the same folder as the exported i3d",
        default=True
    )

    i3d_mapping_file_path: StringProperty(
        name="XML File",
        description="Pick the file where you wish the exporter to export i3d-mappings. The file should be xml and"
                    "contain an '<i3dMapping> somewhere in the file",
        subtype='FILE_PATH',
        default=''
    )

    i3d_mapping_overwrite_mode: EnumProperty(
        name="Overwrite Mode",
        description="Determine how the i3d mapping is updated",
        items=(
            ('CLEAN', "Clean", "Deletes any existing i3d mappings"),
        ),
        default='CLEAN'
    )

    object_sorting_prefix: StringProperty(
        name="Sorting Prefix",
        description="To allow some form of control over the output ordering of the objects in the I3D file it is possible to have the exporter use anything preceeding this keyin the object name as the means for sorting the objects, while also removing this from the final object name. The key can be anything and even multiple characters to allow as much flexibility as possible. To disable the functionality just set the string to nothing",
        default=":"
    )

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

        if status['success']:
            self.report({'INFO'}, f"I3D Export Successful! It took {status['time']:.3f} seconds")
        else:
            self.report({'ERROR'}, "I3D Export Failed! Check console/log for error(s)")

        # Since it is single threaded, this warning wouldn't be sent before the exported starts exporting.
        # So it can't come before the export and it drowns if the export time comes after it.
        if bpy.context.preferences.addons['i3dio'].preferences.fs_data_path == '':
            self.report({'WARNING'},
                        "FS Data folder path is not set, "
                        "see https://stjerneidioten.github.io/"
                        "I3D-Blender-Addon/installation/setup/setup.html#fs-data-folder")

        return {'FINISHED'}        
    
    def draw(self, context):
        pass


# File -> Export item
def menu_func_export(self, context):
    self.layout.operator(I3D_IO_OT_export.bl_idname, text="I3D (.i3d)")


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

        layout.prop(bpy.context.scene.i3dio, 'selection')
        layout.prop(bpy.context.scene.i3dio, 'object_sorting_prefix')


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
        row.prop(bpy.context.scene.i3dio, 'binarize_i3d')
        if bpy.context.preferences.addons['i3dio'].preferences.i3d_converter_path == '':
            row.enabled = False
        else:
            row.enabled = True            
        
        row = layout.row()
        row.prop(bpy.context.scene.i3dio, 'keep_collections_as_transformgroups')

        row = layout.row()
        row.prop(bpy.context.scene.i3dio, 'apply_modifiers')

        row = layout.row()
        row.prop(bpy.context.scene.i3dio, 'apply_unit_scale')

        row = layout.row()
        row.prop(bpy.context.scene.i3dio, 'alphabetic_uvs')

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
        row.prop(bpy.context.scene.i3dio, 'collapse_armatures')

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

        layout.prop(bpy.context.scene.i3dio, 'verbose_output')
        layout.prop(bpy.context.scene.i3dio, 'log_to_file')


@register
class I3D_IO_PT_i3d_mapping_attributes(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_label = "I3D Mapping Options"
    bl_context = 'scene'

    @classmethod
    def poll(cls, context):
        return True

    def draw(self, context):
        layout = self.layout
        layout.prop(bpy.context.scene.i3dio, 'i3d_mapping_file_path')


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.i3dio = PointerProperty(type=I3DExportUIProperties)


def unregister():
    del bpy.types.Scene.i3dio
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
