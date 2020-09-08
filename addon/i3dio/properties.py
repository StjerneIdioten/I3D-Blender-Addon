import logging
import bpy
from bpy.props import (
    StringProperty,
    BoolProperty,
    EnumProperty,
    PointerProperty,
    FloatProperty,
    IntProperty,
    CollectionProperty,
)

classes = []

logger = logging.getLogger(__name__)


def register(cls):
    classes.append(cls)
    return cls


@register
class I3DNodeObjectAttributes(bpy.types.PropertyGroup):
    i3d_map = {
        'visibility': {'name': 'visibility', 'default': True},
        'clip_distance': {'name': 'clipDistance', 'default': 1000000.0},
        'min_clip_distance': {'name': 'minClipDistance', 'default': 0.0},
        'object_mask': {'name': 'objectMask', 'default': 0},
        'rigid_body_type': {'default': 'none'},
        'collision': {'name': 'collision', 'default': True},
        'collision_mask': {'name': 'collisionMask', 'default': 'ff', 'type': 'HEX'},
        'compound': {'name': 'compound', 'default': False},
        'trigger': {'name': 'trigger', 'default': False},
    }

    visibility: BoolProperty(
        name="Visibility",
        description="Visibility flag inside of Giants Engine, decoupled from blender visibility",
        default=i3d_map['visibility']['default']
    )

    clip_distance: FloatProperty(
        name="Clip Distance",
        description="Anything above this distance to the camera, wont be rendered",
        default=i3d_map['clip_distance']['default'],
        min=0.0
    )

    min_clip_distance: FloatProperty(
        name="Min Clip Distance",
        description="Anything below this distance to the camera, wont be rendered",
        default=i3d_map['min_clip_distance']['default'],
        min=0.0
    )

    object_mask: IntProperty(
        name="Object Mask",
        description="Used for determining if the object interacts with certain rendering effects",
        default=i3d_map['object_mask']['default'],
        min=0,
        max=2147483647
    )

    rigid_body_type: EnumProperty(
        name="Rigid Body Type",
        description="Select rigid body type",
        items=[
            ('none', 'None', "No rigidbody for this object"),
            ('static', 'Static', "Inanimate object with infinite mass"),
            ('dynamic', 'Dynamic', "Object moves with physics"),
            ('kinematic', 'Kinematic', "Object moves without physics"),
            ('compoundChild', 'Compound Child', "Uses the collision of the object higher in the hierarchy marked with the 'compound' option")
        ],
        default=i3d_map['rigid_body_type']['default']
    )

    collision: BoolProperty(
        name="Collision",
        description="Does the object take part in collisions",
        default=i3d_map['collision']['default']
    )

    collision_mask: StringProperty(
        name="Collision Mask",
        description="The objects collision mask as a hexadecimal value",
        default=i3d_map['collision_mask']['default']
    )

    compound: BoolProperty(
        name="Compound",
        description="Compound",
        default=i3d_map['compound']['default']
    )

    trigger: BoolProperty(
        name="Trigger",
        description="Trigger",
        default=i3d_map['trigger']['default']
    )


@register
class I3DNodeShapeAttributes(bpy.types.PropertyGroup):
    i3d_map = {
        'casts_shadows': {'name': 'castsShadows', 'default': False},
        'receive_shadows': {'name': 'receiveShadows', 'default': False},
        'non_renderable': {'name': 'nonRenderable', 'default': False},
        'distance_blending': {'name': 'distanceBlending', 'default': True},
        'cpu_mesh': {'name': 'meshUsage', 'default': '0', 'placement': 'IndexedTriangleSet'},
        'decal_layer': {'name': 'decalLayer', 'default': 0},
        'fill_volume': {'name': 'name', 'default': False, 'placement': 'IndexedTriangleSet',
                        'type': 'OVERRIDE', 'override': 'fillVolumeShape'}
    }

    casts_shadows: BoolProperty(
        name="Cast Shadowmap",
        description="Cast Shadowmap",
        default=i3d_map['casts_shadows']['default']
    )

    receive_shadows: BoolProperty(
        name="Receive Shadowmap",
        description="Receive Shadowmap",
        default=i3d_map['receive_shadows']['default']
    )

    non_renderable: BoolProperty(
        name="Non Renderable",
        description="Don't render the mesh, used for collision boxes etc.",
        default=i3d_map['non_renderable']['default']
    )

    distance_blending: BoolProperty(
        name="Distance Blending",
        description="Distance Blending",
        default=i3d_map['distance_blending']['default']
    )

    cpu_mesh: EnumProperty(
        name="CPU Mesh",
        description="CPU Mesh",
        items=[
            ('0', 'Off', "Turns off CPU Mesh"),
            ('256', 'On', "Turns on CPU Mesh")
        ],
        default=i3d_map['cpu_mesh']['default']
    )

    decal_layer: IntProperty(
        name="Decal Layer",
        description="Decal",
        default=i3d_map['decal_layer']['default'],
        max=3,
        min=0,
    )

    fill_volume: BoolProperty(
        name="Fill Volume",
        description="Check this if the object is meant to be a fill volume, since this requires some special naming of "
                    "the IndexedTriangleSet in the i3d file.",
        default=i3d_map['fill_volume']['default']
    )


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
class I3DMergeGroupObjectData(bpy.types.PropertyGroup):
    is_root: BoolProperty(
            name="Root of merge group",
            description="Check if this object is gonna be the root object holding the mesh",
            default=False
        )

    group_id: StringProperty(name='Merge Group',
                             description='The merge group this object belongs to',
                             default=''
                             )

@register
class I3DMappingData(bpy.types.PropertyGroup):
    is_mapped: BoolProperty(
        name="Add to mapping",
        description="If checked this object will be mapped to the i3d mapping of the xml file",
        default=False
    )

    mapping_name: StringProperty(
        name="Alternative Name",
        description="If this is left empty the name of the object itself will be used",
        default=''
    )


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Object.i3d_attributes = PointerProperty(type=I3DNodeObjectAttributes)
    bpy.types.Object.i3d_merge_group = PointerProperty(type=I3DMergeGroupObjectData)
    bpy.types.Object.i3d_mapping = PointerProperty(type=I3DMappingData)
    bpy.types.Mesh.i3d_attributes = PointerProperty(type=I3DNodeShapeAttributes)
    bpy.types.Light.i3d_attributes = PointerProperty(type=I3DNodeLightAttributes)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.i3dio
    del bpy.types.Object.i3d_attributes
    del bpy.types.Object.i3d_merge_group
    del bpy.types.Object.i3d_mapping
    del bpy.types.Mesh.i3d_attributes
    del bpy.types.Light.i3d_attributes




