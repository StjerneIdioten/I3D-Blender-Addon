#!/usr/bin/env python3

"""
    ##### BEGIN GPL LICENSE BLOCK #####
  This program is free software; you can redistribute it and/or
  modify it under the terms of the GNU General Public License
  as published by the Free Software Foundation; either version 2
  of the License, or (at your option) any later version.
  This program is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU General Public License for more details.
  You should have received a copy of the GNU General Public License
  along with this program; if not, write to the Free Software Foundation,
  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
 ##### END GPL LICENSE BLOCK #####
"""

import time
import bpy
from bpy.props import (
    StringProperty,
    BoolProperty
)

from bpy_extras.io_utils import (
    ExportHelper
)

from bpy.types import (
    Operator,
    Panel,
    PropertyGroup
)

from . import i3d_exporter


class I3D_IO_OT_export(Operator, ExportHelper):
    """Save i3d file"""
    bl_idname = "export_scene.i3d"
    bl_label = "Export I3D"
    bl_options = {'PRESET'}

    filename_ext = ".i3d"
    filter_glob: StringProperty(default="*.i3d",
                                options={'HIDDEN'},
                                maxlen=255,
                                )

    use_selection: BoolProperty(
        name="Export Selected",
        description="Only export the selected object",
        default=False,
    )

    export_ik1: BoolProperty(
        name="IK1",
        description="Export the inverse kinematics",
        default=False,
    )

    export_animations: BoolProperty(
        name="Animations",
        description="Export the animations",
        default=False,
    )

    export_shapes: BoolProperty(
        name="Shapes",
        description="Export the shapes",
        default=False,
    )

    # Add remaining properties from original addon as they get implemented

    shape_normals: BoolProperty(
        name="Normals",
        description="Export shape normals",
        default=False,
    )

    shape_uvs: BoolProperty(
        name="UVs",
        description="Export shape UVs",
        default=False,
    )

    # Add remaining properties from original addon as they get implemented

    misc_verbose: BoolProperty(
        name="Verbose",
        description="Verbose output to console",
        default=False,
    )

    misc_relative_paths: BoolProperty(
        name="Relative Paths",
        description="Save relative paths in i3d",
        default=False,
    )

    def execute(self, context):
        print("Exporting to " + self.filepath)
        time_start = time.time()
        exporter = i3d_exporter.Exporter(self.filepath)
        time_elapsed = time.time() - time_start
        print(f"Export took {time_elapsed:.3f} seconds")
        return {'FINISHED'}

    def draw(self, context):
        pass


class I3D_IO_PT_export_main(Panel):
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOL_PROPS'
    bl_label = ""
    bl_parent_id = "FILE_PT_operator"
    bl_options = {'HIDE_HEADER'}

    @classmethod
    def poll(cls, context):
        sfile = context.space_data
        operator = sfile.active_operator

        return operator.bl_idname == "EXPORT_SCENE_OT_i3d"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        sfile = context.space_data
        operator = sfile.active_operator

        layout.prop(operator, "use_selection")


class I3D_IO_PT_export_options(Panel):
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOL_PROPS'
    bl_label = "Export Options"
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
        row.prop(operator, "export_ik1")
        row.prop(operator, "export_animations")


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
        row.prop(operator, "shape_normals")
        row.prop(operator, "shape_uvs")


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
        row.prop(operator, "misc_verbose")
        row.prop(operator, "misc_relative_paths")


classes = (I3D_IO_OT_export,
           I3D_IO_PT_export_main,
           I3D_IO_PT_export_options,
           I3D_IO_PT_export_shape,
           I3D_IO_PT_export_misc
           )


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)