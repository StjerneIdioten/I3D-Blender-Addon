import bpy
from bpy.props import (
    StringProperty,
    BoolProperty
)

from bpy_extras.io_utils import (
    ExportHelper,
    orientation_helper
)

from bpy.types import (
    Operator
)


class TEST_ADDON_OT_center(Operator):
    bl_idname = "view3d.cursor_center"
    bl_label = "Simple operator"
    bl_description = "Center 3d cursor"
    bl_options = {"REGISTER", "UNDO"}

    testval: bpy.props.IntProperty(name="Test Val", default=2, min=1, max=100)

    def execute(self, context):
        bpy.ops.view3d.snap_cursor_to_center()
        print(self.testval)
        return {'FINISHED'}


class TEST_ADDON_OT_export_i3d(Operator, ExportHelper):
    """Save i3d file"""
    bl_idname = "export_scene.i3d"
    bl_label = "Export I3D"

    filename_ext = ".i3d"
    filter_glob: StringProperty(default="*.i3d",
                                options={'HIDDEN'},
                                maxlen=255,
                                )

    use_selection: BoolProperty(
        name="Selection Only",
        description="Only export the selected object",
        default=False,
    )

    def execute(self, context):
        print("Path: " + self.filepath + ', Selection Only: ' + str(self.use_selection))
        return {'FINISHED'}

