import bpy
from bpy.types import (
    Operator,
    Panel
)
from bpy.app.handlers import (
    persistent,
    load_post
)
from bpy.props import (
    StringProperty,
    BoolProperty,
    EnumProperty,
    PointerProperty,
    FloatProperty,
    IntProperty,
    FloatVectorProperty,
    CollectionProperty,
)
from .helper_functions import i3d_property
from ..xml_i3d import i3d_max
from . import (presets, mesh, light)

from .collision_data import COLLISIONS

classes = []


def register(cls):
    classes.append(cls)
    return cls


def validate_collision_filter(value: str, allowed_values: list[str]) -> bool:
    """Validate if the given value exists in the allowed_values list."""
    print(f"Validating collision filter group: {value}")
    return value in allowed_values


@register
class I3DNodeObjectAttributes(bpy.types.PropertyGroup):
    i3d_map = {
        'locked_group': {'name': 'lockedgroup', 'default': False, 'preset_group': 'ALL'},
        'visibility': {'name': 'visibility', 'default': True, 'tracking': {'member_path': 'hide_render',
                                                                           'mapping': {True: False,
                                                                                       False: True}}},
        'clip_distance': {'name': 'clipDistance', 'default': 1000000.0, 'preset_group': 'ALL'},
        'min_clip_distance': {'name': 'minClipDistance', 'default': 0.0, 'preset_group': 'ALL'},
        'object_mask': {'name': 'objectMask', 'default': '0', 'type': 'HEX', 'preset_group': 'ALL'},
        'rigid_body_type': {'default': 'none', 'preset_group': 'MESH'},
        'lod_distances': {'name': 'lodDistance', 'default': (0.0, 0.0, 0.0, 0.0), 'preset_group': 'EMPTY'},
        'lod_blending': {'name': 'lodBlending', 'default': True, 'preset_group': 'EMPTY'},
        'collision': {'name': 'collision', 'default': True, 'preset_group': 'MESH'},
        'collision_filter_group': {'name': 'collisionFilterGroup', 'default': 'ff', 'type': 'HEX', 'preset_group': 'MESH'},
        'collision_filter_mask': {'name': 'collisionFilterMask', 'default': 'ff', 'type': 'HEX', 'preset_group': 'MESH'},
        'collision_mask': {'name': 'collisionMask', 'default': 'ff', 'type': 'HEX', 'preset_group': 'MESH'},
        'compound': {'name': 'compound', 'default': False, 'preset_group': 'MESH'},
        'trigger': {'name': 'trigger', 'default': False, 'preset_group': 'MESH'},
        'restitution': {'name': 'restitution', 'default': 0.0, 'preset_group': 'MESH'},
        'static_friction': {'name': 'staticFriction', 'default': 0.5, 'preset_group': 'MESH'},
        'dynamic_friction': {'name': 'dynamicFriction', 'default': 0.5, 'preset_group': 'MESH'},
        'linear_damping': {'name': 'linearDamping', 'default': 0.0, 'preset_group': 'MESH'},
        'angular_damping': {'name': 'angularDamping', 'default': 0.01, 'preset_group': 'MESH'},
        'density': {'name': 'density', 'default': 1.0, 'preset_group': 'MESH'},
        'solver_iteration_count': {'name': 'solverIterationCount', 'default': 4, 'preset_group': 'MESH'},
        'split_type': {'name': 'splitType', 'default': 0, 'preset_group': 'MESH'},
        'split_uvs': {'name': 'splitUvs', 'default': (0.0, 0.0, 1.0, 1.0, 1.0), 'preset_group': 'MESH'},
        'use_parent': {'name': 'useParent', 'default': True, 'preset_group': 'EMPTY'},
        'minute_of_day_start': {'name': 'minuteOfDayStart', 'default': 0, 'preset_group': 'EMPTY'},
        'minute_of_day_end': {'name': 'minuteOfDayEnd', 'default': 0, 'preset_group': 'EMPTY'},
        'day_of_year_start': {'name': 'dayOfYearStart', 'default': 0, 'preset_group': 'EMPTY'},
        'day_of_year_end': {'name': 'dayOfYearEnd', 'default': 0, 'preset_group': 'EMPTY'},
        'weather_required_mask': {'name': 'weatherRequiredMask', 'default': '0', 'type': 'HEX', 'preset_group': 'EMPTY'},
        'weather_prevent_mask': {'name': 'weatherPreventMask', 'default': '0', 'type': 'HEX', 'preset_group': 'EMPTY'},
        'viewer_spaciality_required_mask': {'name': 'viewerSpacialityRequiredMask', 'default': '0', 'type': 'HEX', 'preset_group': 'EMPTY'},
        'viewer_spaciality_prevent_mask': {'name': 'viewerSpacialityPreventMask', 'default': '0', 'type': 'HEX', 'preset_group': 'EMPTY'},
        'render_invisible': {'name': 'renderInvisible', 'default': False, 'preset_group': 'EMPTY'},
        'visible_shader_parameter': {'name': 'visibleShaderParameter', 'default': 1.0, 'preset_group': 'EMPTY'},
        'joint': {'name': 'joint', 'default': False, 'preset_group': 'EMPTY'},
        'projection': {'name': 'projection', 'default': False, 'preset_group': 'EMPTY'},
        'projection_distance': {'name': 'projDistance', 'default': 0.01, 'preset_group': 'EMPTY'},
        'projection_angle': {'name': 'projAngle', 'default': 0.01, 'preset_group': 'EMPTY'},
        'x_axis_drive': {'name': 'xAxisDrive', 'default': False, 'preset_group': 'EMPTY'},
        'y_axis_drive': {'name': 'yAxisDrive', 'default': False, 'preset_group': 'EMPTY'},
        'z_axis_drive': {'name': 'zAxisDrive', 'default': False, 'preset_group': 'EMPTY'},
        'drive_position': {'name': 'drivePos', 'default': False, 'preset_group': 'EMPTY'},
        'drive_force_limit': {'name': 'driveForceLimit', 'default': 100000.0, 'preset_group': 'EMPTY'},
        'drive_spring': {'name': 'driveSpring', 'default': 1.0, 'preset_group': 'EMPTY'},
        'drive_damping': {'name': 'driveDamping', 'default': 0.01, 'preset_group': 'EMPTY'},
        'breakable_joint': {'name': 'breakableJoint', 'default': False, 'preset_group': 'EMPTY'},
        'joint_break_force': {'name': 'jointBreakForce', 'default': 0.0, 'preset_group': 'EMPTY'},
        'joint_break_torque': {'name': 'jointBreakTorque', 'default': 0.0, 'preset_group': 'EMPTY'},
    }

    locked_group: BoolProperty(
        name="Locked Group",
        description="Enable this option to treat the object as a 'locked group' in Giants Editor. "
        "When the hierarchy is collapsed and you select any of its child objects in the viewport, "
        "the parent object (the locked group) will be selected instead.",
        default=i3d_map['locked_group']['default']
    )

    visibility: BoolProperty(
        name="Visibility",
        description="Visibility",
        default=i3d_map['visibility']['default']
    )

    visibility_tracking: BoolProperty(
        name="Render Visibility",
        description="Can be found at: Object Properties -> Visibility -> Renders "
                    "(can also be toggled through outliner)",
        default=True
    )

    lod_distances: FloatVectorProperty(
        name="LOD Distance",
        description="Defines the level-of-detail (LOD) distances for rendering. "
        "The first value is always 0, and each subsequent value must be equal to or greater than the previous one.",
        size=4,
        default=i3d_map['lod_distances']['default'],
        min=0.0
    )

    lod_blending: BoolProperty(
        name="LOD Blending",
        description="Enable LOD blending",
        default=i3d_map['lod_blending']['default']
    )

    clip_distance: FloatProperty(
        name="Clip Distance",
        description="Anything above this distance to the camera, wont be rendered",
        default=i3d_map['clip_distance']['default'],
        min=0.0,
        max=i3d_max,
        soft_min=0,
        soft_max=65535.0
    )

    min_clip_distance: FloatProperty(
        name="Min Clip Distance",
        description="Anything below this distance to the camera, wont be rendered",
        default=i3d_map['min_clip_distance']['default'],
        min=0.0,
        max=i3d_max,
        soft_min=0,
        soft_max=65535.0
    )

    object_mask: StringProperty(
        name="Object Mask",
        description="Used for determining if the object interacts with certain rendering effects",
        default=i3d_map['object_mask']['default'],
    )

    rigid_body_type: EnumProperty(
        name="Rigid Body Type",
        description="Select rigid body type",
        items=[
            ('none', 'None', "No rigidbody for this object"),
            ('static', 'Static', "Inanimate object with infinite mass"),
            ('dynamic', 'Dynamic', "Object moves with physics"),
            ('kinematic', 'Kinematic', "Object moves without physics"),
            ('compoundChild', 'Compound Child', "Uses the collision of a higher-level object marked as 'compound'")
        ],
        default=i3d_map['rigid_body_type']['default']
    )

    collision: BoolProperty(
        name="Collision",
        description="Does the object take part in collisions",
        default=i3d_map['collision']['default']
    )

    collision_filter_group: StringProperty(
        name="Collision Filter Group",
        description="The objects collision filter group as a hexadecimal value",
        default=i3d_map['collision_filter_group']['default']
    )

    collision_filter_mask: StringProperty(
        name="Collision Filter Mask",
        description="The objects collision filter mask as a hexadecimal value",
        default=i3d_map['collision_filter_mask']['default']
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

    restitution: FloatProperty(
        name="Restitution",
        description="Bounciness of the surface",
        default=i3d_map['restitution']['default'],
        min=0,
        max=1
    )

    static_friction: FloatProperty(
        name="Static Friction",
        description="The force that resists motion between two non-moving surfaces",
        default=i3d_map['static_friction']['default'],
        min=0,
        max=1
    )

    dynamic_friction: FloatProperty(
        name="Dynamic Friction",
        description="The force that resists motion between two moving surfaces",
        default=i3d_map['dynamic_friction']['default'],
        min=0,
        max=1
    )

    linear_damping: FloatProperty(
        name="Linear Damping",
        description="Defines the slowdown factor for linear movement, affecting speed",
        default=i3d_map['linear_damping']['default'],
        min=0,
        max=1
    )

    angular_damping: FloatProperty(
        name="Angular Damping",
        description="Defines the slowdown factor for angular movement, affecting spin",
        default=i3d_map['angular_damping']['default'],
        min=0,
        max=1
    )

    density: FloatProperty(
        name="Density",
        description="Used with the shape of the object to calculate mass. "
                    "The higher the number, the heavier the object",
        default=i3d_map['density']['default'],
        min=0,
        max=20
    )

    solver_iteration_count: IntProperty(
        name="Solver Iteration Count",
        description="The number of iterations the physics engine uses to solve the constraints",
        default=i3d_map['solver_iteration_count']['default'],
        min=1,
        max=20
    )

    split_type: IntProperty(
        name="Split Type",
        description="Split type determines what type of tree it is. "
                    "For custom tree type use a number over 19",
        default=i3d_map['split_type']['default'],
        min=0,
        max=200
    )

    split_uvs: FloatVectorProperty(
        name="Split UVs",
        description="Min U, Min V, Max U, Max V, UV World Scale",
        size=5,
        default=i3d_map['split_uvs']['default'],
        min=0,
        max=i3d_max
    )

    use_parent: BoolProperty(
        name="Use Parent",
        description="Inherits visibility condition attributes from the parent object",
        default=True
    )

    minute_of_day_start: IntProperty(
        name="Minute of Day Start",
        description="The minute of the day when visibility is enabled.\n"
        "Example: 8:00 AM = 480, 8:00 PM = 1200",
        default=i3d_map['minute_of_day_start']['default'],
        max=1440,
        min=0,
    )

    minute_of_day_end: IntProperty(
        name="Minute of Day End",
        description="The minute of the day when visibility is disabled.\n"
        "Example: 8:00 AM = 480, 8:00 PM = 1200",
        default=i3d_map['minute_of_day_end']['default'],
        max=1440,
        min=0,
    )

    day_of_year_start: IntProperty(
        name="Day of Year Start",
        description="The day of the year when visibility is enabled",
        default=i3d_map['day_of_year_start']['default'],
        max=365,
        min=0,
    )

    day_of_year_end: IntProperty(
        name="Day of Year End",
        description="The day of the year when visibility is disabled",
        default=i3d_map['day_of_year_end']['default'],
        max=365,
        min=0,
    )

    weather_required_mask: StringProperty(
        name="Weather Required Mask (Hex)",
        description="Defines the required weather conditions as a hexadecimal value.\n"
        "Examples: Winter = 400, Winter + Snow = 408",
        default=i3d_map['weather_required_mask']['default']
    )

    weather_prevent_mask: StringProperty(
        name="Weather Prevent Mask (Hex)",
        description="Defines the weather conditions that prevent visibility as a hexadecimal value.\n"
        "Examples: Summer = 100, Summer + Sun = 101",
        default=i3d_map['weather_prevent_mask']['default']
    )

    viewer_spaciality_required_mask: StringProperty(
        name="Viewer Spaciality Required Mask (Hex)",
        description="Defines the required viewer spaciality conditions as a hexadecimal value",
        default=i3d_map['viewer_spaciality_required_mask']['default']
    )

    viewer_spaciality_prevent_mask: StringProperty(
        name="Viewer Spaciality Prevent Mask (Hex)",
        description="Defines the viewer spaciality conditions that prevent visibility as a hexadecimal value",
        default=i3d_map['viewer_spaciality_prevent_mask']['default']
    )

    render_invisible: BoolProperty(
        name="Render Invisible",
        description="If enabled, the object is always rendered.\n"
        "Visibility must be controlled in the shader using the visible shader parameter",
        default=i3d_map['render_invisible']['default']
    )

    visible_shader_parameter: FloatProperty(
        name="Visible Shader Parameter",
        description="Specifies the value applied to the visibility shader parameter when the object is visible.\n"
        "If conditions are not met, 0 is passed to the shader",
        default=i3d_map['visible_shader_parameter']['default'],
        min=-100,
        max=100
    )

    joint: BoolProperty(
        name="Joint",
        description="Enable use of joint",
        default=i3d_map['joint']['default']
    )
    projection: BoolProperty(
        name="Enable joint projection",
        description="Enables use of joint",
        default=i3d_map['projection']['default']
    )
    x_axis_drive: BoolProperty(
        name="X Axis Drive",
        description="Enable x axis drive",
        default=i3d_map['x_axis_drive']['default']
    )
    y_axis_drive: BoolProperty(
        name="Y Axis Drive",
        description="Enable y axis drive",
        default=i3d_map['y_axis_drive']['default']
    )
    z_axis_drive: BoolProperty(
        name="Z Axis Drive",
        description="Enable z axis drive",
        default=i3d_map['z_axis_drive']['default']
    )
    drive_position: BoolProperty(
        name="Drive Position",
        description="Enable drive position",
        default=i3d_map['drive_position']['default']
    )
    projection_distance: FloatProperty(
        name="Projection Distance",
        description="Projection distance",
        default=i3d_map['projection_distance']['default'],
        min=0,
        max=i3d_max
    )
    projection_angle: FloatProperty(
        name="Projection Angle",
        description="Projection angle",
        default=i3d_map['projection_angle']['default'],
        min=0,
        max=i3d_max
    )
    drive_force_limit: FloatProperty(
        name="Drive Force Limit",
        description="Drive Force Limit",
        default=i3d_map['drive_force_limit']['default'],
        min=0,
        max=i3d_max
    )
    drive_spring: FloatProperty(
        name="Drive Spring",
        description="Drive Spring",
        default=i3d_map['drive_spring']['default'],
        min=0,
        max=i3d_max
    )
    drive_damping: FloatProperty(
        name="Drive Damping",
        description="Drive Damping",
        default=i3d_map['drive_damping']['default'],
        min=0,
        max=i3d_max
    )
    breakable_joint: BoolProperty(
        name="Breakable",
        description="Breakable joint",
        default=i3d_map['breakable_joint']['default']
    )
    joint_break_force: FloatProperty(
        name="Break Force",
        description="Joint break force",
        default=i3d_map['joint_break_force']['default'],
        min=0,
        max=i3d_max
    )
    joint_break_torque: FloatProperty(
        name="Break Torque",
        description="Joint break torque",
        default=i3d_map['joint_break_torque']['default'],
        min=0,
        max=i3d_max
    )

    exclude_from_export: BoolProperty(
        name="Exclude from Export",
        description="If checked, this object and its children will be excluded from export",
        default=False
    )

    collapse_armature: BoolProperty(
        name="Collapse Armature",
        description=(
            "If enabled, the armature itself will not be exported. "
            "Instead, its root bones will take its position in the scene graph. "
            "If disabled, the armature will be exported as a transform group, "
            "with bones structured as they appear in Blender."
        ),
        default=True
    )


@register
class I3DMergeGroup(bpy.types.PropertyGroup):
    name: StringProperty(
        name='Merge Group Name',
        description='The name of the merge group',
        default='MergeGroup'
    )

    root: PointerProperty(
        name="Merge Group Root Object",
        description="The object acting as the root for the merge group",
        type=bpy.types.Object
    )


@register
class I3DMergeChildren(bpy.types.PropertyGroup):
    enabled: BoolProperty(
        name="Enable Merge Children",
        description=(
            "Marks this object as the Merge Children Root, defining the group of child objects to be merged. "
            "Only the child meshes will be included in the final merged Shape. "
            "The root object's mesh data (vertices, triangles, materials, etc.) will NOT be exported, "
            "but its shape attributes (e.g., cast shadows) and object attributes will still be used."
        ),
        default=False
    )
    apply_transforms: bpy.props.BoolProperty(
        name="Apply Transforms",
        description=(
            "Controls whether child meshes apply their transforms before merging. "
            "When enabled, each child mesh keeps its relative position, rotation, and scale. "
            "When disabled, all child meshes are transformed to match the root object's location and orientation, "
            "removing their individual offsets."
        ),
        default=False
    )
    interpolation_steps: bpy.props.IntProperty(
        name="Interpolation Steps",
        description=(
            "Sets the number of interpolation steps for smoother transitions in shaders. "
            "This affects effects like motion paths that use array textures. "
            "Ensure the corresponding texture supports the same step count to prevent animation misalignment."
        ),
        default=1,
        min=1,
        max=10
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


@register
class I3DReferenceData(bpy.types.PropertyGroup):
    path: StringProperty(
        name="Reference Path",
        description="The path to the .i3d file you want to reference",
        default='',
        subtype='FILE_PATH'
    )
    runtime_loaded: BoolProperty(
        name="Runtime Loaded",
        description=(
            "If enabled, the referenced I3D file will be loaded in-game at runtime. "
            "Disable for objects managed by XML (e.g. lights) or if you only want to preview in Giants Editor. "
            "Most references should NOT be runtime loaded."
        ),
        default=False  # Default in GE is True, but for most use cases False makes more sense
    )
    child_path: StringProperty(
        name="Child Path",
        description=(
            "Selects which root node or sub-node to load from the referenced I3D. "
            "e.g. '0>' for the first root node, '1>' for the second. If left empty and the file has multiple "
            "root nodes, you'll get a warning, but the first node ('0>') will be used by default in Giants Editor."
        ),
        default=''
    )


@register
class I3D_IO_OT_set_collision_preset(bpy.types.Operator):
    bl_idname = 'i3dio.set_collision_preset'
    bl_label = 'Set Collision Preset'
    bl_options = {'INTERNAL'}
    preset: StringProperty()

    @classmethod
    def description(cls, _context, properties):
        return f"Set the collision preset to {properties.preset}"

    def execute(self, context):
        preset = COLLISIONS['presets'].get(self.preset, {})
        i3d_attributes = context.object.i3d_attributes

        if preset:
            i3d_attributes.collision_filter_group = preset.group_hex
            i3d_attributes.collision_filter_mask = preset.mask_hex
        else:
            i3d_attributes.collision_filter_group = i3d_attributes.i3d_map['collision_filter_group']['default']
            i3d_attributes.collision_filter_mask = i3d_attributes.i3d_map['collision_filter_mask']['default']
        return {'FINISHED'}


@register
class I3D_IO_MT_collision_presets(bpy.types.Menu):
    bl_idname = "I3D_IO_MT_collision_presets"
    bl_label = "Collision Presets"

    def draw(self, _context):
        layout = self.layout
        presets = list(COLLISIONS['presets'].keys())

        if not presets:
            layout.label(text="No Presets Available")
            return

        grid = layout.grid_flow(columns=2, even_columns=True, even_rows=True)
        for preset in presets:
            text = preset.title().replace('_', ' ')
            grid.operator(I3D_IO_OT_set_collision_preset.bl_idname, text=text).preset = preset
        layout.separator()
        layout.operator(I3D_IO_OT_set_collision_preset.bl_idname, text="None").preset = "NONE"


SPLIT_TYPE_PRESETS = {
    "Spruce": {'split_type': 1, 'support_wood_harvester': True},
    "Pine": {'split_type': 2, 'support_wood_harvester': True},
    "Larch": {'split_type': 3, 'support_wood_harvester': True},
    "Birch": {'split_type': 4, 'support_wood_harvester': False},
    "Beech": {'split_type': 5, 'support_wood_harvester': False},
    "Maple": {'split_type': 6, 'support_wood_harvester': False},
    "Oak": {'split_type': 7, 'support_wood_harvester': False},
    "Ash": {'split_type': 8, 'support_wood_harvester': False},
    "Locust": {'split_type': 9, 'support_wood_harvester': False},
    "Mahogany": {'split_type': 10, 'support_wood_harvester': False},
    "Poplar": {'split_type': 11, 'support_wood_harvester': False},
    "American Elm": {'split_type': 12, 'support_wood_harvester': False},
    "Cypress": {'split_type': 13, 'support_wood_harvester': False},
    "Downy Serviceberry": {'split_type': 14, 'support_wood_harvester': False},
    "Pagoda Dogwood": {'split_type': 15, 'support_wood_harvester': False},
    "Shagbark Hickory": {'split_type': 16, 'support_wood_harvester': False},
    "Stone Pine": {'split_type': 17, 'support_wood_harvester': False},
    "Willow": {'split_type': 18, 'support_wood_harvester': False},
    "Olive Tree": {'split_type': 19, 'support_wood_harvester': False}
}


@register
class I3D_IO_OT_set_split_type_preset(bpy.types.Operator):
    bl_idname = 'i3dio.set_split_type_preset'
    bl_label = 'Set Split Type Preset'
    bl_options = {'INTERNAL'}
    preset: StringProperty()

    @classmethod
    def description(cls, _context, properties):
        preset = SPLIT_TYPE_PRESETS.get(properties.preset, {})
        support_harvester = preset.get('support_wood_harvester', False)
        return (f"Set the split type preset to {properties.preset}.\n"
                f"Supports wood harvester: {'Yes' if support_harvester else 'No'}")

    def execute(self, context):
        i3d_attributes = context.object.i3d_attributes
        if self.preset == "Default":
            i3d_attributes.split_type = i3d_attributes.i3d_map['split_type']['default']
            return {'FINISHED'}
        preset = SPLIT_TYPE_PRESETS.get(self.preset, {})
        i3d_attributes.split_type = preset['split_type']
        return {'FINISHED'}


@register
class I3D_IO_MT_split_type_presets(bpy.types.Menu):
    bl_idname = 'I3D_IO_MT_split_type_presets'
    bl_label = 'Split Type Presets'

    def draw(self, _context):
        layout = self.layout
        grid = layout.grid_flow(columns=2, even_columns=True, even_rows=True)
        for preset in list(SPLIT_TYPE_PRESETS.keys()):
            grid.operator(I3D_IO_OT_set_split_type_preset.bl_idname, text=preset).preset = preset

        layout.separator()
        layout.operator(I3D_IO_OT_set_split_type_preset.bl_idname, text="Default").preset = "Default"


@register
class I3D_IO_PT_object_attributes(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_label = "I3D Object Attributes"
    bl_context = 'object'

    @classmethod
    def poll(cls, context):
        return context.object is not None

    def draw_header_preset(self, context):
        if context.object.type in ['EMPTY', 'LIGHT', 'MESH']:
            I3D_IO_PT_Object_Presets.draw_panel_header(self.layout)

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        obj = context.object
        i3d_attributes = obj.i3d_attributes

        draw_i3d_mapping_box(layout, obj.i3d_mapping)

        i3d_property(layout, i3d_attributes, 'locked_group', obj)
        i3d_property(layout, i3d_attributes, 'visibility', obj)
        i3d_property(layout, i3d_attributes, 'clip_distance', obj)
        i3d_property(layout, i3d_attributes, 'min_clip_distance', obj)
        row = layout.row(align=True)
        i3d_property(row, i3d_attributes, 'object_mask', obj)
        op = row.operator('i3dio.bit_mask_editor', text="", icon='THREE_DOTS')
        op.target_prop = 'object_mask'
        op.layout_mode = 'VERTICAL'
        op.dialog_width = 1000

        layout.separator(type='LINE')
        box = layout.box()
        box.label(text="Exporter Specific:")
        box.prop(i3d_attributes, 'exclude_from_export')
        if obj.type == 'ARMATURE':
            box.prop(i3d_attributes, 'collapse_armature')
        layout.separator(type='LINE')

        if obj.type == 'EMPTY':
            draw_level_of_detail_attributes(layout, obj, i3d_attributes)
            draw_reference_file_attributes(layout, obj.i3d_reference)
            draw_joint_attributes(layout, i3d_attributes)

        elif obj.type == 'MESH':
            draw_rigid_body_attributes(layout, i3d_attributes)
            draw_merge_children_attributes(layout, obj.i3d_merge_children)
            draw_merge_group_attributes(layout, context)

        draw_visibility_condition_attributes(layout, i3d_attributes)


def unset_properties(i3d_attributes: bpy.types.PropertyGroup, props: tuple) -> None:
    for prop in props:
        i3d_attributes.property_unset(prop)


def draw_rigid_body_attributes(layout: bpy.types.UILayout, i3d_attributes: bpy.types.PropertyGroup) -> None:
    UNSET_PROPS = ('compound', 'collision', 'collision_filter_group', 'collision_filter_mask', 'trigger',
                   'restitution', 'static_friction', 'dynamic_friction', 'linear_damping', 'angular_damping',
                   'density', 'solver_iteration_count', 'split_type', 'split_uvs')

    is_static = i3d_attributes.rigid_body_type == 'static'
    header, panel = layout.panel('i3d_rigid_body_panel', default_closed=False)
    header.label(text="Rigidbody")
    if panel:
        panel.prop(i3d_attributes, 'rigid_body_type')

        if i3d_attributes.rigid_body_type == 'none':
            unset_properties(i3d_attributes, UNSET_PROPS)
            return

        row_compound = panel.row()
        row_compound.prop(i3d_attributes, 'compound')
        if i3d_attributes.rigid_body_type in ('static', 'compoundChild'):
            row_compound.enabled = False
            i3d_attributes.property_unset('compound')

        panel.prop(i3d_attributes, 'collision')
        panel.prop(i3d_attributes, 'trigger')

        col_filter_header, col_filter_panel = layout.panel('i3d_collision_filter', default_closed=False)
        col_filter_header.label(text="Collision Filter")
        col_filter_header.emboss = 'NONE'
        col_filter_header.menu(I3D_IO_MT_collision_presets.bl_idname, icon='PRESET', text="")
        if col_filter_panel:
            row = col_filter_panel.row()
            row.prop(i3d_attributes, 'collision_filter_group')
            op = row.operator('i3dio.bit_mask_editor', text="", icon='THREE_DOTS')
            op.target_prop = 'collision_filter_group'
            op.layout_mode = 'VERTICAL'
            op.dialog_width = 890
            row = col_filter_panel.row()
            row.prop(i3d_attributes, 'collision_filter_mask')
            op = row.operator('i3dio.bit_mask_editor', text="", icon='THREE_DOTS')
            op.target_prop = 'collision_filter_mask'
            op.layout_mode = 'VERTICAL'
            op.dialog_width = 890

        panel.prop(i3d_attributes, 'restitution')
        panel.prop(i3d_attributes, 'static_friction')
        panel.prop(i3d_attributes, 'dynamic_friction')
        panel.prop(i3d_attributes, 'linear_damping')
        panel.prop(i3d_attributes, 'angular_damping')
        panel.prop(i3d_attributes, 'density')
        panel.prop(i3d_attributes, 'solver_iteration_count')

        # Split Type Panel
        header, panel = layout.panel('i3d_split_type_panel', default_closed=True)
        header.label(text="Split Type")
        header.emboss = 'NONE'
        header.menu(I3D_IO_MT_split_type_presets.bl_idname, icon='PRESET', text="")
        header.enabled = is_static
        if panel:
            panel.use_property_split = False
            panel.prop(i3d_attributes, 'split_type')
            panel.enabled = is_static
            col = panel.column(align=True)
            grid_split_uvs = col.grid_flow(row_major=True, columns=2, align=True)
            grid_split_uvs.prop(i3d_attributes, 'split_uvs', index=0, text="Min U")
            grid_split_uvs.prop(i3d_attributes, 'split_uvs', index=1, text="Min V")
            grid_split_uvs.prop(i3d_attributes, 'split_uvs', index=2, text="Max U")
            grid_split_uvs.prop(i3d_attributes, 'split_uvs', index=3, text="Max V")
            col.prop(i3d_attributes, 'split_uvs', index=4, text="UV World Scale")

            if i3d_attributes.split_type == 0 or not is_static:
                unset_properties(i3d_attributes, ('split_uvs', 'split_type'))
                col.enabled = False


def draw_visibility_condition_attributes(layout: bpy.types.UILayout, i3d_attributes: bpy.types.PropertyGroup) -> None:
    PROPS = ('minute_of_day_start', 'minute_of_day_end', 'day_of_year_start', 'day_of_year_end',
             'weather_required_mask', 'weather_prevent_mask', 'viewer_spaciality_required_mask',
             'viewer_spaciality_prevent_mask', 'render_invisible', 'visible_shader_parameter')

    use_parent = i3d_attributes.use_parent
    # layout.use_property_split = False
    header, panel = layout.panel('i3d_visibility_condition_panel', default_closed=True)
    header.use_property_split = False
    header.prop(i3d_attributes, 'use_parent', text="")
    header.label(text="Visibility Condition")
    if panel:
        panel.use_property_split = True
        for prop in PROPS:
            row = panel.row()
            row.prop(i3d_attributes, prop)
            if prop.endswith('_mask'):
                op = row.operator('i3dio.bit_mask_editor', text="", icon='THREE_DOTS')
                op.target_prop = prop
                op.layout_mode = 'VERTICAL'
                op.dialog_width = 375 if prop.startswith("weather_") else 677

            row.enabled = not use_parent

        if use_parent:
            unset_properties(i3d_attributes, PROPS)


def draw_joint_attributes(layout: bpy.types.UILayout, i3d_attributes: bpy.types.PropertyGroup) -> None:
    PROPS = ('projection', 'projection_distance', 'projection_angle', 'x_axis_drive', 'y_axis_drive',
             'z_axis_drive', 'drive_position', 'drive_force_limit', 'drive_spring', 'drive_damping',
             'breakable_joint', 'joint_break_force', 'joint_break_torque')

    header, panel = layout.panel('i3d_joint_panel', default_closed=True)
    header.use_property_split = False
    header.prop(i3d_attributes, 'joint', text="")
    header.label(text="Joint")
    if panel:
        panel.enabled = i3d_attributes.joint
        for prop in PROPS:
            panel.prop(i3d_attributes, prop)

        if not i3d_attributes.joint:
            unset_properties(i3d_attributes, PROPS)


def draw_level_of_detail_attributes(layout: bpy.types.UILayout, obj: bpy.types.Object,
                                    i3d_attributes: bpy.types.PropertyGroup) -> None:
    header, panel = layout.panel('i3d_lod_panel', default_closed=True)
    header.label(text="Level of Detail (LOD)")
    if panel:
        for i in range(4):
            row = panel.row()
            row.enabled = i > 0 and len(obj.children) > i
            row.prop(i3d_attributes, 'lod_distances', index=i, text=f"Level {i}")

        panel.prop(i3d_attributes, 'lod_blending')


def draw_reference_file_attributes(layout: bpy.types.UILayout, i3d_reference: bpy.types.PropertyGroup) -> None:
    header, panel = layout.panel('i3d_reference_file_panel', default_closed=True)
    header.label(text="Reference File")
    if panel:
        panel.prop(i3d_reference, 'path')
        panel.prop(i3d_reference, 'runtime_loaded')
        panel.prop(i3d_reference, 'child_path', placeholder="0>")


def draw_merge_group_attributes(layout: bpy.types.UILayout, context: bpy.types.Context) -> None:
    obj = context.object
    header, panel = layout.panel('i3d_merge_group_panel', default_closed=False)
    header.label(text="Merge Group")
    if panel:
        panel.enabled = not obj.i3d_merge_children.enabled
        row = panel.row(align=True)
        row.operator('i3dio.choose_merge_group', text="", icon='DOWNARROW_HLT')

        merge_groups = context.scene.i3dio_merge_groups
        merge_group_index = obj.i3d_merge_group_index
        if merge_group_index == -1 or merge_group_index >= len(merge_groups):
            row.operator('i3dio.new_merge_group', text="New Merge Group", icon='ADD')
            if merge_group_index >= len(merge_groups):
                # Unset merge group index if out of range (e.g., after copy/paste between scenes)
                obj.property_unset('i3d_merge_group_index')
        else:
            merge_group = context.scene.i3dio_merge_groups[merge_group_index]
            row.prop(merge_group, "name", text="")
            row.operator('i3dio.select_merge_group_root', text="", icon="COLOR_RED")
            row.operator('i3dio.select_mg_objects', text="", icon='GROUP_VERTEX')
            row.operator('i3dio.new_merge_group', text="", icon='DUPLICATE')
            row.operator('i3dio.remove_from_merge_group', text="", icon='PANEL_CLOSE')


def draw_merge_children_attributes(layout: bpy.types.UILayout, i3d_merge_children: bpy.types.PropertyGroup) -> None:
    header, panel = layout.panel('i3d_merge_children_panel', default_closed=True)
    header.use_property_split = False
    header.prop(i3d_merge_children, 'enabled', text="")
    header.label(text="Merge Children")
    if panel:
        panel.enabled = i3d_merge_children.enabled
        panel.prop(i3d_merge_children, 'apply_transforms')
        panel.prop(i3d_merge_children, 'interpolation_steps')


def draw_i3d_mapping_box(layout: bpy.types.UILayout, i3d_mapping: bpy.types.PropertyGroup) -> None:
    box = layout.box()
    box.use_property_split = False
    row = box.row(align=True)
    row.alignment = 'CENTER'
    row.label(text="I3D Mapping")
    row = box.row(align=True)
    row.prop(i3d_mapping, 'is_mapped', text="Add to mapping")
    row = row.row(align=True)
    row.enabled = i3d_mapping.is_mapped
    row.prop(i3d_mapping, 'mapping_name', text="", placeholder="Custom Mapping Name")


@register
class I3D_IO_OT_choose_merge_group(bpy.types.Operator):
    bl_idname = "i3dio.choose_merge_group"
    bl_label = "Choose Merge Group"
    bl_description = "Choose a merge group to assign this object to"
    bl_options = {'INTERNAL', 'UNDO'}
    bl_property = "enum"

    def get_enum_options(self, context):
        merge_groups_item_list = sorted(
            [(str(idx), mg.name, "") for idx, mg in enumerate(context.scene.i3dio_merge_groups)], key=lambda x: x[1]
        )
        return merge_groups_item_list

    enum: EnumProperty(items=get_enum_options, name="Items")

    def execute(self, context):
        obj = context.object
        selected_mg_index = int(self.enum)
        if obj.i3d_merge_group_index != selected_mg_index:
            old_mg_index = obj.i3d_merge_group_index
            obj.i3d_merge_group_index = selected_mg_index
            if old_mg_index != -1:
                remove_merge_group_if_empty(context, old_mg_index)
            context.area.tag_redraw()
        else:
            print("same mg")
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}


@register
class I3D_IO_OT_new_merge_group(bpy.types.Operator):
    bl_idname = "i3dio.new_merge_group"
    bl_label = "New Merge Group"
    bl_description = "Create a new merge group"
    bl_options = {'INTERNAL', 'UNDO'}

    def execute(self, context):
        MERGE_GROUP_DEFAULT_NAME = "MergeGroup"

        obj = context.object
        name = MERGE_GROUP_DEFAULT_NAME
        count = 1
        while context.scene.i3dio_merge_groups.find(name) != -1:
            name = f"{MERGE_GROUP_DEFAULT_NAME}.{count:03d}"
            count += 1
        mg = context.scene.i3dio_merge_groups.add()

        mg.name = name
        mg.root = obj
        old_mg_index = obj.i3d_merge_group_index
        obj.i3d_merge_group_index = len(context.scene.i3dio_merge_groups) - 1
        if old_mg_index != -1:
            remove_merge_group_if_empty(context, old_mg_index)
        return {'FINISHED'}


def remove_merge_group_if_empty(context, mg_index):
    mg_member_count = 0
    objects_in_higher_indexed_merge_groups = []
    for obj in context.scene.objects:
        if obj.type == 'MESH' and obj.i3d_merge_group_index != -1:
            if obj.i3d_merge_group_index == mg_index:
                mg_member_count += 1
            else:
                objects_in_higher_indexed_merge_groups.append(obj)
    if mg_member_count == 0:
        context.scene.i3dio_merge_groups.remove(mg_index)
        for obj in objects_in_higher_indexed_merge_groups[mg_index::]:
            obj.i3d_merge_group_index -= 1
    else:
        print(f"{mg_member_count} members left in '{context.scene.i3dio_merge_groups[mg_index]}'")


@register
class I3D_IO_OT_remove_from_merge_group(bpy.types.Operator):
    bl_idname = "i3dio.remove_from_merge_group"
    bl_label = "Remove From Merge Group"
    bl_description = "Remove this object from it's current merge group"
    bl_options = {'INTERNAL', 'UNDO'}

    def execute(self, context):
        old_mg_index = context.object.i3d_merge_group_index
        context.object.i3d_merge_group_index = -1
        remove_merge_group_if_empty(context, old_mg_index)
        return {'FINISHED'}


@register
class I3D_IO_OT_select_merge_group_root(bpy.types.Operator):
    bl_idname = "i3dio.select_merge_group_root"
    bl_label = "Select Merge Group Root"
    bl_description = "When greyed out it means that the current object is the merge group root"
    bl_options = {'INTERNAL', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.scene.i3dio_merge_groups[context.object.i3d_merge_group_index].root is not context.object

    def execute(self, context):
        context.scene.i3dio_merge_groups[context.object.i3d_merge_group_index].root = context.object
        return {'FINISHED'}


@register
class I3D_IO_OT_select_mg_objects(bpy.types.Operator):
    bl_idname = "i3dio.select_mg_objects"
    bl_label = "Select Objects in MG"
    bl_description = "Select all objects in the same merge group"
    bl_options = {'INTERNAL', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.object.i3d_merge_group_index != -1

    def execute(self, context):
        for obj in context.scene.objects:
            mg_index = context.object.i3d_merge_group_index
            if obj.i3d_merge_group_index == mg_index:
                obj.select_set(True)
        return {'FINISHED'}


@persistent
def handle_old_merge_groups(dummy):
    for scene in bpy.data.scenes:
        for obj in scene.objects:
            if (old_mg := obj.get('i3d_merge_group')) is not None:
                group_id = old_mg.get('group_id')
                is_root = old_mg.get('is_root')
                if group_id is not None and group_id != "":
                    if (mg_idx := scene.i3dio_merge_groups.find(group_id)) != -1:
                        mg = scene.i3dio_merge_groups[mg_idx]
                        obj.i3d_merge_group_index = mg_idx
                    else:
                        mg = scene.i3dio_merge_groups.add()
                        mg.name = group_id
                        obj.i3d_merge_group_index = len(scene.i3dio_merge_groups) - 1
                    if is_root is not None and is_root == 1:
                        mg.root = obj
                del obj['i3d_merge_group']


@register
class I3D_IO_PT_mapping_bone_attributes(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_label = "I3D Mapping"
    bl_context = 'bone'

    @classmethod
    def poll(cls, context):
        return context.bone or context.edit_bone

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        bone = context.bone or context.edit_bone
        draw_i3d_mapping_box(layout, bone.i3d_mapping)


@register
class I3D_IO_PT_Object_Presets(presets.PresetPanel, Panel):
    bl_label = "Object Presets"
    preset_operator = "script.execute_preset"
    preset_add_operator = "i3dio.add_object_preset"

    @property
    def preset_subdir(self):
        subdir = presets.PresetSubdir() / 'object'
        match bpy.context.object.type:
            case 'EMPTY':
                return subdir / 'empty'
            case 'MESH':
                return subdir / 'mesh'
            case 'LIGHT':
                return subdir / 'light'
            case _:
                return subdir


@register
class I3D_IO_OT_Object_Add_Preset(presets.AddPresetBase, Operator):
    bl_idname = "i3dio.add_object_preset"
    bl_label = "Add an Object Preset"
    preset_menu = "I3D_IO_PT_Object_Presets"

    @property
    def preset_values(self):
        base_values = [f"bpy.context.object.i3d_attributes.{name}" for name, attributes in I3DNodeObjectAttributes.i3d_map.items() if attributes.get('preset_group', None) in ['ALL', bpy.context.object.type]]
        match bpy.context.object.type:
            case 'MESH':
                base_values.extend([f"bpy.context.object.data.i3d_attributes.{name}" for name in mesh.I3DNodeShapeAttributes.i3d_map.keys()])
            case 'LIGHT':
                base_values.extend([f"bpy.context.object.data.i3d_attributes.{name}" for name in light.I3DNodeLightAttributes.i3d_map.keys()])
        return base_values

    preset_subdir = I3D_IO_PT_Object_Presets.preset_subdir


@persistent
def handle_old_lod_distances(dummy):
    for obj in bpy.data.objects:
        if obj.type == 'EMPTY' and 'lod_distance' in obj.get('i3d_attributes', {}):
            current_lod = obj['i3d_attributes']['lod_distance']
            try:
                # Convert old string to list of floats
                lod_distance_values = [float(x) for x in current_lod.split()]

                # Ensure the list has exactly 4 elements, padding with 0.0 for missing values
                padded_length = len(lod_distance_values)
                lod_distance_values = (lod_distance_values + [0.0] * 4)[:4]
                lod_distance_values[0] = I3DNodeObjectAttributes.i3d_map['lod_distances']['default'][0]

                # Each value (except the first) must be >= the previous one
                # Only apply constraints to the original (unpadded) values
                for i in range(1, padded_length):
                    if lod_distance_values[i] < lod_distance_values[i - 1]:
                        lod_distance_values[i] = lod_distance_values[i - 1]

                obj.i3d_attributes.lod_distances = lod_distance_values
                del obj['i3d_attributes']['lod_distance']
            except (ValueError, AttributeError):
                pass


@persistent
def handle_old_reference_paths(dummy):
    for obj in bpy.data.objects:
        if obj.type == 'EMPTY' and (path := obj.get('i3d_reference_path')) is not None:
            obj.i3d_reference.path = path
            del obj['i3d_reference_path']


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Object.i3d_attributes = PointerProperty(type=I3DNodeObjectAttributes)
    bpy.types.Object.i3d_merge_group_index = IntProperty(default=-1)
    bpy.types.Object.i3d_mapping = PointerProperty(type=I3DMappingData)
    bpy.types.Bone.i3d_mapping = PointerProperty(type=I3DMappingData)
    bpy.types.EditBone.i3d_mapping = PointerProperty(type=I3DMappingData)
    bpy.types.Object.i3d_reference = PointerProperty(type=I3DReferenceData)
    bpy.types.Scene.i3dio_merge_groups = CollectionProperty(type=I3DMergeGroup)
    bpy.types.Object.i3d_merge_children = PointerProperty(type=I3DMergeChildren)
    load_post.append(handle_old_merge_groups)
    load_post.append(handle_old_lod_distances)
    load_post.append(handle_old_reference_paths)


def unregister():
    load_post.remove(handle_old_reference_paths)
    load_post.remove(handle_old_lod_distances)
    load_post.remove(handle_old_merge_groups)
    del bpy.types.Object.i3d_merge_children
    del bpy.types.Scene.i3dio_merge_groups
    del bpy.types.Object.i3d_reference
    del bpy.types.EditBone.i3d_mapping
    del bpy.types.Bone.i3d_mapping
    del bpy.types.Object.i3d_mapping
    del bpy.types.Object.i3d_merge_group_index
    del bpy.types.Object.i3d_attributes

    for cls in classes:
        bpy.utils.unregister_class(cls)
