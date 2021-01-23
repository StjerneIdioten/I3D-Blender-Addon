import bpy
from bpy.types import (
    Panel
)

from bpy.props import (
    PointerProperty,
    FloatProperty,
    EnumProperty,
    FloatVectorProperty,
    BoolProperty
)

from .helper_functions import i3d_property
from ..xml_i3d import i3d_max

classes = []


def register(cls):
    classes.append(cls)
    return cls


@register
class I3DNodeLightAttributes(bpy.types.PropertyGroup):
    i3d_map = {
        'type_of_light': {'name': 'type',
                          'default': 'point',
                          'tracking': {'member_path': 'type',
                                       'mapping': {'POINT': 'point',
                                                   'SUN': 'point',
                                                   'SPOT': 'spot',
                                                   'AREA': 'directional'}
                                       }
                          },
        'emit_diffuse': {'name': 'emitDiffuse', 'default': True},
        'emit_specular': {'name': 'emitSpecular', 'default': True},
        'scattering': {'name': 'scattering', 'default': False},
        'range': {'name': 'range', 'default': 1, 'tracking': {'member_path': 'cutoff_distance'}},
        'color': {'name': 'color', 'default': (1.0, 1.0, 1.0), 'tracking': {'member_path': 'color'}},
        'cone_angle': {'name': 'coneAngle', 'default': 60, 'type': 'ANGLE', 'depends': {'name': 'type_of_light', 'value': 'spot'},
                       'tracking': {'member_path': 'spot_size'}
                       },
        'drop_off': {'name': 'dropOff', 'default': 4, 'depends': {'name': 'type_of_light', 'value': 'spot'}},
        'depth_map_bias': {'name': 'depthMapBias', 'default': 0.0012},
        'depth_map_slope_scale_bias': {'name': 'depthMapSlopeScaleBias', 'default': 2.0},
    }

    type_of_light: EnumProperty(
        name="Type",
        description="Which type of light is this?",
        items=[
            ('point', 'Point', "Point Light"),
            ('spot', 'Spot', "Spot Light"),
            ('directional', 'Directional', "Directional Light")
        ],
        default='point'
    )

    type_of_light_tracking: BoolProperty(
        name="Type",
        description="Can be found at: Object Data Properties -> Light",
        default=True
    )

    color: FloatVectorProperty(
        name="Color",
        description="The Color of light",
        min=0,
        max=1000,
        soft_min=0,
        soft_max=500,
        size=3,
        precision=3,
        subtype='COLOR',
        default=i3d_map['color']['default']
        )

    color_tracking: BoolProperty(
        name="Color",
        description="Can be found at: Object Data Properties -> Light -> Color",
        default=True
    )

    emit_diffuse: BoolProperty(
        name="Diffuse",
        description="Diffuse",
        default=i3d_map['emit_diffuse']['default']
    )

    emit_specular: BoolProperty(
        name="Specular",
        description="Specular",
        default=i3d_map['emit_specular']['default']
    )

    scattering: BoolProperty(
        name="Light Scattering",
        description="Light Scattering",
        default=i3d_map['scattering']['default']
    )

    range: FloatProperty(
        name="Range",
        description="Range",
        default=i3d_map['range']['default'],
        min=0.01,
        max=i3d_max,
        soft_min=0.01,
        soft_max=65535
    )

    range_tracking: BoolProperty(
        name="Custom Distance",
        description="Can be found at: Object Data Properties -> Light -> Custom Distance -> Distance",
        default=True
    )

    cone_angle: FloatProperty(
        name="Cone Angle",
        description="Cone Angle",
        default=i3d_map['cone_angle']['default'],
        min=0,
        max=i3d_max,
        soft_min=0,
        soft_max=180
    )

    cone_angle_tracking: BoolProperty(
        name="Spot Size",
        description="Can be found at: Object Data Properties -> Light -> Spot Shape -> Size",
        default=True,
    )

    drop_off: FloatProperty(
        name="Drop Off",
        description="Drop Off",
        default=i3d_map['drop_off']['default'],
        min=0,
        max=5,
        soft_min=0,
        soft_max=5
    )

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
        layout.alignment = 'RIGHT'
        obj = bpy.context.active_object.data

        i3d_property(layout, obj.i3d_attributes, 'type_of_light', obj)
        layout.prop(obj.i3d_attributes, "emit_diffuse")
        layout.prop(obj.i3d_attributes, "emit_specular")
        layout.prop(obj.i3d_attributes, "scattering")
        i3d_property(layout, obj.i3d_attributes, 'range', obj)
        i3d_property(layout, obj.i3d_attributes, 'color', obj)
        i3d_property(layout, obj.i3d_attributes, 'cone_angle', obj)

        i3d_property(layout, obj.i3d_attributes, 'drop_off', obj)
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
