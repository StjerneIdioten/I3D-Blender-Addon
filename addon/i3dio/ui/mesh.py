import bpy
from bl_operators.presets import AddPresetBase
from bpy.types import Operator, Panel

from ..i3d_attributes.mesh import I3DNodeShapeAttributes
from ..i3d_attributes.resolve import make_value_reader
from . import presets
from .helper_functions import bit_mask_property, i3d_property


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
        attributes = mesh.i3d_attributes
        read_value = make_value_reader(
            attributes, I3DNodeShapeAttributes.i3d_schema, owner=mesh, on_error=lambda _source, _error: None
        )

        layout.separator(type='LINE')
        i3d_property(layout, attributes, "color_export", mesh, read_value=read_value, expand=True)
        layout.separator(type='LINE')
        i3d_property(layout, attributes, "casts_shadows", mesh, read_value=read_value)
        i3d_property(layout, attributes, "receive_shadows", mesh, read_value=read_value)
        i3d_property(layout, attributes, "rendered_in_viewports", mesh, read_value=read_value)
        i3d_property(layout, attributes, "non_renderable", mesh, read_value=read_value)
        i3d_property(layout, attributes, "distance_blending", mesh, read_value=read_value)
        i3d_property(layout, attributes, "is_occluder", mesh, read_value=read_value)
        i3d_property(layout, attributes, "terrain_decal", mesh, read_value=read_value)
        i3d_property(layout, attributes, "cpu_mesh", mesh, read_value=read_value, expand=True)
        i3d_property(layout, attributes, "double_sided", mesh, read_value=read_value)
        i3d_property(layout, attributes, "material_holder", mesh, read_value=read_value)
        bit_mask_property(layout, attributes, "nav_mesh_mask", mesh, read_value=read_value, used_bits=8)
        i3d_property(layout, attributes, "decal_layer", mesh, read_value=read_value)
        i3d_property(layout, attributes, "vertex_compression_range", mesh, read_value=read_value)

        header, panel = layout.panel('i3d_bounding_volume', default_closed=False)
        header.label(text="I3D Bounding Volume")
        if panel:
            i3d_property(panel, attributes, 'bounding_volume_object', mesh, read_value=read_value)


_CLASSES = (
    I3D_IO_PT_Mesh_Presets,
    I3D_IO_OT_Mesh_Add_Preset,
    I3D_IO_PT_shape_attributes,
)
register, unregister = bpy.utils.register_classes_factory(_CLASSES)
