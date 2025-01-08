import bpy
from bpy.types import (
    Panel
)

from bpy.app.handlers import (persistent, load_post)

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

from .collision_data import COLLISIONS_ENUM_LIST, COLLISIONS

classes = []


def register(cls):
    classes.append(cls)
    return cls


@register
class I3DNodeObjectAttributes(bpy.types.PropertyGroup):
    i3d_map = {
        'visibility': {'name': 'visibility', 'default': True, 'tracking': {'member_path': 'hide_render',
                                                                           'mapping': {True: False,
                                                                                       False: True}}},
        'clip_distance': {'name': 'clipDistance', 'default': 1000000.0},
        'min_clip_distance': {'name': 'minClipDistance', 'default': 0.0},
        'object_mask': {'name': 'objectMask', 'default': '0', 'type': 'HEX'},
        'rigid_body_type': {'default': 'none'},
        'lod_distances': {'name': 'lodDistance', 'default': (0.0, 0.0, 0.0, 0.0)},
        'lod_blending': {'name': 'lodBlending', 'default': True},
        'collision': {'name': 'collision', 'default': True},
        'collision_filter_group': {'name': 'collisionFilterGroup', 'default': 'ff', 'type': 'HEX'},
        'collision_filter_mask': {'name': 'collisionFilterMask', 'default': 'ff', 'type': 'HEX'},
        'compound': {'name': 'compound', 'default': False},
        'trigger': {'name': 'trigger', 'default': False},
        'restitution': {'name': 'restitution', 'default': 0.0},
        'static_friction': {'name': 'staticFriction', 'default': 0.5},
        'dynamic_friction': {'name': 'dynamicFriction', 'default': 0.5},
        'linear_damping': {'name': 'linearDamping', 'default': 0.0},
        'angular_damping': {'name': 'angularDamping', 'default': 0.01},
        'density': {'name': 'density', 'default': 1.0},
        'solver_iteration_count': {'name': 'solverIterationCount', 'default': 4},
        'split_type': {'name': 'splitType', 'default': 0},
        'split_uvs': {'name': 'splitUvs', 'default': (0.0, 0.0, 1.0, 1.0, 1.0)},
        'minute_of_day_start': {'name': 'minuteOfDayStart', 'default': 0},
        'minute_of_day_end': {'name': 'minuteOfDayEnd', 'default': 0},
        'day_of_year_start': {'name': 'dayOfYearStart', 'default': 0},
        'day_of_year_end': {'name': 'dayOfYearEnd', 'default': 0},
        'weather_required_mask': {'name': 'weatherRequiredMask', 'default': '0', 'type': 'HEX'},
        'weather_prevent_mask': {'name': 'weatherPreventMask', 'default': '0', 'type': 'HEX'},
        'viewer_spaciality_required_mask': {'name': 'viewerSpacialityRequiredMask', 'default': '0', 'type': 'HEX'},
        'viewer_spaciality_prevent_mask': {'name': 'viewerSpacialityPreventMask', 'default': '0', 'type': 'HEX'},
        'render_invisible': {'name': 'renderInvisible', 'default': False},
        'visible_shader_parameter': {'name': 'visibleShaderParameter', 'default': 1.0},
        'joint': {'name': 'joint', 'default': False},
        'projection': {'name': 'projection', 'default': False},
        'projection_distance': {'name': 'projDistance', 'default': 0.01},
        'projection_angle': {'name': 'projAngle', 'default': 0.01},
        'x_axis_drive': {'name': 'xAxisDrive', 'default': False},
        'y_axis_drive': {'name': 'yAxisDrive', 'default': False},
        'z_axis_drive': {'name': 'zAxisDrive', 'default': False},
        'drive_position': {'name': 'drivePos', 'default': False},
        'drive_force_limit': {'name': 'driveForceLimit', 'default': 100000.0},
        'drive_spring': {'name': 'driveSpring', 'default': 1.0},
        'drive_damping': {'name': 'driveDamping', 'default': 0.01},
        'breakable_joint': {'name': 'breakableJoint', 'default': False},
        'joint_break_force': {'name': 'jointBreakForce', 'default': 0.0},
        'joint_break_torque': {'name': 'jointBreakTorque', 'default': 0.0},
    }

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

    rendered_in_viewports: BoolProperty(
        name="Rendered In Viewports",
        description="Determines if the object is rendered in Giants Editor viewport",
        default=i3d_map['rendered_in_viewports']['default']
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

    def collision_preset_items(self, _context) -> list[tuple[str, str, str]]:
        return COLLISIONS_ENUM_LIST

    def collision_preset_update(self, _context) -> None:
        preset_name = self.collisions_preset

        if preset_name == "NONE":
            self.collision_filter_group = self.i3d_map['collision_filter_group']['default']
            self.collision_filter_mask = self.i3d_map['collision_filter_mask']['default']
            return

        if preset_name in COLLISIONS['presets']:
            preset = COLLISIONS['presets'][preset_name]

            self.collision_filter_group = preset.group_hex
            self.collision_filter_mask = preset.mask_hex

    collisions_preset: EnumProperty(
        name="Collision Preset",
        description="Select a collision preset",
        items=collision_preset_items,
        default=0,
        options=set(),
        update=collision_preset_update
    )

    collision_filter_group: StringProperty(
        name="Collision Filter Group",
        description="The objects collision filter group as a hexadecimal value",
        default=i3d_map['collision_filter_group']['default'],
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

    split_type_presets: EnumProperty(
        name="Split Type Presets",
        description="List containing all in-game tree types.",
        items=[
            ('0', "Custom / Manual", "Set a custom tree type or just set a tree type manually"),
            ('1', "Spruce", "Spruce supports wood harvester"),
            ('2', "Pine", "Pine supports wood harvester"),
            ('3', "Larch", "Larch supports wood harvester"),
            ('4', "Birch", "Birch doesn't support wood harvester"),
            ('5', "Beech", "Beech doesn't support wood harvester"),
            ('6', "Maple", "Maple doesn't support wood harvester"),
            ('7', "Oak", "Oak doesn't support wood harvester"),
            ('8', "Ash", "Ash doesn't support wood harvester"),
            ('9', "Locust", "Locust doesn't support wood harvester"),
            ('10', "Mahogany", "Mahogany doesn't support wood harvester"),
            ('11', "Poplar", "Poplar doesn't support wood harvester"),
            ('12', "American Elm", "American Elm doesn't support wood harvester"),
            ('13', "Cypress", "Cypress doesn't support wood harvester"),
            ('14', "Downy Serviceberry", "Downy Serviceberry doesn't support wood harvester"),
            ('15', "Pagoda Dogwood", "Pagoda Dogwood doesn't support wood harvester"),
            ('16', "Shagbark Hickory", "Shagbark Hickory doesn't support wood harvester"),
            ('17', "Stone Pine", "Stone Pine doesn't support wood harvester"),
            ('18', "Willow", "Willow doesn't support wood harvester"),
            ('19', "Olive Tree", "Olive Tree doesn't support wood harvester")
        ],
        default='0',
        update=lambda self, context: setattr(self, 'split_type', int(self.split_type_presets))
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
        description="If enabled, use the parent visibility conditions. All properties will export as expected, "
        "but they will not appear in Giants Editor unless weatherPreventMask is set to a value other than 0",
        default=True
    )

    minute_of_day_start: IntProperty(
        name="Minute of Day Start",
        description="The minute of day when visibility is true. "
                    "8:00 AM = 480 / "
                    "8:00 PM = 1200",
        default=i3d_map['minute_of_day_start']['default'],
        max=1440,
        min=0,
    )

    minute_of_day_end: IntProperty(
        name="Minute of Day End",
        description="The minute of day when visibility is false. "
                    "8:00 AM = 480 / "
                    "8:00 PM = 1200",
        default=i3d_map['minute_of_day_end']['default'],
        max=1440,
        min=0,
    )

    day_of_year_start: IntProperty(
        name="Day of Year Start",
        description="Day of Year when visibility is true.",
        default=i3d_map['day_of_year_start']['default'],
        max=365,
        min=0,
    )

    day_of_year_end: IntProperty(
        name="Day of Year End",
        description="Day of Year when visibility is false.",
        default=i3d_map['day_of_year_end']['default'],
        max=365,
        min=0,
    )

    weather_required_mask: StringProperty(
        name="Weather Required Mask (Hex)",
        description="The weather required mask as a hexadecimal value. "
                    "Winter = 400 / "
                    "Winter + Snow = 408",
        default=i3d_map['weather_required_mask']['default']
    )

    weather_prevent_mask: StringProperty(
        name="Weather Prevent Mask (Hex)",
        description="The weather prevent mask as a hexadecimal value. "
                    "Summer = 100 / "
                    "Summer + Sun = 101",
        default=i3d_map['weather_prevent_mask']['default']
    )

    viewer_spaciality_required_mask: StringProperty(
        name="Viewer Spaciality Required Mask (Hex)",
        description="The Viewer Spaciality Required Mask as a hexadecimal value.",
        default=i3d_map['viewer_spaciality_required_mask']['default']
    )

    viewer_spaciality_prevent_mask: StringProperty(
        name="Viewer Spaciality Prevent Mask (Hex)",
        description="The Viewer Spaciality Prevent Mask as a hexadecimal value.",
        default=i3d_map['viewer_spaciality_prevent_mask']['default']
    )

    render_invisible: BoolProperty(
        name="Render Invisible",
        description='If set, the object is always rendered and "visibility"'
        'must be controlled in the shader using the visible shader parameter',
        default=i3d_map['render_invisible']['default']
    )

    visible_shader_parameter: FloatProperty(
        name="Visible Shader Parameter",
        description='This value is applied to the "visibility" shader parameter when the object is visible.'
        'If conditions are not met, 0 is passed to the shader.',
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
        description="If checked, the reference file will be loaded at runtime",
        default=False
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
        type=bpy.types.Object,
    )


@register
class I3D_IO_PT_object_attributes(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_label = "I3D Object Attributes"
    bl_context = 'object'

    @classmethod
    def poll(cls, context):
        return context.object is not None

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        obj = context.object
        i3d_attributes = obj.i3d_attributes

        i3d_property(layout, i3d_attributes, 'visibility', obj)
        i3d_property(layout, i3d_attributes, 'clip_distance', obj)
        i3d_property(layout, i3d_attributes, 'min_clip_distance', obj)
      
        layout.prop(obj.i3d_attributes, 'exclude_from_export')

        if obj.type == 'MESH':
            draw_rigid_body_attributes(layout, i3d_attributes)
            draw_merge_group_attributes(layout, obj)

        if obj.type == 'EMPTY':
            layout.prop(i3d_attributes, 'lod_distance', placeholder="Enter your LOD Distances if needed.")

            if obj.type == 'EMPTY':
            child_count = len(obj.children)
            header, panel = layout.panel('i3d_lod_panel', default_closed=True)
            header.label(text="Level of Detail (LOD)")
            if panel:
                for i in range(4):
                    row = panel.row()
                    row.enabled = i > 0 and child_count > i
                    row.prop(obj.i3d_attributes, 'lod_distances', index=i, text=f"Level {i}")

                panel.prop(obj.i3d_attributes, 'lod_blending')

            header, panel = layout.panel("i3d_reference", default_closed=False)
            header.label(text="Reference File")
            if panel:
                panel.use_property_split = True
                panel.prop(obj.i3d_reference, 'path')
                row = panel.row()
                row.enabled = obj.i3d_reference.path != '' and obj.i3d_reference.path.endswith('.i3d')
                row.prop(obj.i3d_reference, 'runtime_loaded')

            draw_joint_attributes(layout, i3d_attributes)

        header, panel = layout.panel("i3d_mapping_attributes", default_closed=False)
        header.label(text="I3D Mapping")
        if panel:
            panel.use_property_split = True
            panel.prop(obj.i3d_mapping, 'is_mapped')
            row = panel.row()
            row.enabled = obj.i3d_mapping.is_mapped
            row.prop(obj.i3d_mapping, 'mapping_name', placeholder="myCube")

        draw_visibility_condition_attributes(layout, i3d_attributes)


def draw_rigid_body_attributes(layout, i3d_attributes) -> None:
    def _unset_rigidbody_properties(attributes) -> None:
        """Helper function to unset all rigid body-related properties."""
        for prop in ['compound', 'collision', 'trigger', 'restitution',
                     'static_friction', 'dynamic_friction', 'linear_damping', 'angular_damping',
                     'density', 'solver_iteration_count', 'split_type', 'split_type_presets', 'split_uvs']:
            attributes.property_unset(prop)

    header, panel = layout.panel("i3d_rigid_body_attributes", default_closed=False)
    header.label(text="Rigidbody")
    if panel:
        panel.prop(i3d_attributes, 'rigid_body_type')

        if i3d_attributes.rigid_body_type == 'none':
            _unset_rigidbody_properties(i3d_attributes)
            return

        row_compound = panel.row()
        row_compound.prop(i3d_attributes, 'compound')
        if i3d_attributes.rigid_body_type in ('static', 'compoundChild'):
            row_compound.enabled = False
            i3d_attributes.property_unset('compound')

        panel.prop(i3d_attributes, 'collision')
        panel.prop(i3d_attributes, 'trigger')

        panel.separator(factor=2, type='LINE')
        panel.prop(i3d_attributes, 'collisions_preset')
        panel.prop(i3d_attributes, 'collision_filter_group')
        panel.prop(i3d_attributes, 'collision_filter_mask')
        panel.separator(factor=2, type='LINE')

        panel.prop(i3d_attributes, 'restitution')
        panel.prop(i3d_attributes, 'static_friction')
        panel.prop(i3d_attributes, 'dynamic_friction')
        panel.prop(i3d_attributes, 'linear_damping')
        panel.prop(i3d_attributes, 'angular_damping')
        panel.prop(i3d_attributes, 'density')
        panel.prop(i3d_attributes, 'solver_iteration_count')

        panel.separator(factor=2, type='LINE')
        # Split type
        row = panel.row(align=True)
        row.use_property_split = False
        row.prop(i3d_attributes, "split_type")
        row.prop(i3d_attributes, "split_type_presets", text="", icon_only=True, icon="NONE")

        split_uvs_col = panel.column()
        split_uvs_col.use_property_split = False
        split_uvs_col.label(text="Split UVs")
        grid = split_uvs_col.grid_flow(row_major=True, columns=2, align=True)
        grid.prop(i3d_attributes, "split_uvs", index=0, text="Min U")
        grid.prop(i3d_attributes, "split_uvs", index=2, text="Max U")
        grid.prop(i3d_attributes, "split_uvs", index=1, text="Min V")
        grid.prop(i3d_attributes, "split_uvs", index=3, text="Max V")
        split_uvs_col.prop(i3d_attributes, "split_uvs", index=4, text="UV World Scale")

        # Disable split type and split UVs if rigid body type is static
        if i3d_attributes.rigid_body_type != 'static':
            row.enabled = False
            split_uvs_col.enabled = False
            i3d_attributes.property_unset('split_type')
            i3d_attributes.property_unset('split_uvs')
        elif i3d_attributes.split_type == 0:
            split_uvs_col.enabled = False
            i3d_attributes.property_unset('split_uvs')


def draw_visibility_condition_attributes(layout, i3d_attributes) -> None:
    props = ['minute_of_day_start', 'minute_of_day_end', 'day_of_year_start', 'day_of_year_end',
             'weather_required_mask', 'weather_prevent_mask', 'viewer_spaciality_required_mask',
             'viewer_spaciality_prevent_mask', 'render_invisible', 'visible_shader_parameter']

    def _unset_visibility_condition_properties(attributes) -> None:
        """Helper function to unset all visibility condition-related properties."""
        for prop in props:
            attributes.property_unset(prop)

    # Turn off for header property
    layout.use_property_split = False
    header, panel = layout.panel("i3d_visibility_condition_attributes", default_closed=True)
    header.prop(i3d_attributes, 'use_parent', text='Visibility Condition')
    if panel:
        if i3d_attributes.use_parent:
            _unset_visibility_condition_properties(i3d_attributes)

        panel.enabled = not i3d_attributes.use_parent

        # NOTE: Seems like the only way this will be used in GE is if you set weatherPreventMask to something
        # "useParent" is not a attribute in I3D, its simply just a toggle in their panel
        panel.use_property_split = True
        for prop in props:
            panel.prop(i3d_attributes, prop)


def draw_joint_attributes(layout, i3d_attributes):
    layout.use_property_split = False
    header, panel = layout.panel("i3d_joint_attributes", default_closed=True)
    header.prop(i3d_attributes, 'joint', text='Joint')
    if panel:
        panel.use_property_split = True
        panel.enabled = i3d_attributes.joint
        panel.prop(i3d_attributes, 'projection')
        panel.prop(i3d_attributes, 'projection_distance')
        panel.prop(i3d_attributes, 'projection_angle')
        panel.prop(i3d_attributes, 'x_axis_drive')
        panel.prop(i3d_attributes, 'y_axis_drive')
        panel.prop(i3d_attributes, 'z_axis_drive')
        panel.prop(i3d_attributes, 'drive_position')
        panel.prop(i3d_attributes, 'drive_force_limit')
        panel.prop(i3d_attributes, 'drive_spring')
        panel.prop(i3d_attributes, 'drive_damping')
        panel.prop(i3d_attributes, 'breakable_joint')
        panel.prop(i3d_attributes, 'joint_break_force')
        panel.prop(i3d_attributes, 'joint_break_torque')


def draw_merge_group_attributes(layout, obj):
    layout.use_property_split = True
    header, panel = layout.panel("i3d_merge_group_attributes", default_closed=False)
    header.label(text="Merge Group")
    if panel:
        row = panel.row(align=True)
        row.operator('i3dio.choose_merge_group', text="", icon='DOWNARROW_HLT')

        col = row.column(align=True)
        merge_group_index = obj.i3d_merge_group_index

        if merge_group_index == -1:
            col.operator("i3dio.new_merge_group", text="New", icon="ADD")
        else:
            merge_group = bpy.context.scene.i3dio_merge_groups[merge_group_index]
            col.prop(merge_group, "name", text="")
            col = row.column(align=True)
            col.operator('i3dio.select_merge_group_root', text="", icon="COLOR_RED")
            col = row.column(align=True)
            col.operator('i3dio.select_mg_objects', text="", icon='GROUP_VERTEX')
            col = row.column(align=True)
            col.operator('i3dio.new_merge_group', text="", icon='DUPLICATE')
            col = row.column(align=True)
            col.operator('i3dio.remove_from_merge_group', text="", icon='PANEL_CLOSE')


@register
class I3D_IO_OT_choose_merge_group(bpy.types.Operator):
    bl_idname = "i3dio.choose_merge_group"
    bl_label = "Choose Merge Group"
    bl_description = "Choose a merge group to assign this object to"
    bl_options = {'INTERNAL', 'UNDO'}
    bl_property = "enum"

    def get_enum_options(self, context):
        merge_groups_item_list = sorted([(str(idx), mg.name, "") for idx, mg in
                                         enumerate(context.scene.i3dio_merge_groups)], key=lambda x: x[1])
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
    bl_options = {'INTERNAL'}

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
    bl_options = {'UNDO'}

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


@persistent
def handle_old_reference_paths(dummy):
    for obj in bpy.data.objects:
        if obj.type == 'EMPTY' and (path := obj.get('i3d_reference_path')) is not None:
            obj.i3d_reference.path = path
            del obj['i3d_reference_path']


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

        row = layout.row()
        row.prop(bone.i3d_mapping, 'is_mapped')
        row = layout.row()
        row.prop(bone.i3d_mapping, 'mapping_name')


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


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Object.i3d_attributes = PointerProperty(type=I3DNodeObjectAttributes)
    bpy.types.Object.i3d_merge_group_index = IntProperty(default=-1)
    bpy.types.Object.i3d_mapping = PointerProperty(type=I3DMappingData)
    bpy.types.Object.i3d_reference = PointerProperty(type=I3DReferenceData)
    bpy.types.Bone.i3d_mapping = PointerProperty(type=I3DMappingData)
    bpy.types.EditBone.i3d_mapping = PointerProperty(type=I3DMappingData)
    bpy.types.Scene.i3dio_merge_groups = CollectionProperty(type=I3DMergeGroup)
    load_post.append(handle_old_merge_groups)
    load_post.append(handle_old_reference_paths)
    load_post.append(handle_old_lod_distances)


def unregister():
    load_post.remove(handle_old_lod_distances)
    load_post.remove(handle_old_merge_groups)
    del bpy.types.Scene.i3dio_merge_groups
    del bpy.types.Object.i3d_reference
    del bpy.types.EditBone.i3d_mapping
    del bpy.types.Bone.i3d_mapping
    del bpy.types.Object.i3d_mapping
    del bpy.types.Object.i3d_merge_group_index
    del bpy.types.Object.i3d_attributes

    for cls in classes:
        bpy.utils.unregister_class(cls)
