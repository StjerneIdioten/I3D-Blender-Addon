import bpy
from bpy.types import (
    Panel
)

from bpy.props import (
    PointerProperty,
    FloatProperty,
)

classes = []


def register(cls):
    classes.append(cls)
    return cls


@register
class I3DNodeLightAttributes(bpy.types.PropertyGroup):
    i3d_map = {
        'depth_map_bias': {'name': 'depthMapBias', 'default': 0.0012},
        'depth_map_slope_scale_bias': {'name': 'depthMapSlopeScaleBias', 'default': 2.0},
    }

    depth_map_bias: FloatProperty(
        name="Shadow Map Bias",
        description="Shadow Map Bias",
        default=i3d_map['depth_map_bias']['default'],
        min=0.0,
        max=10.0
    )

    depth_map_slope_scale_bias: FloatProperty(
        name="Shadow Map Slope Scale Bias",
        description="Shadow Map Slope Scale Bias",
        default=i3d_map['depth_map_slope_scale_bias']['default'],
        min=-10.0,
        max=10.0
    )


@register
class I3D_IO_PT_light_attributes(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_label = "I3D Light Attributes"
    bl_context = 'data'

    @classmethod
    def poll(cls, context):
        if context.object is not None:
            return context.object.type == 'LIGHT'

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        obj = bpy.context.active_object.data

        layout.prop(obj.i3d_attributes, "depth_map_bias")
        layout.prop(obj.i3d_attributes, "depth_map_slope_scale_bias")


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Light.i3d_attributes = PointerProperty(type=I3DNodeLightAttributes)


def unregister():
    del bpy.types.Light.i3d_attributes
    for cls in classes:
        bpy.utils.unregister_class(cls)
