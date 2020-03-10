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

# Used for comparison when needed in the exporter, since it is near impossible to reach the default defined in the
# properties themselves
defaults = {
    'visibility': True,
    'clipDistance': 1000000.0,
    'minClipDistance': 0.0,
    'objectMask': 0,
    'castsShadows': False,
    'receiveShadows': False,
    'nonRenderable': False,
    'distanceBlending': True,
    'depthMapBias': 0.0012,
    'depthMapSlopeScaleBias': 2.0,
    'collision': True,
    'disabled': True,            # Used for certain properties like Enum, to tell the exporter not to export
    'dynamic': False,
    'static': False,
    'kinematic': False,
    }

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.handlers = []  # Clear handlers between runs since the logging module keeps track outside addon
formatter = logging.Formatter('%(module)s:%(funcName)s:%(levelname)s: %(message)s')
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
console_handler.setLevel(logging.DEBUG)
logger.addHandler(console_handler)
logger.info(f"Initialized logger for {__name__} module")


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

    verbose_output: BoolProperty(
        name="Verbose Output",
        description="Print out info to console",
        default=True
    )

    log_to_file: BoolProperty(
        name="Generate logfile",
        description="Generates a log file in the same folder as the exported i3d",
        default=True
    )


@register
class I3DNodeTransformAttributes(bpy.types.PropertyGroup):

    @register
    class visibility(bpy.types.PropertyGroup):
        name_i3d: StringProperty(default='visibility', options={'SKIP_SAVE'})
        value_i3d: BoolProperty(
            name="Visibility",
            description="Visibility flag inside of Giants Engine, decoupled from blender visibility",
            default=defaults['visibility']
        )

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

    visibility: PointerProperty(type=visibility)
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
            name="Receive Shadowmap",
            description="Receive Shadowmap",
            default=defaults['receiveShadows']
        )

    @register
    class non_renderable(bpy.types.PropertyGroup):
        name_i3d: StringProperty(default='nonRenderable', options={'SKIP_SAVE'})
        value_i3d: BoolProperty(
            name="Non Renderable",
            description="Don't render the mesh, used for collision boxes etc.",
            default=defaults['nonRenderable']
        )

    @register
    class distance_blending(bpy.types.PropertyGroup):
        name_i3d: StringProperty(default='distanceBlending', options={'SKIP_SAVE'})
        value_i3d: BoolProperty(
            name="Distance Blending",
            description="Distance Blending",
            default=defaults['distanceBlending']
        )

    casts_shadows: PointerProperty(type=casts_shadows)
    receive_shadows: PointerProperty(type=receive_shadows)
    non_renderable: PointerProperty(type=non_renderable)
    distance_blending: PointerProperty(type=distance_blending)


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


@register
class I3DMergeGroupMember(bpy.types.PropertyGroup):
    object: PointerProperty(type=bpy.types.Object)


@register
class I3DMergeGroup(bpy.types.PropertyGroup):
    root: PointerProperty(type=bpy.types.Object)
    children: CollectionProperty(type=I3DMergeGroupMember)

    def add_to_children(self, obj):
        self.children.add().object = obj

    def remove_from_children(self, obj):
        for idx, child in enumerate(self.children):
            if child.object == obj:
                self.children.remove(idx)


@register
class I3DMergeGroups(bpy.types.PropertyGroup):
    groups: CollectionProperty(type=I3DMergeGroup)

    def add_to_mergegroup(self, group_name, obj):
        logger.debug(f"Adding object {obj.name!r} to mergegroup '{group_name}'")
        if group_name not in self.groups:
            logger.debug(f"'{group_name}' is a new mergegroup")
            self.groups.add().name = group_name
        self.groups[group_name].add_to_children(obj)

    def remove_from_mergegroup(self, group_name, obj):
        logger.debug(f"Removing object {obj.name!r} from mergegroup '{group_name}'")
        group = self.groups[group_name]
        group.remove_from_children(obj)
        if len(group.children) == 0:
            logger.debug(f"{obj.name!r} was the last child in mergegroup '{group_name}', deleting mergegroup")
            self.groups.remove(self.groups.find(group_name))

    def set_root_on_mergegroup(self, group_name, obj):
        logger.debug(f"Setting object {obj.name!r} as root for mergegroup '{group_name}'")

        root_obj = self.groups[group_name].root
        if root_obj is not None:
            self.groups[group_name].root.i3d_merge_group.is_root = False

        self.groups[group_name].root = obj

    def reset_root_on_mergegroup(self, group_name):
        logger.debug(f"Resetting root on mergegroup '{group_name}'")
        self.groups[group_name].root = None


@register
class I3DMergeGroupObjectData(bpy.types.PropertyGroup):

    def update_group(self, context):
        if self.group_id == self.prev_group_id:
            logger.debug(f"{context.object.name!r} mergegroup updated, but value was not changed")
        else:
            if self.prev_group_id == '':
                logger.debug(f"{context.object.name!r} added to mergegroup '{self.group_id}'")
                bpy.context.scene.i3d_merge_groups.add_to_mergegroup(self.group_id, context.object)
            else:
                if self.is_root:
                    bpy.context.scene.i3d_merge_groups.reset_root_on_mergegroup(self.prev_group_id)

                if self.group_id == '':
                    logger.debug(f"{context.object.name!r} removed from mergegroup '{self.prev_group_id}'")
                    bpy.context.scene.i3d_merge_groups.remove_from_mergegroup(self.prev_group_id, context.object)
                elif self.group_id != '':
                    logger.debug(f"{context.object.name!r} mergegroup changed to '{self.group_id}' from '{self.prev_group_id}'")
                    bpy.context.scene.i3d_merge_groups.remove_from_mergegroup(self.prev_group_id, context.object)
                    bpy.context.scene.i3d_merge_groups.add_to_mergegroup(self.group_id, context.object)

                if self.is_root:
                    self.is_root = False

    def get_group_id(self):
        # Use the dict access to avoid recursion (Since this way does not call the getter)
        return self.get('group_id', '')

    def set_group_id(self, value):
        # Use the dict access to avoid recursion (Since this way does not call the setters/getters)
        self['prev_group_id'] = self.get('group_id', '')
        self['group_id'] = value
        logger.debug(f"'group_id' set with value '{value}'. 'prev_group_id' set with value '{self['prev_group_id']}'")

    def update_root(self, context):
        logger.debug(f"{context.object.name!r} update root field to '{self.is_root}'")
        if self.is_root:
            bpy.context.scene.i3d_merge_groups.set_root_on_mergegroup(self.group_id, context.object)
        else:
            if bpy.context.scene.i3d_merge_groups.groups[self.group_id].root == context.object:
                bpy.context.scene.i3d_merge_groups.reset_root_on_mergegroup(self.group_id)

    is_root: BoolProperty(
        name="Root of merge group",
        description="Check if this object is gonna be the root object holding the mesh",
        default=False,
        update=update_root
    )

    group_id: StringProperty(name='Merge Group',
                             description='The merge group this object belongs to',
                             default='',
                             update=update_group,
                             get=get_group_id,
                             set=set_group_id)

    prev_group_id: StringProperty(default='')


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.i3dio = PointerProperty(type=I3DExportUIProperties)
    bpy.types.Scene.i3d_merge_groups = PointerProperty(type=I3DMergeGroups)
    bpy.types.Object.i3d_attributes = PointerProperty(type=I3DNodeTransformAttributes)
    bpy.types.Object.i3d_merge_group = PointerProperty(type=I3DMergeGroupObjectData)
    bpy.types.Mesh.i3d_attributes = PointerProperty(type=I3DNodeShapeAttributes)
    bpy.types.Light.i3d_attributes = PointerProperty(type=I3DNodeLightAttributes)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.i3dio
    del bpy.types.Object.i3d_attributes
    del bpy.types.Mesh.i3d_attributes
    del bpy.types.Light.i3d_attributes
