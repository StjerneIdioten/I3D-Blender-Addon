#!/usr/bin/env python3

"""
    ##### BEGIN GPL LICENSE BLOCK #####
  This program is free software; you can redistribute it and/or
  modify it under the terms of the GNU General Public License
  as published by the Free Software Foundation; either version 2
  of the License, or (at your option) any later version.
  This program is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU General Public License for more details.
  You should have received a copy of the GNU General Public License
  along with this program; if not, write to the Free Software Foundation,
  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
 ##### END GPL LICENSE BLOCK #####
"""

import bpy
from bpy.props import (
    StringProperty,
    BoolProperty,
    EnumProperty,
    PointerProperty,
    FloatProperty,
    IntProperty
)

classes = []

# Used for comparison when needed in the exporter, since it is near impossible to reach the default defined in the
# properties themselves
defaults = {
    'disabled': True,            # Used for certain properties like Enum, to tell the exporter not to export
    'dynamic': False,
    'static': False,
    'kinematic': False,
    'clipDistance': 1000000.0,
    'minClipDistance': 0.0,
    'objectMask': 0,
    'castsShadows': False,
    'receiveShadows': False,
    'depthMapBias': 0.0012,
    'depthMapSlopeScaleBias': 2.0,
    'collision': True
            }


def register(cls):
    classes.append(cls)
    return cls


@register
class I3DExportUIProperties(bpy.types.PropertyGroup):
    selection: EnumProperty(
        name="Export",
        description="Select which part of the scene to export",
        items=[
            ('ALL', "Everything", "Export everything from the scene master collection"),
            ('ACTIVE_COLLECTION', "Active Collection", "Export only the active collection and all its children")
        ],
        default='ACTIVE_COLLECTION'
    )

    keep_collections_as_transformgroups: BoolProperty(
        name="Keep Collections",
        description="Keep organisational collections as transformgroups in the i3d file. If turned off collections "
                    "will be ignored and the child objects will be added to the nearest parent in the hierarchy",
        default=True
    )

    apply_modifiers: BoolProperty(
        name="Apply Modifiers",
        description="Apply modifiers on objects before exporting mesh (Non destructive)",
        default=True
    )

    apply_unit_scale: BoolProperty(
        name="Apply Unit Scale",
        description="Apply the unit scale setting to the exported mesh and transform data",
        default=True
    )

    object_types_to_export: EnumProperty(
        name="Object types",
        description="Select which objects should be included in the exported",
        items=(
            ('EMPTY', "Empty", "Export empties"),
            ('CAMERA', "Camera", "Export cameras"),
            ('LIGHT', "Light", "Export lights"),
            ('MESH', "Mesh", "Export meshes")
        ),
        options={'ENUM_FLAG'},
        default={'EMPTY', 'CAMERA', 'LIGHT', 'MESH'},
    )

    copy_files: BoolProperty(
        name="Copy Files",
        description="Copies the files to have them together with the i3d file. Structure is determined by 'File "
                    "Structure' parameter. If turned off files are referenced by their absolute path instead."
                    "Files from the FS data folder are always converted to relative $data\\shared\\path\\to\\file.",
        default=True
    )

    overwrite_files: BoolProperty(
        name="Overwrite Files",
        description="Overwrites files if they already exist, currently it is only evaluated for material files!",
        default=True
    )

    file_structure: EnumProperty(
        name="File Structure",
        description="Determine the file structure of the copied files",
        items=(
            ('FLAT', "Flat", "The hierarchy is flattened, everything is in the same folder as the i3d"),
            ('BLENDER', "Blender", "The hierarchy is mimiced from around the blend file"),
            ('MODHUB', "Modhub", "The hierarchy is setup according to modhub guidelines, sorted by filetype")
        ),
        default='MODHUB'
    )


@register
class I3DNodeTransformAttributes(bpy.types.PropertyGroup):

    @register
    class clip_distance(bpy.types.PropertyGroup):
        name_i3d: StringProperty(default='clipDistance', options={'SKIP_SAVE'})
        value_i3d: FloatProperty(
            name="Clip Distance",
            description="Anything above this distance to the camera, wont be rendered",
            default=defaults['clipDistance'],
            min=0.0
        )

    @register
    class min_clip_distance(bpy.types.PropertyGroup):
        name_i3d: StringProperty(default='minClipDistance', options={'SKIP_SAVE'})
        value_i3d: FloatProperty(
            name="Min Clip Distance",
            description="Anything below this distance to the camera, wont be rendered",
            default=defaults['minClipDistance'],
            min=0.0
        )

    @register
    class object_mask(bpy.types.PropertyGroup):
        name_i3d: StringProperty(default='objectMask', options={'SKIP_SAVE'})
        value_i3d: IntProperty(
            name="Object Mask",
            description="Used for determining if the object interacts with certain rendering effects",
            default=defaults['objectMask'],
            min=0,
            max=2147483647
        )

    @register
    class rigid_body_type(bpy.types.PropertyGroup):

        name_i3d: EnumProperty(
            name="Rigid Body Type",
            description="Select rigid body type",
            items=[
                ('disabled', 'Disabled', "Disable rigidbody for this object"),
                ('static', 'Static', "Inanimate object with infinite mass"),
                ('dynamic', 'Dynamic', "Object moves with physics"),
                ('kinematic', 'Kinematic', "Object moves without physics")
            ],
            default='disabled'
        )

        value_i3d: BoolProperty(default=True, options={'SKIP_SAVE'})

    @register
    class collision(bpy.types.PropertyGroup):

        name_i3d: StringProperty(default='collision', options={'SKIP_SAVE'})
        value_i3d: BoolProperty(
            name="Collision",
            description="Does the object take part in collisions",
            default=defaults['collision']
        )

    clip_distance: PointerProperty(type=clip_distance)
    min_clip_distance: PointerProperty(type=min_clip_distance)
    object_mask: PointerProperty(type=object_mask)

    rigid_body_type: PointerProperty(type=rigid_body_type)
    collision: PointerProperty(type=collision)


@register
class I3DNodeShapeAttributes(bpy.types.PropertyGroup):

    @register
    class casts_shadows(bpy.types.PropertyGroup):
        name_i3d: StringProperty(default='castsShadows', options={'SKIP_SAVE'})
        value_i3d: BoolProperty(
            name="Cast Shadowmap",
            description="Cast Shadowmap",
            default=defaults['castsShadows']
        )

    @register
    class receive_shadows(bpy.types.PropertyGroup):
        name_i3d: StringProperty(default='receiveShadows', options={'SKIP_SAVE'})
        value_i3d: BoolProperty(
            name="Cast Shadowmap",
            description="Cast Shadowmap",
            default=defaults['castsShadows']
        )

    casts_shadows: PointerProperty(type=casts_shadows)
    receive_shadows: PointerProperty(type=receive_shadows)


@register
class I3DNodeLightAttributes(bpy.types.PropertyGroup):

    @register
    class depth_map_bias(bpy.types.PropertyGroup):
        name_i3d: StringProperty(default='depthMapBias', options={'SKIP_SAVE'})
        value_i3d: FloatProperty(
            name="Shadow Map Bias",
            description="Shadow Map Bias",
            default=defaults['depthMapBias'],
            min=0.0,
            max=10.0
        )

    @register
    class depth_map_slope_scale_bias(bpy.types.PropertyGroup):
        name_i3d: StringProperty(default='depthMapSlopeScaleBias', options={'SKIP_SAVE'})
        value_i3d: FloatProperty(
            name="Shadow Map Slope Scale Bias",
            description="Shadow Map Slope Scale Bias",
            default=defaults['depthMapSlopeScaleBias'],
            min=-10.0,
            max=10.0
        )

    depth_map_bias: PointerProperty(type=depth_map_bias)
    depth_map_slope_scale_bias: PointerProperty(type=depth_map_slope_scale_bias)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.i3dio = PointerProperty(type=I3DExportUIProperties)
    bpy.types.Object.i3d_attributes = PointerProperty(type=I3DNodeTransformAttributes)
    bpy.types.Mesh.i3d_attributes = PointerProperty(type=I3DNodeShapeAttributes)
    bpy.types.Light.i3d_attributes = PointerProperty(type=I3DNodeLightAttributes)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.i3dio
    del bpy.types.Object.i3d_attributes
    del bpy.types.Mesh.i3d_attributes
    del bpy.types.Light.i3d_attributes
