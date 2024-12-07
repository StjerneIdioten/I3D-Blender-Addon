import bpy
from bpy.types import (
    Panel
)

from bpy.props import (
    StringProperty,
    BoolProperty,
    EnumProperty,
    PointerProperty,
    IntProperty,
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
        'distance_blending': {'name': 'distanceBlending', 'default': True},
        'rendered_in_viewports': {'name': 'renderedInViewports', 'default': True},
        'is_occluder': {'name': 'occluder', 'default': False},
        'terrain_decal': {'name': 'terrainDecal', 'default': False},
        'cpu_mesh': {'name': 'meshUsage', 'default': '0', 'placement': 'IndexedTriangleSet'},
        'fill_volume': {'name': 'name', 'default': False, 'placement': 'IndexedTriangleSet',
                        'type': 'OVERRIDE', 'override': 'fillVolumeShape'},
        'double_sided': {'name': 'doubleSided', 'default': False},
        'material_holder': {'name': 'materialHolder', 'default': False},
        'nav_mesh_mask': {'name': 'buildNavMeshMask', 'default': '0', 'type': 'HEX'},
        'decal_layer': {'name': 'decalLayer', 'default': 0},
        'vertex_compression_range': {'name': 'vertexCompressionRange', 'default': 'auto',
                                     'placement': 'IndexedTriangleSet'},
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

    rendered_in_viewports: BoolProperty(
        name="Rendered In Viewports",
        description="Determines if the object is rendered in Giants Editor viewport",
        default=i3d_map['rendered_in_viewports']['default']
    )

    is_occluder: BoolProperty(
        name="Occluder Mesh",
        description="Is Occluder?",
        default=i3d_map['is_occluder']['default']
    )

    terrain_decal: BoolProperty(
        name="Terrain Decal",
        description="If checked, the shape will be rendered as a terrain decal",
        default=i3d_map['terrain_decal']['default']
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

    fill_volume: BoolProperty(
        name="Fill Volume",
        description="Check this if the object is meant to be a fill volume, since this requires some special naming of "
                    "the IndexedTriangleSet in the i3d file.",
        default=i3d_map['fill_volume']['default']
    )

    double_sided: BoolProperty(
        name="Double Sided",
        description="If checked, the shape will be rendered from both sides",
        default=i3d_map['double_sided']['default']
    )

    material_holder: BoolProperty(
        name="Material Holder",
        description="Needs to be set if the material of this shape is to be used on any non-standard geometry "
        "such as GEOMETRY_PARTICLE_SYSTEM or GEOMETRY_FILL_PLANE in order for the shaders to be properly precompiled",
        default=i3d_map['material_holder']['default']
    )

    nav_mesh_mask: StringProperty(
        name="Nav Mesh Mask (Hex)",
        description="Build Nav Mesh Mask",
        default=i3d_map['nav_mesh_mask']['default'],
    )

    decal_layer: IntProperty(
        name="Decal Layer",
        description="Decal",
        default=i3d_map['decal_layer']['default'],
        max=3,
        min=0,
    )

    vertex_compression_range: EnumProperty(
        name="Vertex Compression Range",
        description="Vertex Compression Range",
        items=[
            ('auto', 'Auto', "Auto"),
            ('0.5', '0.5', "0.5"),
            ('1.0', '1.0', "1.0"),
            ('2.0', '2.0', "2.0"),
            ('4.0', '4.0', "4.0"),
            ('8.0', '8.0', "8.0"),
            ('16.0', '16.0', "16.0"),
            ('32.0', '32.0', "32.0"),
            ('64.0', '64.0', "64.0"),
            ('128.0', '128.0', "128.0"),
            ('256.0', '256.0', "256.0"),
        ],
        default=i3d_map['vertex_compression_range']['default']
    )

    bounding_volume_object: PointerProperty(
        name="Bounding Volume Object",
        description="Object used to calculate bvCenter and bvRadius. If it shares the origin with the original object, "
        "Giants Engine ignores exported values and recalculates them.",
        type=bpy.types.Object,
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
        layout.prop(obj.i3d_attributes, "rendered_in_viewports")
        layout.prop(obj.i3d_attributes, "is_occluder")
        layout.prop(obj.i3d_attributes, "terrain_decal")
        layout.prop(obj.i3d_attributes, "cpu_mesh")
        layout.prop(obj.i3d_attributes, 'fill_volume')
        layout.prop(obj.i3d_attributes, "double_sided")
        layout.prop(obj.i3d_attributes, 'material_holder')
        layout.prop(obj.i3d_attributes, "nav_mesh_mask")
        layout.prop(obj.i3d_attributes, "decal_layer")
        layout.prop(obj.i3d_attributes, "vertex_compression_range")


@register
class I3D_IO_PT_shape_bounding_box(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_label = "I3D Bounding Volume"
    bl_context = 'data'

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.type == 'MESH'

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        obj = bpy.context.active_object.data

        row = layout.row()
        row.prop(obj.i3d_attributes, 'bounding_volume_object')


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Mesh.i3d_attributes = PointerProperty(type=I3DNodeShapeAttributes)


def unregister():
    del bpy.types.Mesh.i3d_attributes
    for cls in classes:
        bpy.utils.unregister_class(cls)
