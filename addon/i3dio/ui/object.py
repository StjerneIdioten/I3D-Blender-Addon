import bpy
from bpy.types import (
    Panel
)

from bpy.app.handlers import (persistent, save_pre, load_post)

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
        'lod_distance': {'name': 'lodDistance', 'default': "Enter your LOD Distances if needed."},
        'collision': {'name': 'collision', 'default': True},
        'collision_mask': {'name': 'collisionMask', 'default': 'ff', 'type': 'HEX'},
        'compound': {'name': 'compound', 'default': False},
        'trigger': {'name': 'trigger', 'default': False},
        'restitution': {'name': 'restitution', 'default': 0.0},
        'static_friction': {'name': 'staticFriction', 'default': 0.5},
        'dynamic_friction': {'name': 'dynamicFriction', 'default': 0.5},
        'linear_damping': {'name': 'linearDamping', 'default': 0.0},
        'angular_damping': {'name': 'angularDamping', 'default': 0.01},
        'density': {'name': 'density', 'default': 1.0},
        'split_type': {'name': 'splitType', 'default': 0},
        'split_uvs': {'name': 'splitUvs', 'default': (0.0, 0.0, 1.0, 1.0, 1.0)},
        'use_parent': {'name': 'useParent', 'default': True},
        'minute_of_day_start': {'name': 'minuteOfDayStart', 'default': 0},
        'minute_of_day_end': {'name': 'minuteOfDayEnd', 'default': 0},
        'day_of_year_start': {'name': 'dayOfYearStart', 'default': 0},
        'day_of_year_end': {'name': 'dayOfYearEnd', 'default': 0},
        'weather_required_mask': {'name': 'weatherRequiredMask', 'default': '0', 'type': 'HEX'},
        'weather_prevent_mask': {'name': 'weatherPreventMask', 'default': '0', 'type': 'HEX'},
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

    lod_distance: StringProperty(
        name="LOD Distance",
        description="For example:0 100",
        default=i3d_map['lod_distance']['default'],
        maxlen=1024
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
        description="Can be found at: Attributes -> Visibility Condition",
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
        obj = bpy.context.active_object
        
        i3d_property(layout, obj.i3d_attributes, 'visibility', obj)
        i3d_property(layout, obj.i3d_attributes, 'clip_distance', obj)
        i3d_property(layout, obj.i3d_attributes, 'min_clip_distance', obj)
        i3d_property(layout, obj.i3d_attributes, 'lod_distance', obj)

@register
class I3D_IO_PT_rigid_body_attributes(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_label = 'Rigidbody'
    bl_context = 'object'
    bl_parent_id = 'I3D_IO_PT_object_attributes'

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.type == 'MESH'

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        obj = bpy.context.active_object

        layout.prop(obj.i3d_attributes, 'rigid_body_type')

        if obj.i3d_attributes.rigid_body_type != 'none':
            row_compound = layout.row()
            row_compound.prop(obj.i3d_attributes, 'compound')

            if obj.i3d_attributes.rigid_body_type in ('static', 'compoundChild'):
                row_compound.enabled = False
                obj.i3d_attributes.property_unset('compound')

            layout.prop(obj.i3d_attributes, 'collision')
            layout.prop(obj.i3d_attributes, 'collision_mask')
            layout.prop(obj.i3d_attributes, 'trigger')
            layout.prop(obj.i3d_attributes, 'restitution')
            layout.prop(obj.i3d_attributes, 'static_friction')
            layout.prop(obj.i3d_attributes, 'dynamic_friction')
            layout.prop(obj.i3d_attributes, 'linear_damping')
            layout.prop(obj.i3d_attributes, 'angular_damping')
            layout.prop(obj.i3d_attributes, 'density')

            row_split_type_presets = layout.row()
            row_split_type_presets.prop(obj.i3d_attributes, 'split_type_presets')

            row_split_type = layout.row()
            row_split_type.prop(obj.i3d_attributes, 'split_type')

            split_uvs_col = layout.column()
            split_uvs_col.label(text="Split UVs")
            split_uvs_col.prop(obj.i3d_attributes, "split_uvs", index=0, text="Min U")
            split_uvs_col.prop(obj.i3d_attributes, "split_uvs", index=1, text="Min V")
            split_uvs_col.prop(obj.i3d_attributes, "split_uvs", index=2, text="Max U")
            split_uvs_col.prop(obj.i3d_attributes, "split_uvs", index=3, text="Max V")
            split_uvs_col.prop(obj.i3d_attributes, "split_uvs", index=4, text="UV World Scale")

            if obj.i3d_attributes.rigid_body_type != 'static':
                row_split_type.enabled = False
                row_split_type_presets.enabled = False
                split_uvs_col.enabled = False
                obj.i3d_attributes.property_unset('split_type')
                obj.i3d_attributes.property_unset('split_type_presets')
                obj.i3d_attributes.property_unset('split_uvs')
            else:
                if obj.i3d_attributes.split_type == 0:
                    split_uvs_col.enabled = False
                    obj.i3d_attributes.property_unset('split_uvs')

        else:
            # Reset all properties if rigidbody is disabled (This is easier than doing conditional export for now.
            # Since properties that are defaulted, wont get exported)
            obj.i3d_attributes.property_unset('compound')
            obj.i3d_attributes.property_unset('collision')
            obj.i3d_attributes.property_unset('collision_mask')
            obj.i3d_attributes.property_unset('trigger')
            obj.i3d_attributes.property_unset('restitution')
            obj.i3d_attributes.property_unset('static_friction')
            obj.i3d_attributes.property_unset('dynamic_friction')
            obj.i3d_attributes.property_unset('linear_damping')
            obj.i3d_attributes.property_unset('angular_damping')
            obj.i3d_attributes.property_unset('density')
            obj.i3d_attributes.property_unset('split_type')
            obj.i3d_attributes.property_unset('split_type_presets')
            obj.i3d_attributes.property_unset('split_uvs')


@register
class I3D_IO_PT_visibility_condition_attributes(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_label = 'Visibility Condition'
    bl_context = 'object'
    bl_parent_id = 'I3D_IO_PT_object_attributes'

    @classmethod
    def poll(cls, context):
        return context.object is not None

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        obj = bpy.context.active_object
        row = layout.row()
        row.prop(obj.i3d_attributes, 'use_parent')
        
        row = layout.row()
        row.prop(obj.i3d_attributes, 'minute_of_day_start')
        if obj.i3d_attributes.use_parent == True:
            row.enabled = False

        row = layout.row()
        row.prop(obj.i3d_attributes, 'minute_of_day_end')
        if obj.i3d_attributes.use_parent == True:
            row.enabled = False

        row = layout.row()
        row.prop(obj.i3d_attributes, 'day_of_year_start')
        if obj.i3d_attributes.use_parent == True:
            row.enabled = False

        row = layout.row()
        row.prop(obj.i3d_attributes, 'day_of_year_end')
        if obj.i3d_attributes.use_parent == True:
            row.enabled = False


        row = layout.row()
        row.prop(obj.i3d_attributes, 'weather_required_mask')
        if obj.i3d_attributes.use_parent == True:
            row.enabled = False

        row = layout.row()
        row.prop(obj.i3d_attributes, 'weather_prevent_mask')
        if obj.i3d_attributes.use_parent == True:
            row.enabled = False

        if obj.i3d_attributes.use_parent == True:
            obj.i3d_attributes.property_unset('minute_of_day_start')
            obj.i3d_attributes.property_unset('minute_of_day_end')
            obj.i3d_attributes.property_unset('day_of_year_start')
            obj.i3d_attributes.property_unset('day_of_year_end')
            obj.i3d_attributes.property_unset('weather_required_mask')
            obj.i3d_attributes.property_unset('weather_prevent_mask')

@register
class I3DMergeGroupMemberObject(bpy.types.PropertyGroup):
    object: PointerProperty(
        name="Merge Group Member",
        type=bpy.types.Object,
		)

@register
class I3DMergeGroup(bpy.types.PropertyGroup):
    def add_member(self, member_object):
        self.members.add().object = member_object

    def remove_member(self, member_object):
        for idx,member in enumerate(self.members):
            if member.object is member_object:
                self.members.remove(idx)

    name: StringProperty(
        name='Merge Group Name',
        description='The name of the merge group',
        default='MergeGroup'
    )

    members: CollectionProperty(
        name="Members",
        description="Members of the merge group",
        type=I3DMergeGroupMemberObject)

    root: PointerProperty(
        name="Merge Group Root Object",
        description="The object acting as the root for the merge group",
        type=bpy.types.Object,
		)
  
@register
class I3D_IO_PT_merge_group_attributes(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_label = 'Merge Group'
    bl_context = 'object'
    bl_parent_id = 'I3D_IO_PT_object_attributes'

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.type == 'MESH'

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        obj = context.object

        row = layout.row(align=True)
        row.use_property_decorate = False

        row.operator('i3dio.choose_merge_group', text="", icon='DOWNARROW_HLT')

        col = row.column(align=True)
        merge_group_index = obj.i3d_merge_group_index 
        if merge_group_index == -1:
            col.operator("i3dio.new_merge_group", text="New", icon="ADD")
        else:
            merge_group = context.scene.i3dio_merge_groups[merge_group_index]
            col.prop(merge_group, "name", text="")
            col = row.column(align=True)
            col.operator('i3dio.select_merge_group_root', text="", icon="COLOR_RED")
            col = row.column(align=True)
            col.operator('i3dio.select_mg_objects', text="", icon='GROUP_VERTEX')
            col = row.column(align=True)
            col.operator('i3dio.new_merge_group', text="", icon='DUPLICATE')
            col = row.column(align=True)
            col.operator('i3dio.remove_merge_group', text="", icon='PANEL_CLOSE')


@register
class I3D_IO_OT_choose_merge_group(bpy.types.Operator):
    bl_idname = "i3dio.choose_merge_group"
    bl_label = "Choose Merge Group"
    bl_description = "Choose a merge group to assign this object to"
    bl_options = {'INTERNAL', 'UNDO'}
    bl_property = "enum"

    def get_enum_options(self, context):
        merge_groups_item_list = sorted([(str(idx), mg.name, "") for idx,mg in enumerate(context.scene.i3dio_merge_groups)],key=lambda x: x[1])
        return merge_groups_item_list

    enum: EnumProperty(items=get_enum_options, name="Items")

    def execute(self, context):
        obj = context.object
        selected_mg_index = int(self.enum)
        if obj.i3d_merge_group_index != selected_mg_index:
            context.scene.i3dio_merge_groups[obj.i3d_merge_group_index].remove_member(obj)
            context.scene.i3dio_merge_groups[selected_mg_index].add_member(obj)
            obj.i3d_merge_group_index = selected_mg_index
            context.area.tag_redraw()
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
        if obj.i3d_merge_group_index != -1:
            context.scene.i3dio_merge_groups[obj.i3d_merge_group_index].remove_member(obj)
        mg.name = name
        mg.root = obj
        mg.add_member(obj)
        obj.i3d_merge_group_index = len(context.scene.i3dio_merge_groups) - 1
        return {'FINISHED'}
    
    
@register
class I3D_IO_OT_remove_merge_group(bpy.types.Operator):
    bl_idname = "i3dio.remove_merge_group"
    bl_label = "Remove From Merge Group"
    bl_description = "Remove this object from it's current merge group"
    bl_options = {'INTERNAL', 'UNDO'}

    def execute(self, context):
        mg_index = context.object.i3d_merge_group_index
        for member in context.scene.i3dio_merge_groups[mg_index].members:
            member.object.i3d_merge_group_index = -1
        context.scene.i3dio_merge_groups.remove(mg_index)
        for mg in context.scene.i3dio_merge_groups[mg_index::]:
            for member in mg.members:
                member.object.i3d_merge_group_index -= 1
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
        for member in context.scene.i3dio_merge_groups[context.object.i3d_merge_group_index].members:
            if member.object is not None:
                member.object.select_set(True)
            else:
                print("Deleted Member Object")
        return {'FINISHED'}

@persistent
def prune_merge_groups(dummy):
    for scene in bpy.data.scenes:
        for mg in scene.i3dio_merge_groups:
            for idx, member in reversed(list(enumerate(mg.members))):
                if member.object is None:
                    mg.members.remove(idx)

@persistent
def handle_old_merge_groups(dummy):
    for scene in bpy.data.scenes:
        for obj in scene.objects:
            if (old_mg := obj.get('i3d_merge_group')) != None:
                group_id = old_mg.get('group_id')
                is_root = old_mg.get('is_root')
                if group_id != None and group_id != "":
                    if (mg_idx := scene.i3dio_merge_groups.find(group_id)) != -1:
                        mg = scene.i3dio_merge_groups[mg_idx]
                        obj.i3d_merge_group_index = mg_idx
                    else:
                        mg = scene.i3dio_merge_groups.add()
                        mg.name = group_id
                        obj.i3d_merge_group_index = len(scene.i3dio_merge_groups) - 1
                    mg.add_member(obj)
                    if is_root != None and is_root == 1:
                        mg.root = obj
                del obj['i3d_merge_group']

@register
class I3D_IO_PT_joint_attributes(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_label = 'Joint'
    bl_context = 'object'
    bl_parent_id = 'I3D_IO_PT_object_attributes'

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.type == 'EMPTY'

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        obj = context.object

        layout.prop(obj.i3d_attributes, 'joint')

        properties = [
            ('projection',),
            ('x_axis_drive',),
            ('y_axis_drive',),
            ('z_axis_drive',),
            ('drive_position',),
            ('projection_distance',),
            ('projection_angle',),
            ('drive_force_limit',),
            ('drive_spring',),
            ('drive_damping',),
            ('breakable_joint',),
            ('joint_break_force',),
            ('joint_break_torque',)
        ]

        for prop in properties:
            row = layout.row()
            row.prop(obj.i3d_attributes, prop[0])
            if obj.i3d_attributes.joint is False:
                row.enabled = False
                obj.i3d_attributes.property_unset(prop[0])


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
class I3D_IO_PT_mapping_attributes(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_label = "I3D Mapping"
    bl_context = 'object'
    bl_parent_id = 'I3D_IO_PT_object_attributes'

    @classmethod
    def poll(cls, context):
        return context.object is not None

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        obj = bpy.context.active_object

        row = layout.row()
        row.prop(obj.i3d_mapping, 'is_mapped')
        row = layout.row()
        row.prop(obj.i3d_mapping, 'mapping_name')

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Object.i3d_attributes = PointerProperty(type=I3DNodeObjectAttributes)
    bpy.types.Object.i3d_merge_group_index = IntProperty(default = -1)
    bpy.types.Object.i3d_mapping = PointerProperty(type=I3DMappingData)
    bpy.types.Scene.i3dio_merge_groups = CollectionProperty(type=I3DMergeGroup)
    save_pre.append(prune_merge_groups)
    load_post.append(handle_old_merge_groups)

def unregister():
    load_post.remove(handle_old_merge_groups)
    save_pre.remove(prune_merge_groups)
    del bpy.types.Scene.i3dio_merge_groups
    del bpy.types.Object.i3d_mapping
    del bpy.types.Object.i3d_merge_group_index
    del bpy.types.Object.i3d_attributes

    for cls in classes:
        bpy.utils.unregister_class(cls)
