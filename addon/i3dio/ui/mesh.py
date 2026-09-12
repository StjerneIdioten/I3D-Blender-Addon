import bpy
from bl_operators.presets import AddPresetBase
from bpy.types import Operator, Panel

from ..i3d_attributes.mesh import I3DNodeShapeAttributes
from . import presets


class I3D_IO_PT_Mesh_Presets(presets.PresetPanel, Panel):
    bl_label = "Mesh Presets"
    preset_operator = "script.execute_preset"
    preset_add_operator = "i3dio.add_mesh_preset"

    @property
    def preset_subdir(self):
        return presets.PresetSubdir() / 'mesh'


class I3D_IO_OT_Mesh_Add_Preset(AddPresetBase, Operator):
    bl_idname = "i3dio.add_mesh_preset"
    bl_label = "Add a Mesh Preset"
    preset_menu = "I3D_IO_PT_Mesh_Presets"

    @property
    def preset_values(self):
        return [
            f"bpy.context.object.data.i3d_attributes.{name}"
            for name, _definition in I3DNodeShapeAttributes.i3d_schema.exported()
        ]

    preset_subdir = I3D_IO_PT_Mesh_Presets.preset_subdir


class I3D_IO_PT_shape_attributes(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_label = "I3D Shape Attributes"
    bl_context = 'data'

    @classmethod
    def poll(cls, context):
        return context.mesh

    def draw_header_preset(self, context):
        I3D_IO_PT_Mesh_Presets.draw_panel_header(self.layout)

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        mesh = context.mesh

        layout.separator(type='LINE')
        layout.prop(mesh.i3d_attributes, "color_export", expand=True)
        layout.separator(type='LINE')
        layout.prop(mesh.i3d_attributes, "casts_shadows")
        layout.prop(mesh.i3d_attributes, "receive_shadows")
        layout.prop(mesh.i3d_attributes, "rendered_in_viewports")
        layout.prop(mesh.i3d_attributes, "non_renderable")
        layout.prop(mesh.i3d_attributes, "distance_blending")
        layout.prop(mesh.i3d_attributes, "is_occluder")
        layout.prop(mesh.i3d_attributes, "terrain_decal")
        layout.prop(mesh.i3d_attributes, "cpu_mesh", expand=True)
        layout.prop(mesh.i3d_attributes, "double_sided")
        layout.prop(mesh.i3d_attributes, "material_holder")
        row = layout.row()
        row.prop(mesh.i3d_attributes, "nav_mesh_mask")
        op = row.operator('i3dio.bit_mask_editor', text="", icon='THREE_DOTS')
        op.target_prop = "nav_mesh_mask"
        op.used_bits = 8
        layout.prop(mesh.i3d_attributes, "decal_layer")
        layout.prop(mesh.i3d_attributes, "vertex_compression_range")

        header, panel = layout.panel('i3d_bounding_volume', default_closed=False)
        header.label(text="I3D Bounding Volume")
        if panel:
            panel.prop(mesh.i3d_attributes, 'bounding_volume_object')


_CLASSES = (
    I3D_IO_PT_Mesh_Presets,
    I3D_IO_OT_Mesh_Add_Preset,
    I3D_IO_PT_shape_attributes,
)
register, unregister = bpy.utils.register_classes_factory(_CLASSES)
