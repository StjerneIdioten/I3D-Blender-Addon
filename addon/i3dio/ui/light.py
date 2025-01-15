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
                                                   'SUN': 'directional',
                                                   'SPOT': 'spot',
                                                   'AREA': 'directional'}
                                       }
                          },
        'emit_diffuse': {'name': 'emitDiffuse', 'default': True},
        'emit_specular': {'name': 'emitSpecular', 'default': True},
        'scattering': {'name': 'scattering', 'default': False,
                       'depends': [{'name': 'type_of_light', 'value': 'directional'}]},
        'range': {'name': 'range', 'default': 1, 'tracking': {'member_path': 'cutoff_distance'}},
        'color': {'name': 'color', 'default': (1.0, 1.0, 1.0), 'tracking': {'member_path': 'color'}},
        'cone_angle': {'name': 'coneAngle', 'default': 1.047198, 'type': 'ANGLE',
                       'depends': [{'name': 'type_of_light', 'value': 'spot'}],
                       'tracking': {'member_path': 'spot_size'}
                       },
        'drop_off': {'name': 'dropOff', 'default': 4, 'depends': [{'name': 'type_of_light', 'value': 'spot'}]},
        'cast_shadow_map': {'name': 'castShadowMap', 'default': False, 'tracking': {'member_path': 'use_shadow'}},
        'shadow_map_bias': {'name': 'depthMapBias', 'default': 0.005,
                            'depends': [{'name': 'cast_shadow_map', 'value': True}]},
        'shadow_map_slope_scale_bias': {'name': 'depthMapSlopeScaleBias', 'default': 0.005,
                                        'depends': [{'name': 'cast_shadow_map', 'value': True}]},
        'shadow_map_slope_clamp': {'name': 'depthMapSlopeClamp', 'default': 0.02,
                                           'depends': [{'name': 'cast_shadow_map', 'value': True}]},
        'shadow_map_resolution': {'name': 'depthMapResolution', 'default': '512',
                                  'depends': [{'name': 'cast_shadow_map', 'value': True}]},
        'shadow_map_perspective': {'name': 'shadowPerspective', 'default': False,
                                   'depends': [{'name': 'cast_shadow_map', 'value': True}]},
        'shadow_far_distance': {'name': 'shadowFarDistance', 'default': 80,
                                'depends': [{'name': 'cast_shadow_map', 'value': True}]},
        'shadow_extrusion_distance': {'name': 'shadowExtrusionDistance', 'default': 200,
                                      'depends': [{'name': 'cast_shadow_map', 'value': True}]},
        'shadow_map_num_splits': {'name': 'numShadowMapSplits', 'default': '1',
                                  'depends': [{'name': 'cast_shadow_map', 'value': True}]},
        'split_distance_1': {'name': 'shadowMapSplitDistance0', 'default': 80,
                             'depends': [{'name': 'shadow_map_num_splits', 'value': '4'},
                                         {'name': 'cast_shadow_map', 'value': True}]},
        'split_distance_2': {'name': 'shadowMapSplitDistance1', 'default': 80,
                             'depends': [{'name': 'shadow_map_num_splits', 'value': '4'},
                                         {'name': 'cast_shadow_map', 'value': True}]},
        'split_distance_3': {'name': 'shadowMapSplitDistance2', 'default': 80,
                             'depends': [{'name': 'shadow_map_num_splits', 'value': '4'},
                                         {'name': 'cast_shadow_map', 'value': True}]},
        'split_distance_4': {'name': 'shadowMapSplitDistance3', 'default': 80,
                             'depends': [{'name': 'shadow_map_num_splits', 'value': '4'},
                                         {'name': 'cast_shadow_map', 'value': True}]},

    }

    type_of_light: EnumProperty(
        name="Type",
        description="Which type of light is this?",
        items=[
            ('point', 'Point', "Point Light"),
            ('spot', 'Spot', "Spot Light"),
            ('directional', 'Directional', "Directional Light")
        ],
        default=i3d_map['type_of_light']['default']
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
        description="Depends on 'Type' being 'Directional'",
        default=i3d_map['scattering']['default']
    )

    range: FloatProperty(
        name="Range",
        description="Range",
        default=i3d_map['range']['default'],
        precision=3,
        min=0.01,
        max=i3d_max,
        soft_min=0.01,
        soft_max=65535,
    )

    range_tracking: BoolProperty(
        name="Custom Distance",
        description="Can be found at: Object Data Properties -> Light -> Custom Distance -> Distance",
        default=True
    )

    cone_angle: FloatProperty(
        name="Cone Angle",
        description="Depends on 'Type' being 'Spot'",
        default=i3d_map['cone_angle']['default'],
        precision=3,
        unit='ROTATION',
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
        description="Depends on 'Type' being 'Spot'",
        default=i3d_map['drop_off']['default'],
        precision=3,
        min=0,
        max=5,
        soft_min=0,
        soft_max=5
    )

    cast_shadow_map: BoolProperty(
        name="Cast Shadow Map",
        description="Cast Shadow Map",
        default=i3d_map['cast_shadow_map']['default'],
    )

    cast_shadow_map_tracking: BoolProperty(
        name="Shadows",
        description="Can be found at: Object Data Properties -> Shadow",
        default=True,
    )

    shadow_map_bias: FloatProperty(
        name="Shadow Map Bias",
        description="Depends on 'Cast Shadow Map' being 'True'",
        default=i3d_map['shadow_map_bias']['default'],
        precision=3,
        min=0.0,
        max=10.0
    )

    shadow_map_slope_scale_bias: FloatProperty(
        name="Shadow Map Slope Scale Bias",
        description="Depends on 'Cast Shadow Map' being 'True'",
        default=i3d_map['shadow_map_slope_scale_bias']['default'],
        precision=3,
        min=-i3d_max,
        max=i3d_max,
        soft_min=-10,
        soft_max=10
    )

    shadow_map_slope_clamp: FloatProperty(
        name="Shadow Map Slope Clamp",
        description="Depends on 'Cast Shadow Map' being 'True'",
        default=i3d_map['shadow_map_slope_clamp']['default'],
        precision=3,
        min=-i3d_max,
        max=i3d_max,
        soft_min=-10,
        soft_max=10
    )

    shadow_map_resolution: EnumProperty(
        name="Shadow Map Resolution",
        description="Depends on 'Cast Shadow Map' being 'True'",
        items=[
            ('256', '256', "256"),
            ('512', '512', "512"),
            ('1024', '1024', "1024"),
            ('2048', '2048', "2048"),
            ('4096', '4096', "4096"),
        ],
        default=i3d_map['shadow_map_resolution']['default']
    )

    shadow_map_perspective: BoolProperty(
        name="Shadowmap Perspective",
        description="Depends on 'Cast Shadow Map' being 'True'",
        default=i3d_map['shadow_map_perspective']['default'],
    )

    shadow_far_distance: FloatProperty(
        name="Shadow Far Distance",
        description="Depends on 'Cast Shadow Map' being 'True'",
        default=i3d_map['shadow_far_distance']['default'],
        precision=3,
        min=0,
        max=i3d_max,
        soft_min=0,
        soft_max=65535
    )

    shadow_extrusion_distance: FloatProperty(
        name="Shadow Extrusion Distance",
        description="Depends on 'Cast Shadow Map' being 'True'",
        default=i3d_map['shadow_extrusion_distance']['default'],
        precision=3,
        min=0,
        max=i3d_max,
        soft_min=0,
        soft_max=100
    )

    shadow_map_num_splits: EnumProperty(
        name="Shadow Map Num Splits",
        description="Depends on 'Cast Shadow Map' being 'True'",
        items=[
            ('1', '1', "1"),
            ('4', '4', "4")
        ],
        default=i3d_map['shadow_map_num_splits']['default']
    )

    split_distance_1: FloatProperty(
        name="Split Distance #1",
        description="Depends on 'Cast Shadow Map' being 'True' and 'Shadow Map Num Splits' being '4'",
        default=i3d_map['split_distance_1']['default'],
        precision=3,
        min=0,
        max=i3d_max,
        soft_min=0,
        soft_max=500
    )

    split_distance_2: FloatProperty(
        name="Split Distance #2",
        description="Depends on 'Cast Shadow Map' being 'True' and 'Shadow Map Num Splits' being '4'",
        default=i3d_map['split_distance_2']['default'],
        precision=3,
        min=0,
        max=i3d_max,
        soft_min=0,
        soft_max=500
    )

    split_distance_3: FloatProperty(
        name="Split Distance #3",
        description="Depends on 'Cast Shadow Map' being 'True' and 'Shadow Map Num Splits' being '4'",
        default=i3d_map['split_distance_3']['default'],
        precision=3,
        min=0,
        max=i3d_max,
        soft_min=0,
        soft_max=500
    )

    split_distance_4: FloatProperty(
        name="Split Distance #4",
        description="Depends on 'Cast Shadow Map' being 'True' and 'Shadow Map Num Splits' being '4'",
        default=i3d_map['split_distance_4']['default'],
        precision=3,
        min=0,
        max=i3d_max,
        soft_min=0,
        soft_max=500
    )


@register
class I3D_IO_PT_light_attributes(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_label = "I3D Light Attributes"
    bl_context = 'data'

    @classmethod
    def poll(cls, context):
        return context.light

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.alignment = 'RIGHT'
        light = context.light

        i3d_property(layout, light.i3d_attributes, 'type_of_light', light)
        i3d_property(layout, light.i3d_attributes, "emit_diffuse", light)
        i3d_property(layout, light.i3d_attributes, "emit_specular", light)
        i3d_property(layout, light.i3d_attributes, "scattering", light)
        i3d_property(layout, light.i3d_attributes, 'range', light)
        i3d_property(layout, light.i3d_attributes, 'color', light)

        i3d_property(layout, light.i3d_attributes, 'cone_angle', light)
        i3d_property(layout, light.i3d_attributes, 'drop_off', light)

        i3d_property(layout, light.i3d_attributes, "cast_shadow_map", light)
        i3d_property(layout, light.i3d_attributes, "shadow_map_bias", light)
        i3d_property(layout, light.i3d_attributes, "shadow_map_slope_scale_bias", light)
        i3d_property(layout, light.i3d_attributes, "shadow_map_slope_clamp", light)
        i3d_property(layout, light.i3d_attributes, "shadow_map_resolution", light)
        i3d_property(layout, light.i3d_attributes, "shadow_map_perspective", light)
        i3d_property(layout, light.i3d_attributes, "shadow_far_distance", light)
        i3d_property(layout, light.i3d_attributes, "shadow_extrusion_distance", light)
        i3d_property(layout, light.i3d_attributes, "shadow_map_num_splits", light)
        i3d_property(layout, light.i3d_attributes, "split_distance_1", light)
        i3d_property(layout, light.i3d_attributes, "split_distance_2", light)
        i3d_property(layout, light.i3d_attributes, "split_distance_3", light)
        i3d_property(layout, light.i3d_attributes, "split_distance_4", light)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Light.i3d_attributes = PointerProperty(type=I3DNodeLightAttributes)


def unregister():
    del bpy.types.Light.i3d_attributes
    for cls in classes:
        bpy.utils.unregister_class(cls)
