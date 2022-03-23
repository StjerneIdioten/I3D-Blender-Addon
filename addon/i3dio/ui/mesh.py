import bpy
from bpy.types import (
    Panel
)

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


def register(cls):
    classes.append(cls)
    return cls


@register
class I3DNodeShapeAttributes(bpy.types.PropertyGroup):
    i3d_map = {
        'casts_shadows': {'name': 'castsShadows', 'default': False},
        'receive_shadows': {'name': 'receiveShadows', 'default': False},
        'non_renderable': {'name': 'nonRenderable', 'default': False},        
        'is_occluder': {'name': 'occluder', 'default': False},
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

    is_occluder: BoolProperty(
        name="Occluder",
        description="Is Occluder?",
        default=i3d_map['is_occluder']['default']
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
class I3D_IO_PT_shape_attributes(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_label = "I3D Shape Attributes"
    bl_context = 'data'

    @classmethod
    def poll(cls, context):
        if context.object is not None:
            return context.object.type == 'MESH'

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        obj = bpy.context.active_object.data

        layout.prop(obj.i3d_attributes, "casts_shadows")
        layout.prop(obj.i3d_attributes, "receive_shadows")
        layout.prop(obj.i3d_attributes, "non_renderable")
        layout.prop(obj.i3d_attributes, "distance_blending")
        layout.prop(obj.i3d_attributes, "is_occluder")
        layout.prop(obj.i3d_attributes, "cpu_mesh")
        layout.prop(obj.i3d_attributes, "decal_layer")
        layout.prop(obj.i3d_attributes, 'fill_volume')


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Mesh.i3d_attributes = PointerProperty(type=I3DNodeShapeAttributes)


def unregister():
    del bpy.types.Mesh.i3d_attributes
    for cls in classes:
        bpy.utils.unregister_class(cls)
