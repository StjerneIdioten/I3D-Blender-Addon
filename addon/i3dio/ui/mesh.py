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
    FloatVectorProperty,
)

classes = []

from ..xml_i3d import i3d_max

def register(cls):
    classes.append(cls)
    return cls


@register
class I3DNodeShapeAttributes(bpy.types.PropertyGroup):
    i3d_map = {
        'casts_shadows': {'name': 'castsShadows', 'default': False, 'blender_default': False},
        'receive_shadows': {'name': 'receiveShadows', 'default': False, 'blender_default': False},
        'non_renderable': {'name': 'nonRenderable', 'default': False},
        'distance_blending': {'name': 'distanceBlending', 'default': True},
        'rendered_in_viewports': {'name': 'renderedInViewports', 'default': True},
        'is_occluder': {'name': 'occluder', 'default': False},
        'cpu_mesh': {'name': 'meshUsage', 'default': '0', 'placement': 'IndexedTriangleSet'},
        'nav_mesh_mask': {'name': 'buildNavMeshMask', 'default': '0', 'type': 'HEX'},
        'decal_layer': {'name': 'decalLayer', 'default': 0},
        'fill_volume': {'name': 'name', 'default': False, 'placement': 'IndexedTriangleSet',
                        'type': 'OVERRIDE', 'override': 'fillVolumeShape'}
    }

    casts_shadows: BoolProperty(
        name="Cast Shadowmap",
        description="Cast Shadowmap",
        default=i3d_map['casts_shadows']['blender_default']
    )

    receive_shadows: BoolProperty(
        name="Receive Shadowmap",
        description="Receive Shadowmap",
        default=i3d_map['receive_shadows']['blender_default']
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
        description="Determines if the object is rendered in Giants Editor viewport or not",
        default=i3d_map['rendered_in_viewports']['default']
    )

    is_occluder: BoolProperty(
        name="Occluder",
        description="Is Occluder?",
        default=i3d_map['is_occluder']['default']
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

    fill_volume: BoolProperty(
        name="Fill Volume",
        description="Check this if the object is meant to be a fill volume, since this requires some special naming of "
                    "the IndexedTriangleSet in the i3d file.",
        default=i3d_map['fill_volume']['default']
    )

    bounding_volume_object: PointerProperty(
        name="Bounding Volume Object",
        description="The object used to calculate bvCenter and bvRadius. "
        "If the bounding volume object shares origin with the original object, "
        "then Giants Engine will always ignore the exported values and recalculate them itself",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH' and obj is not bpy.context.object
    )

    use_vertex_colors: BoolProperty(
        name="Use Vertex Colors",
        description="Enable to export vertex colors for this object",
        default=False
    )


@register
class I3D_IO_PT_shape_attributes(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_label = "I3D Shape Attributes"
    bl_context = 'data'

    @classmethod
    def poll(cls, context):
        return context.mesh

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        mesh = context.mesh

        layout.prop(mesh.i3d_attributes, "casts_shadows")
        layout.prop(mesh.i3d_attributes, "receive_shadows")
        layout.prop(mesh.i3d_attributes, "rendered_in_viewports")
        layout.prop(mesh.i3d_attributes, "non_renderable")
        layout.prop(mesh.i3d_attributes, "distance_blending")
        layout.prop(mesh.i3d_attributes, "is_occluder")
        layout.prop(mesh.i3d_attributes, "cpu_mesh")
        layout.prop(mesh.i3d_attributes, "nav_mesh_mask")
        layout.prop(mesh.i3d_attributes, "decal_layer")
        layout.prop(mesh.i3d_attributes, 'fill_volume')
        layout.prop(mesh.i3d_attributes, 'use_vertex_colors')

        header, panel = layout.panel('i3d_bounding_volume', default_closed=False)
        header.label(text="I3D Bounding Volume")
        if panel:
            panel.prop(mesh.i3d_attributes, 'bounding_volume_object')


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Mesh.i3d_attributes = PointerProperty(type=I3DNodeShapeAttributes)


def unregister():
    del bpy.types.Mesh.i3d_attributes
    for cls in classes:
        bpy.utils.unregister_class(cls)
