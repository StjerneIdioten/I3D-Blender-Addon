import bpy
from bpy.types import (
    Operator,
    Panel
)
from bpy.app.handlers import persistent

from bpy.props import (
    StringProperty,
    BoolProperty,
    EnumProperty,
    PointerProperty,
    IntProperty,
)

from . import presets

classes = []


def register(cls):
    classes.append(cls)
    return cls


# Versioning for the i3d attributes
CURRENT_VERSION = 2


@register
class I3DNodeShapeAttributes(bpy.types.PropertyGroup):
    version: IntProperty(default=0)
    i3d_map = {
        'casts_shadows': {'name': 'castsShadows', 'default': False, 'blender_default': True,
                          'prev_default': False},
        'receive_shadows': {'name': 'receiveShadows', 'default': False, 'blender_default': True,
                            'prev_default': False},
        'non_renderable': {'name': 'nonRenderable', 'default': False},
        'distance_blending': {'name': 'distanceBlending', 'default': True},
        'rendered_in_viewports': {'name': 'renderedInViewports', 'default': True},
        'is_occluder': {'name': 'occluder', 'default': False},
        'terrain_decal': {'name': 'terrainDecal', 'default': False},
        'cpu_mesh': {'name': 'meshUsage', 'default': '0', 'placement': 'IndexedTriangleSet'},
        'double_sided': {'name': 'doubleSided', 'default': False},
        'material_holder': {'name': 'materialHolder', 'default': False},
        'nav_mesh_mask': {'name': 'buildNavMeshMask', 'default': '0', 'type': 'HEX'},
        'decal_layer': {'name': 'decalLayer', 'default': 0},
        'vertex_compression_range': {'name': 'vertexCompressionRange', 'default': 'auto',
                                     'placement': 'IndexedTriangleSet'},
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

    terrain_decal: BoolProperty(
        name="Terrain Decal",
        description="If enabled, the shape will be rendered as a terrain decal",
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

    double_sided: BoolProperty(
        name="Double Sided",
        description="If enabled, the shape will be rendered from both sides",
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


@register
class I3D_IO_PT_Mesh_Presets(presets.PresetPanel, Panel):
    bl_label = "Mesh Presets"
    preset_operator = "script.execute_preset"
    preset_add_operator = "i3dio.add_mesh_preset"

    @property
    def preset_subdir(self):
        return presets.PresetSubdir() / 'mesh'


@register
class I3D_IO_OT_Mesh_Add_Preset(presets.AddPresetBase, Operator):
    bl_idname = "i3dio.add_mesh_preset"
    bl_label = "Add a Mesh Preset"
    preset_menu = "I3D_IO_PT_Mesh_Presets"

    @property
    def preset_values(self):
        return [f"bpy.context.object.data.i3d_attributes.{name}" for name in I3DNodeShapeAttributes.i3d_map.keys()]

    preset_subdir = I3D_IO_PT_Mesh_Presets.preset_subdir


@register
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

        layout.prop(mesh.i3d_attributes, "casts_shadows")
        layout.prop(mesh.i3d_attributes, "receive_shadows")
        layout.prop(mesh.i3d_attributes, "rendered_in_viewports")
        layout.prop(mesh.i3d_attributes, "non_renderable")
        layout.prop(mesh.i3d_attributes, "distance_blending")
        layout.prop(mesh.i3d_attributes, "is_occluder")
        layout.prop(mesh.i3d_attributes, "terrain_decal")
        layout.prop(mesh.i3d_attributes, "cpu_mesh", expand=True)
        layout.prop(mesh.i3d_attributes, "double_sided")
        layout.prop(mesh.i3d_attributes, "material_holder")
        row = layout.row()
        row.prop(mesh.i3d_attributes, "nav_mesh_mask")
        op = row.operator('i3dio.bit_mask_editor', text="", icon='THREE_DOTS')
        op.target_prop = "nav_mesh_mask"
        op.used_bits = 8
        layout.prop(mesh.i3d_attributes, "decal_layer")
        layout.prop(mesh.i3d_attributes, "vertex_compression_range")
        layout.prop(mesh.i3d_attributes, 'fill_volume')

        header, panel = layout.panel('i3d_bounding_volume', default_closed=False)
        header.label(text="I3D Bounding Volume")
        if panel:
            panel.prop(mesh.i3d_attributes, 'bounding_volume_object')


@persistent
def migrate_i3d_property_defaults(dummy) -> None:
    if not bpy.data.filepath:
        return  # Skip new files
    for mesh in bpy.data.meshes:
        props = mesh.i3d_attributes
        if props.version >= CURRENT_VERSION:
            continue  # Skip already migrated meshes
        for prop_name, defaults in I3DNodeShapeAttributes.i3d_map.items():
            if "prev_default" in defaults and not props.is_property_set(prop_name):
                setattr(props, prop_name, defaults['prev_default'])
        # Update version only if migration was performed
        props.version = CURRENT_VERSION


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Mesh.i3d_attributes = PointerProperty(type=I3DNodeShapeAttributes)
    bpy.app.handlers.load_post.append(migrate_i3d_property_defaults)


def unregister():
    bpy.app.handlers.load_post.remove(migrate_i3d_property_defaults)
    del bpy.types.Mesh.i3d_attributes
    for cls in classes:
        bpy.utils.unregister_class(cls)
