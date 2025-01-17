import bpy
from pathlib import Path

classes = []


def register(cls):
    classes.append(cls)
    return cls


ATTRIBUTE_MAP = {
    "UNIVERSAL": [
        "visibility", "clip_distance", "min_clip_distance", "object_mask", "exclude_from_export"
    ],
    "MESH": [
        "rigid_body_type", "collision", "collision_mask", "compound", "trigger", "restitution", "static_friction",
        "dynamic_friction", "linear_damping", "angular_damping", "density", "solver_iteration_count",
        "split_type", "split_uvs",
    ],
    "MESH_DATA": [  # mesh.i3d_attributes
        "casts_shadows", "receive_shadows", "non_renderable", "distance_blending", "rendered_in_viewports",
        "is_occluder", "cpu_mesh", "nav_mesh_mask", "decal_layer", "fill_volume", "use_vertex_colors",
    ],
    "EMPTY": [
        "lod_distances", "lod_blending", "use_parent", "minute_of_day_start", "minute_of_day_end", "day_of_year_start",
        "day_of_year_end", "weather_required_mask", "weather_prevent_mask", "viewer_spaciality_required_mask",
        "viewer_spaciality_prevent_mask", "render_invisible", "visible_shader_parameter", "joint", "projection",
        "projection_distance", "projection_angle", "x_axis_drive", "y_axis_drive", "z_axis_drive", "drive_position",
        "drive_force_limit", "drive_spring", "drive_damping",
        "breakable_joint", "joint_break_force", "joint_break_torque",
    ],
}


class PresetManager:
    """Utility class for managing preset files"""
    preset_dir = Path(bpy.utils.user_resource('SCRIPTS', path="presets/i3dio", create=True))
    addon_preset_dir = Path(__file__).parent

    @staticmethod
    def get_preset_filepath(name):
        return PresetManager.preset_dir / f"{name}.py"

    @staticmethod
    def list_presets(subdir=None):
        """List presets in the given subdirectory or all directories"""
        preset_dir = PresetManager.addon_preset_dir / subdir if subdir else PresetManager.preset_dir
        return list(preset_dir.glob("*.py")) if preset_dir.exists() else []

    @staticmethod
    def save_preset(name, grouped_values):
        filepath = PresetManager.get_preset_filepath(name)
        with filepath.open("w", encoding="utf-8") as file:
            file.write("import bpy\n")
            file.write("obj = bpy.context.object\n\n")

            # Write universal attributes
            for attr, value in grouped_values["UNIVERSAL"].items():
                file.write(f"obj.i3d_attributes.{attr} = {repr(value)}\n")

            # Write mesh-specific attributes under 'if obj.type == "MESH":'
            if grouped_values["MESH"]:
                file.write("\nif obj.type == 'MESH':\n")
                for attr, value in grouped_values["MESH"].items():
                    file.write(f"    obj.data.i3d_attributes.{attr} = {repr(value)}\n")

            # Write empty-specific attributes under 'if obj.type == "EMPTY":'
            if grouped_values["EMPTY"]:
                file.write("\nif obj.type == 'EMPTY':\n")
                for attr, value in grouped_values["EMPTY"].items():
                    file.write(f"    obj.i3d_attributes.{attr} = {repr(value)}\n")

        return filepath

    @staticmethod
    def collect_attributes(source: bpy.types.Object, obj_type: str) -> dict:
        """Collect attributes explicitly defined in a PropertyGroup based on object type."""
        # Combine universal attributes with type-specific attributes
        applicable_attributes = ATTRIBUTE_MAP.get("UNIVERSAL", [])
        applicable_attributes += ATTRIBUTE_MAP.get(obj_type, [])

        if obj_type == "MESH":
            applicable_attributes += ATTRIBUTE_MAP.get("MESH_DATA", [])

        grouped_values = {"UNIVERSAL": {}, "MESH": {}, "EMPTY": {}}

        for attr in applicable_attributes:
            try:
                value = getattr(source.i3d_attributes, attr)
                if isinstance(value, bpy.types.bpy_prop_array):
                    value = list(value)
                if obj_type == "MESH" and attr in ATTRIBUTE_MAP["MESH_DATA"]:
                    grouped_values["MESH"][attr] = value
                elif obj_type == "EMPTY" and attr in ATTRIBUTE_MAP["EMPTY"]:
                    grouped_values["EMPTY"][attr] = value
                else:
                    grouped_values["UNIVERSAL"][attr] = value
            except AttributeError:
                pass  # Skip attributes that cannot be accessed
        return grouped_values


def get_preset_items():
    """Dynamically build a list of (value, label, description) tuples."""
    items = []
    for file in PresetManager.list_presets():
        name = file.stem
        items.append((name, name, f"Delete the preset '{name}'"))
    if not items:
        items.append(("NONE", "No Presets Found", ""))
    return items


@register
class I3D_IO_OT_DeletePreset(bpy.types.Operator):
    bl_idname = "i3dio.delete_preset"
    bl_label = "Delete Preset"
    bl_description = "Delete a preset file"

    preset_to_delete: bpy.props.EnumProperty(
        name="Preset",
        description="Which preset to delete",
        items=get_preset_items(),
    )

    def execute(self, context):
        preset_filepath = PresetManager.get_preset_filepath(self.preset_to_delete)
        if preset_filepath.exists():
            preset_filepath.unlink()
            self.report({'INFO'}, f"Preset deleted: {preset_filepath}")
        else:
            self.report({'ERROR'}, f"Preset not found: {preset_filepath}")
            return {'CANCELLED'}
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=100)

    def draw(self, context):
        layout = self.layout
        layout.label(text="Select a preset to delete:")
        layout.prop(self, "preset_to_delete", text="")


@register
class I3D_IO_OT_SavePreset(bpy.types.Operator):
    bl_idname = "i3dio.save_preset"
    bl_label = "Save Preset"
    bl_description = "Save the current object state as a preset"

    name: bpy.props.StringProperty(name="Preset Name", default="NewPreset")

    def execute(self, context):
        obj = context.object
        grouped_values = PresetManager.collect_attributes(obj, obj.type)
        filepath = PresetManager.save_preset(self.name, grouped_values)
        self.report({'INFO'}, f"Preset saved: {filepath}")
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


def draw_presets(layout: bpy.types.UILayout, subdir: Path, menu_idname: str, add_delete: bool = False) -> None:
    presets = PresetManager.list_presets(subdir)
    col = layout.column(align=True)
    for file in presets:
        row = col.row(align=True)
        name = file.stem
        op = row.operator("script.execute_preset", text=name)
        op.filepath = str(file)
        op.menu_idname = menu_idname
    if add_delete:
        # NOTE: Tried adding it to the same row as the presets, but it either caused the presets to be misaligned
        # or scale the menu across the entire width of the monitor.
        layout.separator(factor=2)
        layout.operator("i3dio.delete_preset", text="Delete Preset", icon='TRASH')


@register
class I3D_IO_MT_PhysicsPresets(bpy.types.Menu):
    bl_label = "Physics Presets"

    def draw(self, _context):
        layout = self.layout
        draw_presets(layout, "Physics", self.__class__.__name__)


@register
class I3D_IO_MT_NonPhysicsPresets(bpy.types.Menu):
    bl_label = "Non-Physics Presets"

    def draw(self, context):
        layout = self.layout
        draw_presets(layout, "NonPhysics", self.__class__.__name__)


@register
class I3D_IO_MT_UserPresets(bpy.types.Menu):
    bl_label = "Your Presets"

    def draw(self, _context):
        layout = self.layout
        draw_presets(layout, None, self.__class__.__name__, add_delete=True)


@register
class I3D_IO_MT_MainPresets(bpy.types.Menu):
    bl_label = "Select Preset"

    def draw(self, _context):
        layout = self.layout
        layout.menu("I3D_IO_MT_PhysicsPresets", icon='PHYSICS')
        layout.menu("I3D_IO_MT_NonPhysicsPresets", icon='MODIFIER')
        layout.menu("I3D_IO_MT_UserPresets", icon='FILE_FOLDER')
        layout.separator(factor=2)
        layout.operator("i3dio.save_preset", icon='FILE_NEW')


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
