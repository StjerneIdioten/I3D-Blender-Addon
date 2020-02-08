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

from . import i3d_exporter, i3d_properties


@orientation_helper(axis_forward='-Z', axis_up='Y')
class I3D_IO_OT_export(Operator, ExportHelper):
    """Save i3d file"""
    bl_idname = "export_scene.i3d"
    bl_label = "Export I3D"
    bl_options = {'PRESET'}  # 'PRESET' enables the preset dialog for saving settings as preset

    filename_ext = ".i3d"
    filter_glob: StringProperty(default="*.i3d",
                                options={'HIDDEN'},
                                maxlen=255,
                                )

    # Add remaining properties from original addon as they get implemented

    def execute(self, context):
        print("Exporting to " + self.filepath)
        time_start = time.time()
        exporter = i3d_exporter.Exporter(self.filepath, self.axis_forward, self.axis_up)
        time_elapsed = time.time() - time_start
        print(f"Export took {time_elapsed:.3f} seconds")
        return {'FINISHED'}

    def draw(self, context):
        pass


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

        box = layout.box()
        row = box.row()
        row.label(text='Object types to export')
        column = box.column()
        column.props_enum(bpy.context.scene.i3dio, 'object_types_to_export')

        layout.prop(operator, "axis_forward")
        layout.prop(operator, "axis_up")


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


classes = (I3D_IO_OT_export,
           I3D_IO_PT_export_main,
           I3D_IO_PT_export_options,
           I3D_IO_PT_export_files
           )


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)