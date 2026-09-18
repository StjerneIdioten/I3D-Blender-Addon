import math

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, FloatVectorProperty, PointerProperty

from ..constants import I3D_MAX
from .schema import I3DSchema, TrackingDefinition, exported


class LightProperties:
    type_of_light = exported(
        EnumProperty(
            name='Type',
            description='Which type of light is this?',
            items=[
                ('point', 'Point', 'Point Light'),
                ('spot', 'Spot', 'Spot Light'),
                ('directional', 'Directional', 'Directional Light'),
            ],
            default='point',
        ),
        i3d_name='type',
        i3d_default='point',
        tracking=TrackingDefinition(
            member_path='type',
            toggle=BoolProperty(
                name='Type', description='Can be found at: Object Data Properties -> Light', default=True
            ),
            mapping={'POINT': 'point', 'SUN': 'directional', 'SPOT': 'spot', 'AREA': 'directional'},
        ),
    )
    color = exported(
        FloatVectorProperty(
            name='Color',
            description='The Color of light',
            min=0,
            max=1000,
            soft_min=0,
            soft_max=500,
            size=3,
            precision=3,
            subtype='COLOR',
            default=(1.0, 1.0, 1.0),
        ),
        i3d_name='color',
        i3d_default=(1.0, 1.0, 1.0),
        tracking=TrackingDefinition(
            member_path='color',
            toggle=BoolProperty(
                name='Color', description='Can be found at: Object Data Properties -> Light -> Color', default=True
            ),
        ),
    )
    emit_diffuse = exported(
        BoolProperty(name='Diffuse', description='Diffuse', default=True),
        i3d_name='emitDiffuse',
        i3d_default=True,
    )
    emit_specular = exported(
        BoolProperty(name='Specular', description='Specular', default=True),
        i3d_name='emitSpecular',
        i3d_default=True,
    )
    scattering = exported(
        BoolProperty(name='Light Scattering', description='Enable light scattering for this light', default=False),
        i3d_name='scattering',
        i3d_default=False,
        requires=(type_of_light.equals('directional'),),
    )
    range = exported(
        FloatProperty(
            name='Range',
            description='Range',
            default=1,
            precision=3,
            min=0.01,
            max=I3D_MAX,
            soft_min=0.01,
            soft_max=65535,
        ),
        i3d_name='range',
        i3d_default=1,
        tracking=TrackingDefinition(
            member_path='cutoff_distance',
            toggle=BoolProperty(
                name='Custom Distance',
                description='Can be found at: Object Data Properties -> Light -> Custom Distance -> Distance',
                default=True,
            ),
        ),
    )
    cone_angle = exported(
        FloatProperty(
            name='Cone Angle',
            description='Opening angle of the spotlight cone',
            default=1.047198,
            precision=3,
            unit='ROTATION',
            min=0,
            max=I3D_MAX,
            soft_min=0,
            soft_max=180,
        ),
        i3d_name='coneAngle',
        i3d_default=1.047198,
        converter=math.degrees,
        requires=(type_of_light.equals('spot'),),
        tracking=TrackingDefinition(
            member_path='spot_size',
            toggle=BoolProperty(
                name='Spot Size',
                description='Can be found at: Object Data Properties -> Light -> Spot Shape -> Size',
                default=True,
            ),
        ),
    )
    drop_off = exported(
        FloatProperty(
            name='Drop Off',
            description='Intensity falloff of the spotlight',
            default=4,
            precision=3,
            min=0,
            max=I3D_MAX,
            soft_min=0,
            soft_max=5,
        ),
        i3d_name='dropOff',
        i3d_default=4,
        requires=(type_of_light.equals('spot'),),
    )
    cast_shadow_map = exported(
        BoolProperty(name='Cast Shadow Map', description='Cast Shadow Map', default=False),
        i3d_name='castShadowMap',
        i3d_default=False,
        tracking=TrackingDefinition(
            member_path='use_shadow',
            toggle=BoolProperty(
                name='Shadows', description='Can be found at: Object Data Properties -> Shadow', default=True
            ),
        ),
    )
    shadow_map_bias = exported(
        FloatProperty(
            name='Shadow Map Bias',
            description='Depth bias applied to the shadow map',
            default=0.005,
            precision=3,
            min=0.0,
            max=10.0,
        ),
        i3d_name='depthMapBias',
        i3d_default=0.005,
        requires=(cast_shadow_map.equals(True),),
    )
    shadow_map_slope_scale_bias = exported(
        FloatProperty(
            name='Shadow Map Slope Scale Bias',
            description='Slope scale factor for the shadow map depth bias',
            default=0.005,
            precision=3,
            min=-I3D_MAX,
            max=I3D_MAX,
            soft_min=-10,
            soft_max=10,
        ),
        i3d_name='depthMapSlopeScaleBias',
        i3d_default=0.005,
        requires=(cast_shadow_map.equals(True),),
    )
    shadow_map_slope_clamp = exported(
        FloatProperty(
            name='Shadow Map Slope Clamp',
            description='Clamp for the slope-dependent shadow map bias',
            default=0.02,
            precision=3,
            min=-I3D_MAX,
            max=I3D_MAX,
            soft_min=-10,
            soft_max=10,
        ),
        i3d_name='depthMapSlopeClamp',
        i3d_default=0.02,
        requires=(cast_shadow_map.equals(True),),
    )
    shadow_map_resolution = exported(
        EnumProperty(
            name='Shadow Map Resolution',
            description='Resolution of the shadow map',
            items=[
                ('256', '256', '256'),
                ('512', '512', '512'),
                ('1024', '1024', '1024'),
                ('2048', '2048', '2048'),
                ('4096', '4096', '4096'),
            ],
            default='512',
        ),
        i3d_name='depthMapResolution',
        i3d_default='512',
        requires=(cast_shadow_map.equals(True),),
    )
    shadow_map_perspective = exported(
        BoolProperty(
            name='Shadowmap Perspective', description='Use perspective projection for the shadow map', default=False
        ),
        i3d_name='shadowPerspective',
        i3d_default=False,
        requires=(cast_shadow_map.equals(True),),
    )
    shadow_far_distance = exported(
        FloatProperty(
            name='Shadow Far Distance',
            description='Far distance used for shadow rendering',
            default=80,
            precision=3,
            min=0,
            max=I3D_MAX,
            soft_min=0,
            soft_max=65535,
        ),
        i3d_name='shadowFarDistance',
        i3d_default=80,
        requires=(cast_shadow_map.equals(True),),
    )
    shadow_extrusion_distance = exported(
        FloatProperty(
            name='Shadow Extrusion Distance',
            description='Extrusion distance used for shadow rendering',
            default=200,
            precision=3,
            min=0,
            max=I3D_MAX,
            soft_min=0,
            soft_max=100,
        ),
        i3d_name='shadowExtrusionDistance',
        i3d_default=200,
        requires=(cast_shadow_map.equals(True),),
    )
    shadow_map_num_splits = exported(
        EnumProperty(
            name='Shadow Map Num Splits',
            description='Number of splits used for the shadow map',
            items=[('1', '1', '1'), ('4', '4', '4')],
            default='1',
        ),
        i3d_name='numShadowMapSplits',
        i3d_default='1',
        requires=(cast_shadow_map.equals(True),),
    )
    split_distance_1 = exported(
        FloatProperty(
            name='Split Distance #1',
            description='Distance setting for shadow-map split 1',
            default=80,
            precision=3,
            min=0,
            max=I3D_MAX,
            soft_min=0,
            soft_max=500,
        ),
        i3d_name='shadowMapSplitDistance0',
        i3d_default=80,
        requires=(shadow_map_num_splits.equals('4'),),
    )
    split_distance_2 = exported(
        FloatProperty(
            name='Split Distance #2',
            description='Distance setting for shadow-map split 2',
            default=80,
            precision=3,
            min=0,
            max=I3D_MAX,
            soft_min=0,
            soft_max=500,
        ),
        i3d_name='shadowMapSplitDistance1',
        i3d_default=80,
        requires=(shadow_map_num_splits.equals('4'),),
    )
    split_distance_3 = exported(
        FloatProperty(
            name='Split Distance #3',
            description='Distance setting for shadow-map split 3',
            default=80,
            precision=3,
            min=0,
            max=I3D_MAX,
            soft_min=0,
            soft_max=500,
        ),
        i3d_name='shadowMapSplitDistance2',
        i3d_default=80,
        requires=(shadow_map_num_splits.equals('4'),),
    )
    split_distance_4 = exported(
        FloatProperty(
            name='Split Distance #4',
            description='Distance setting for shadow-map split 4',
            default=80,
            precision=3,
            min=0,
            max=I3D_MAX,
            soft_min=0,
            soft_max=500,
        ),
        i3d_name='shadowMapSplitDistance3',
        i3d_default=80,
        requires=(shadow_map_num_splits.equals('4'),),
    )


@I3DSchema.from_definitions(LightProperties).install
class I3DNodeLightAttributes(bpy.types.PropertyGroup):
    pass


_CLASSES = (I3DNodeLightAttributes,)
_register, _unregister = bpy.utils.register_classes_factory(_CLASSES)


def register() -> None:
    _register()
    bpy.types.Light.i3d_attributes = PointerProperty(type=I3DNodeLightAttributes)


def unregister() -> None:
    del bpy.types.Light.i3d_attributes
    _unregister()
