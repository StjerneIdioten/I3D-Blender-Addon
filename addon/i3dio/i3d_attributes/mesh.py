import bpy
from bpy.props import BoolProperty, EnumProperty, IntProperty, PointerProperty, StringProperty

from .schema import I3DSchema, exported, parse_hex_u32, stored

CPU_MESH_ITEMS = (("0", "Off", "Turns off CPU Mesh"), ("256", "On", "Turns on CPU Mesh"))

VERTEX_COMPRESSION_RANGE_ITEMS = (
    ("auto", "Auto", "Auto"),
    ("0.5", "0.5", "0.5"),
    ("1.0", "1.0", "1.0"),
    ("2.0", "2.0", "2.0"),
    ("4.0", "4.0", "4.0"),
    ("8.0", "8.0", "8.0"),
    ("16.0", "16.0", "16.0"),
    ("32.0", "32.0", "32.0"),
    ("64.0", "64.0", "64.0"),
    ("128.0", "128.0", "128.0"),
    ("256.0", "256.0", "256.0"),
)

COLOR_EXPORT_ITEMS = (
    (
        "AUTO",
        "Auto (by Shader)",
        "Export only if any applied shader on the material requires colors and the mesh has a color attribute layer",
    ),
    ("IF_PRESENT", "If Layer Exists", "Export when a color attribute layer exists, regardless of shader"),
)


def poll_bounding_volume_object(attributes: bpy.types.PropertyGroup, obj: bpy.types.Object) -> bool:
    return obj.type == "MESH" and obj.data != attributes.id_data


MESH_SCHEMA = I3DSchema(
    casts_shadows=exported(
        BoolProperty(name="Cast Shadowmap", description="Cast Shadowmap", default=True),
        i3d_name="castsShadows",
        i3d_default=False,
    ),
    receive_shadows=exported(
        BoolProperty(name="Receive Shadowmap", description="Receive Shadowmap", default=True),
        i3d_name="receiveShadows",
        i3d_default=False,
    ),
    non_renderable=exported(
        BoolProperty(
            name="Non Renderable",
            description="Don't render the mesh, used for collision boxes etc.",
            default=False,
        ),
        i3d_name="nonRenderable",
        i3d_default=False,
    ),
    distance_blending=exported(
        BoolProperty(name="Distance Blending", description="Distance Blending", default=True),
        i3d_name="distanceBlending",
        i3d_default=True,
    ),
    rendered_in_viewports=exported(
        BoolProperty(
            name="Rendered In Viewports",
            description=("Determines if the object is rendered in Giants Editor viewport or not"),
            default=True,
        ),
        i3d_name="renderedInViewports",
        i3d_default=True,
    ),
    is_occluder=exported(
        BoolProperty(name="Occluder", description="Is Occluder?", default=False), i3d_name="occluder", i3d_default=False
    ),
    terrain_decal=exported(
        BoolProperty(
            name="Terrain Decal",
            description=("If enabled, the shape will be rendered as a terrain decal"),
            default=False,
        ),
        i3d_name="terrainDecal",
        i3d_default=False,
    ),
    cpu_mesh=exported(
        EnumProperty(name="CPU Mesh", description="CPU Mesh", items=CPU_MESH_ITEMS, default="0"),
        i3d_name="meshUsage",
        i3d_default="0",
        target="IndexedTriangleSet",
    ),
    double_sided=exported(
        BoolProperty(
            name="Double Sided",
            description=("If enabled, the shape will be rendered from both sides"),
            default=False,
        ),
        i3d_name="doubleSided",
        i3d_default=False,
    ),
    material_holder=exported(
        BoolProperty(
            name="Material Holder",
            description=(
                "Needs to be set if the material of this shape is to be used "
                "on any non-standard geometry such as "
                "GEOMETRY_PARTICLE_SYSTEM or GEOMETRY_FILL_PLANE in order "
                "for the shaders to be properly precompiled"
            ),
            default=False,
        ),
        i3d_name="materialHolder",
        i3d_default=False,
    ),
    nav_mesh_mask=exported(
        StringProperty(name="Nav Mesh Mask (Hex)", description="Build Nav Mesh Mask", default="0"),
        i3d_name="buildNavMeshMask",
        i3d_default="0",
        converter=parse_hex_u32,
    ),
    decal_layer=exported(
        IntProperty(
            name="Decal Layer",
            description="Decal",
            default=0,
            min=0,
            max=3,
        ),
        i3d_name="decalLayer",
        i3d_default=0,
    ),
    vertex_compression_range=exported(
        EnumProperty(
            name="Vertex Compression Range",
            description="Vertex Compression Range",
            items=VERTEX_COMPRESSION_RANGE_ITEMS,
            default="auto",
        ),
        i3d_name="vertexCompressionRange",
        i3d_default="auto",
        target="IndexedTriangleSet",
    ),
    bounding_volume_object=stored(
        PointerProperty(
            name="Bounding Volume Object",
            description=(
                "The object used to calculate bvCenter and bvRadius. "
                "If the bounding volume object shares origin with the "
                "original object, then Giants Engine will always ignore "
                "the exported values and recalculate them itself"
            ),
            type=bpy.types.Object,
            poll=poll_bounding_volume_object,
        )
    ),
    color_export=stored(
        EnumProperty(
            name="Vertex Color Export",
            description=("Controls if vertex colors are exported for this mesh"),
            items=COLOR_EXPORT_ITEMS,
            default="AUTO",
        )
    ),
)


@MESH_SCHEMA.install
class I3DNodeShapeAttributes(bpy.types.PropertyGroup):
    pass


_CLASSES = (I3DNodeShapeAttributes,)
_register, _unregister = bpy.utils.register_classes_factory(_CLASSES)


def register() -> None:
    _register()
    bpy.types.Mesh.i3d_attributes = PointerProperty(type=I3DNodeShapeAttributes)


def unregister() -> None:
    del bpy.types.Mesh.i3d_attributes
    _unregister()
