import bpy
from bl_operators.presets import AddPresetBase
from bpy.types import Operator, Panel

from ..i3d_attributes.light import I3DNodeLightAttributes
from ..i3d_attributes.resolve import make_value_reader
from . import presets
from .helper_functions import i3d_property


class I3D_IO_PT_Light_Presets(presets.PresetPanel, Panel):
    bl_label = "Light Presets"
    preset_operator = "script.execute_preset"
    preset_add_operator = "i3dio.add_light_preset"

    @property
    def preset_subdir(self):
        return presets.PresetSubdir() / 'light'


class I3D_IO_OT_Light_Add_Preset(AddPresetBase, Operator):
    bl_idname = "i3dio.add_light_preset"
    bl_label = "Add a Light Preset"
    preset_menu = "I3D_IO_PT_Light_Presets"

    @property
    def preset_values(self):
        return presets.schema_preset_values("bpy.context.object.data.i3d_attributes", I3DNodeLightAttributes.i3d_schema)

    preset_subdir = I3D_IO_PT_Light_Presets.preset_subdir


class I3D_IO_PT_light_attributes(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_label = "I3D Light Attributes"
    bl_context = 'data'

    @classmethod
    def poll(cls, context):
        return context.light

    def draw_header_preset(self, context):
        I3D_IO_PT_Light_Presets.draw_panel_header(self.layout)

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.alignment = 'RIGHT'
        light = context.light
        # Display unavailable tracked values without logging on every redraw.
        read_value = make_value_reader(
            light.i3d_attributes, I3DNodeLightAttributes.i3d_schema, owner=light, on_error=lambda _source, _error: None
        )

        i3d_property(layout, light.i3d_attributes, 'type_of_light', light, read_value=read_value)
        i3d_property(layout, light.i3d_attributes, "emit_diffuse", light, read_value=read_value)
        i3d_property(layout, light.i3d_attributes, "emit_specular", light, read_value=read_value)
        i3d_property(layout, light.i3d_attributes, "scattering", light, read_value=read_value)
        i3d_property(layout, light.i3d_attributes, 'range', light, read_value=read_value)
        i3d_property(layout, light.i3d_attributes, 'color', light, read_value=read_value)

        i3d_property(layout, light.i3d_attributes, 'cone_angle', light, read_value=read_value)
        i3d_property(layout, light.i3d_attributes, 'drop_off', light, read_value=read_value)

        i3d_property(layout, light.i3d_attributes, "cast_shadow_map", light, read_value=read_value)
        i3d_property(layout, light.i3d_attributes, "shadow_map_bias", light, read_value=read_value)
        i3d_property(layout, light.i3d_attributes, "shadow_map_slope_scale_bias", light, read_value=read_value)
        i3d_property(layout, light.i3d_attributes, "shadow_map_slope_clamp", light, read_value=read_value)
        i3d_property(layout, light.i3d_attributes, "shadow_map_resolution", light, read_value=read_value)
        i3d_property(layout, light.i3d_attributes, "shadow_map_perspective", light, read_value=read_value)
        i3d_property(layout, light.i3d_attributes, "shadow_far_distance", light, read_value=read_value)
        i3d_property(layout, light.i3d_attributes, "shadow_extrusion_distance", light, read_value=read_value)
        i3d_property(layout, light.i3d_attributes, "shadow_map_num_splits", light, read_value=read_value)
        i3d_property(layout, light.i3d_attributes, "split_distance_1", light, read_value=read_value)
        i3d_property(layout, light.i3d_attributes, "split_distance_2", light, read_value=read_value)
        i3d_property(layout, light.i3d_attributes, "split_distance_3", light, read_value=read_value)
        i3d_property(layout, light.i3d_attributes, "split_distance_4", light, read_value=read_value)


_CLASSES = (I3D_IO_PT_Light_Presets, I3D_IO_OT_Light_Add_Preset, I3D_IO_PT_light_attributes)
register, unregister = bpy.utils.register_classes_factory(_CLASSES)
