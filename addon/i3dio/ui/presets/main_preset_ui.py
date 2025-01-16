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
    def save_preset(name, defines, values):
        filepath = PresetManager.get_preset_filepath(name)
        with filepath.open("w", encoding="utf-8") as file:
            file.write("import bpy\n\n")

            # Write the defines (e.g., obj and mesh setup)
            for define in defines:
                file.write(f"{define}\n")
            file.write("\n")

            # Write object attributes
            for key, value in values.items():
                if key.startswith("mesh."):  # Skip mesh attributes
                    continue
                file.write(f"{key} = {repr(value)}\n")

            # Write mesh attributes under 'if mesh:'
            mesh_attributes = {k: v for k, v in values.items() if k.startswith("mesh.")}
            if mesh_attributes:
                file.write("\nif mesh:\n")
                for key, value in mesh_attributes.items():
                    file.write(f"    {key} = {repr(value)}\n")
        return filepath

    @staticmethod
    def collect_attributes(source: bpy.types.Object, source_key: str, obj_type: str):
        """Collect attributes explicitly defined in a PropertyGroup based on object type."""
        # Combine universal attributes with type-specific attributes
        applicable_attributes = ATTRIBUTE_MAP.get("UNIVERSAL", [])
        applicable_attributes += ATTRIBUTE_MAP.get(obj_type, [])

        if obj_type == "MESH":
            applicable_attributes += ATTRIBUTE_MAP.get("MESH_DATA", [])

        values = {}
        for attr in applicable_attributes:
            try:
                value = getattr(source.i3d_attributes, attr)
                if isinstance(value, bpy.types.bpy_prop_array):
                    value = list(value)
                values[f"{source_key}.i3d_attributes.{attr}"] = value
            except AttributeError:
                pass  # Skip attributes that cannot be accessed
        return values


@register
class I3D_IO_OT_DeletePreset(bpy.types.Operator):
    bl_idname = "i3dio.delete_preset"
    bl_label = "Delete Preset"
    bl_description = "Delete a preset file"

    name: bpy.props.StringProperty(name="Preset Name")

    def execute(self, context):
        filepath = PresetManager.get_preset_filepath(self.name)
        if filepath.exists():
            filepath.unlink()
            self.report({'INFO'}, f"Preset deleted: {filepath}")
        else:
            self.report({'ERROR'}, f"Preset not found: {filepath}")
        return {'FINISHED'}

    def invoke(self, context, _event):
        return context.window_manager.invoke_props_dialog(self, confirm_text="Delete", width=200)

    def draw(self, _context):
        self.layout.label(text=f"Delete preset '{self.name}'?")


@register
class I3D_IO_OT_SavePreset(bpy.types.Operator):
    bl_idname = "i3dio.save_preset"
    bl_label = "Save Preset"
    bl_description = "Save the current object state as a preset"

    name: bpy.props.StringProperty(name="Preset Name", default="NewPreset")

    def execute(self, context):
        obj = context.object
        if not obj:
            self.report({'ERROR'}, "No object selected.")
            return {'CANCELLED'}

        preset_defines = [
            "obj = bpy.context.object",
            "mesh = obj.data if obj.type == 'MESH' else None",
        ]
        preset_values = {}

        # Collect object attributes
        preset_values.update(PresetManager.collect_attributes(obj, "obj", obj.type))

        # Collect mesh-specific attributes
        if obj.type == 'MESH' and hasattr(obj.data, "i3d_attributes"):
            preset_values.update(PresetManager.collect_attributes(obj.data, "mesh", "MESH_DATA"))

        # Save the preset
        filepath = PresetManager.save_preset(self.name, preset_defines, preset_values)
        self.report({'INFO'}, f"Preset saved: {filepath}")
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


def draw_presets(layout: bpy.types.UILayout, subdir: Path, menu_idname: str, add_delete: bool = False) -> None:
    presets = PresetManager.list_presets(subdir)
    for file in presets:
        name = file.stem
        row = layout.row(align=True)
        op = row.operator("script.execute_preset", text=name)
        op.filepath = str(file)
        op.menu_idname = menu_idname
        if add_delete:
            row.operator("i3dio.delete_preset", text="", icon='TRASH').name = name


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
