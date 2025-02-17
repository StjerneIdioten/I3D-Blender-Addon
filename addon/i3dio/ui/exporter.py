import bpy

from bpy.props import (
    StringProperty,
    BoolProperty,
    EnumProperty,
    PointerProperty,
    CollectionProperty
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
class I3DShaderSearchPath(bpy.types.PropertyGroup):
    path: StringProperty(
        name="Search Path",
        description="Folder to search for shaders",
        subtype='FILE_PATH',
        default=''
    )


@register
class I3DExportUIProperties(bpy.types.PropertyGroup):
    # Used when exporting through the file browser
    i3d_mapping_file_path: StringProperty(
        name="XML File",
        description="Pick the file where you wish the exporter to export i3d-mappings. The file should be xml and"
                    "contain an '<i3dMapping> somewhere in the file",
        subtype='FILE_PATH',
        default=''
    )

    shader_extra_paths: CollectionProperty(
        type=I3DShaderSearchPath,
        name="Extra Shader Search Paths",
        description=("A list of extra paths for the exporter to search for valid shader files. "
                     "The paths will be stored relative to the .blend file in an attempt to keep them portable.")
    )


@register
@orientation_helper(axis_forward='-Z', axis_up='Y')
class I3D_IO_OT_export(Operator, ExportHelper):
    """Save i3d file"""
    bl_idname = "export_scene.i3d"
    bl_label = "Export I3D"
    bl_options = {'UNDO', 'PRESET'}  # 'PRESET' enables the preset dialog for saving settings as preset

    filename_ext = xml_i3d.file_ending
    filter_glob: StringProperty(default=f"*{xml_i3d.file_ending}",
                                options={'HIDDEN'},
                                maxlen=255,
                                )

    # List of operator properties, the attributes will be assigned
    # to the class instance from the operator settings before calling.

    collection: StringProperty(
        name="Source Collection",
        description="Export only objects from this collection (and its children)",
        default="",
    )

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
            ('CURVE', "Curve", "Export curves"),
            ('ARMATURE', "Armatures", "Export armatures, used for skinned meshes")
        ),
        options={'ENUM_FLAG'},
        default={'EMPTY', 'CAMERA', 'LIGHT', 'MESH', 'CURVE', 'ARMATURE'},
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

    object_sorting_prefix: StringProperty(
        name="Sorting Prefix",
        description="To allow some form of control over the output ordering of the objects in the I3D file it is "
        "possible to have the exporter use anything preceeding this keyin the object name as the means for "
        "sorting the objects, while also removing this from the final object name. "
        "The key can be anything and even multiple characters to allow as much flexibility as possible. "
        "To disable the functionality just set the string to nothing",
        default=":"
    )

    i3d_mapping_file_path: StringProperty(
        name="XML File",
        description="Pick the file where you wish the exporter to export i3d-mappings. The file should be xml and"
                    "contain an '<i3dMapping> somewhere in the file",
        subtype='FILE_PATH',
        default=''
    )

    scene_key = "i3dio_export_settings"

    def save_settings_to_scene(self, context):
        # Save the settings to the scene property since properties are no longer stored directly in scene
        # This is done to allow the settings to be saved between sessions
        # Do not save collection prop since then we can use that as check if it was exported through file browser
        # Use i3d_mapping_file_path from context.scene.i3dio instead of self.i3d_mapping_file_path
        ACCEPTED_PROPERTIES = [
            "selection",
            "binarize_i3d",
            "keep_collections_as_transformgroups",
            "apply_modifiers",
            "apply_unit_scale",
            "alphabetic_uvs",
            "object_types_to_export",
            "features_to_export",
            "collapse_armatures",
            "copy_files",
            "overwrite_files",
            "file_structure",
            "verbose_output",
            "log_to_file",
            "object_sorting_prefix",
        ]
        export_props = {}
        for prop in ACCEPTED_PROPERTIES:
            if hasattr(self, prop):
                value = getattr(self, prop)
                if isinstance(value, set):
                    export_props[prop] = list(value)
                else:
                    export_props[prop] = value
        context.scene[self.scene_key] = export_props

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False  # No animation.

        is_file_browser = context.space_data.type == 'FILE_BROWSER'

        export_main(layout, self, is_file_browser)
        export_options(layout, self)
        export_files(layout, self)
        export_debug(layout, self)
        if not is_file_browser:
            export_i3d_mapping(layout, self)

    def invoke(self, context, event):
        # To load the settings from the scene property to the operator
        settings = context.scene.get(self.scene_key, {})
        if settings:
            for key, value in settings.items():
                if hasattr(self, key):
                    current_value = getattr(self, key)
                    if isinstance(current_value, set) and isinstance(value, list):
                        setattr(self, key, set(value))
                    else:
                        setattr(self, key, value)
        return ExportHelper.invoke(self, context, event)

    def execute(self, context):
        # If not exporting a collection, save settings to scene props for file browser exports.
        # Also save i3d_mapping_file_path from context.scene.i3dio to avoid multiple checks later.
        if not self.collection:
            self.save_settings_to_scene(context)
            settings = self.as_keywords(ignore=("filepath", "filter_glob"))
            settings['i3d_mapping_file_path'] = context.scene.i3dio.i3d_mapping_file_path
        else:
            settings = self.as_keywords(ignore=("filepath", "filter_glob"))

        status = exporter.export_blend_to_i3d(self, self.filepath, self.axis_forward, self.axis_up, settings)

        if status['success']:
            self.report({'INFO'}, f"I3D Export Successful! It took {status['time']:.3f} seconds")
        else:
            self.report({'ERROR'}, "I3D Export Failed! Check console/log for error(s)")

        # Since it is single threaded, this warning wouldn't be sent before the exported starts exporting.
        # So it can't come before the export and it drowns if the export time comes after it.
        if context.preferences.addons['i3dio'].preferences.fs_data_path == '':
            self.report({'WARNING'},
                        "FS Data folder path is not set, "
                        "see https://stjerneidioten.github.io/"
                        "I3D-Blender-Addon/installation/setup/setup.html#fs-data-folder")

        return {'FINISHED'}


def export_main(layout, operator, is_file_browser):
    if is_file_browser:
        layout.prop(operator, 'selection')
    layout.prop(operator, 'object_sorting_prefix')


def export_options(layout, operator):
    header, body = layout.panel("I3D_export_options", default_closed=False)
    header.label(text="Export Options")
    if body:
        body.use_property_split = False
        col = body.column()
        col.enabled = bool(bpy.context.preferences.addons['i3dio'].preferences.i3d_converter_path)
        col.prop(operator, 'binarize_i3d')

        col = body.column()
        col.prop(operator, 'keep_collections_as_transformgroups')
        col.prop(operator, 'apply_modifiers')
        col.prop(operator, 'apply_unit_scale')
        col.prop(operator, 'alphabetic_uvs')

        box = body.box()
        row = box.row()
        row.label(text='Object types to export:')
        column = box.column()
        column.props_enum(operator, 'object_types_to_export')

        box = body.box()
        row = box.row()
        row.label(text='Features to enable:')
        column = box.column()
        column.props_enum(operator, 'features_to_export')
        row = box.row()
        row.prop(operator, 'collapse_armatures')

        body.prop(operator, "axis_forward")
        body.prop(operator, "axis_up")


def export_files(layout, operator):
    header, body = layout.panel("I3D_export_files", default_closed=False)
    header.label(text="File Options")
    if body:
        body.use_property_split = False
        body.prop(operator, 'copy_files')
        body.prop(operator, 'overwrite_files')
        body.enabled = operator.copy_files
        body.prop(operator, 'file_structure')


def export_debug(layout, operator):
    header, body = layout.panel("I3D_export_debug", default_closed=False)
    header.label(text="Debug Options")
    if body:
        body.use_property_split = False
        body.prop(operator, 'verbose_output')
        body.prop(operator, 'log_to_file')


def export_i3d_mapping(layout, operator):
    header, body = layout.panel("I3D_export_i3d_mapping", default_closed=False)
    header.label(text="I3D Mapping Options")
    if body:
        body.use_property_split = False
        body.prop(operator, 'i3d_mapping_file_path')


@register
class IO_FH_i3d(bpy.types.FileHandler):
    bl_idname = "IO_FH_i3d"
    bl_label = "I3D"
    bl_export_operator = "export_scene.i3d"
    bl_file_extensions = ".i3d"

    @classmethod
    def poll_drop(cls, context):
        pass


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
        layout.prop(context.scene.i3dio, 'i3d_mapping_file_path')


# File -> Export item
def menu_func_export(self, context):
    self.layout.operator(I3D_IO_OT_export.bl_idname, text="I3D (.i3d)")


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.i3dio = PointerProperty(type=I3DExportUIProperties)


def unregister():
    del bpy.types.Scene.i3dio
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
