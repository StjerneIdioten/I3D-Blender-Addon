import bpy
from pathlib import Path
from .. import __package__ as base_package
from .. import xml_i3d
from .object import I3DNodeObjectAttributes
from .mesh import I3DNodeShapeAttributes


classes = []


def register(cls):
    classes.append(cls)
    return cls


VISIBILITY_CONDITION_FLAGS: dict[str, dict[str, str]] = {}  # category: {bit: name}


def hex_to_binary(hex_str: str) -> str:
    try:
        return bin(int(hex_str.strip(), 16))[2:].zfill(32)
    except ValueError:
        return "0" * 32


def binary_to_hex(binary_str: str) -> str:
    return hex(int(binary_str, 2))[2:].lstrip("0").lower() or "0"


def binary_to_bits(binary_str: str) -> list[bool]:
    return [bool(int(b)) for b in reversed(binary_str)]


def bits_to_binary(bits: list[bool]) -> str:
    return ''.join(str(int(bit)) for bit in reversed(bits))


def hex_to_bits(hex_str: str) -> list[bool]:
    return binary_to_bits(hex_to_binary(hex_str))


def hex_to_decimal(hex_str: str) -> str:
    return str(int(hex_str, 16))


def is_valid_hex(value: str) -> bool:
    try:
        int(value, 16)
        return True
    except ValueError:
        return False


def is_valid_binary(value: str) -> bool:
    return all(c in "01" for c in value) and len(value) <= 32


def is_data_attribute(obj: bpy.types.Object, target_prop: str) -> bool:
    return hasattr(obj.data, "i3d_attributes") and hasattr(obj.data.i3d_attributes, target_prop)


def get_i3d_attribute(obj: bpy.types.Object, target_prop: str) -> str:
    for attr_source in (obj.data, obj):
        i3d_attributes = getattr(attr_source, "i3d_attributes", None)
        if i3d_attributes and hasattr(i3d_attributes, target_prop):
            return getattr(i3d_attributes, target_prop)
    return "0"


def set_i3d_attribute(obj: bpy.types.Object, target_prop: str, value: str) -> None:
    attr_source = obj.data if hasattr(obj.data.i3d_attributes, target_prop) else obj
    if hasattr(attr_source, "i3d_attributes"):
        setattr(attr_source.i3d_attributes, target_prop, value)


def get_bit_names(target_prop: str) -> list[str]:  # No flag files for collision_mask etc in FS22
    category_map = {"weather_required_mask": "weatherFlags", "weather_prevent_mask": "weatherFlags",
                    "viewer_spaciality_required_mask": "viewerSpatialityFlags",
                    "viewer_spaciality_prevent_mask": "viewerSpatialityFlags"}
    category = category_map.get(target_prop)
    return [name for _bit, name in VISIBILITY_CONDITION_FLAGS.get(category, {}).items()] if category else []


def message_box(message: str, title: str = "Info", icon: str = 'INFO') -> None:
    def draw(self, context):
        self.layout.label(text=message)
    bpy.context.window_manager.popup_menu(draw, title=title, icon=icon)


@register
class I3D_IO_OT_handle_invalid_bit_mask(bpy.types.Operator):
    bl_idname = "i3dio.handle_invalid_bit_mask"
    bl_label = "Handle Invalid Bit Mask"
    bl_description = "Handles invalid bit mask input by resetting to default value and reopening the editor"
    bl_options = {'INTERNAL'}

    target: bpy.props.StringProperty(default="")
    used_bits: bpy.props.IntProperty(default=32)

    def execute(self, _context):
        if is_data_attribute(bpy.context.object, self.target):
            default_prop_val = I3DNodeShapeAttributes.i3d_map.get(self.target).get("default", "0")
        else:
            default_prop_val = I3DNodeObjectAttributes.i3d_map.get(self.target).get("default", "0")
        # Hacky way to open the bit mask editor again with the appropriate values
        bpy.ops.i3dio.bit_mask_editor('INVOKE_DEFAULT', target_prop=self.target, used_bits=self.used_bits,
                                      internal_value=str(default_prop_val))
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=300, confirm_text="Continue")

    def draw(self, context):
        layout = self.layout
        layout.label(text=f"Invalid Hex Value from {self.target}.", icon='ERROR')
        layout.label(text="Click 'Continue' to use default value and open the editor.")


@register
class I3D_IO_OT_bit_mask_editor(bpy.types.Operator):
    bl_idname = "i3dio.bit_mask_editor"
    bl_label = "Bit Mask Editor"
    bl_description = "Edit Bit Masks"
    bl_options = {'INTERNAL', 'UNDO'}

    internal_value: bpy.props.StringProperty(default="")
    target_prop: bpy.props.StringProperty(default="")
    used_bits: bpy.props.IntProperty(default=32)

    def update_placeholder(self, _context):
        hex_value = self.placeholder
        if not is_valid_hex(hex_value):
            message_box("Invalid Hex Input. Input was set to 0.", "Warning", 'ERROR')
            hex_value = "0"
            self.placeholder = hex_value
        if self.bit_mask_binary != hex_to_binary(hex_value):
            self.bit_mask_binary = hex_to_binary(hex_value)
        if self.bit_mask_hex != hex_value:
            self.bit_mask_hex = hex_value
        if self.bit_mask_decimal != hex_to_decimal(hex_value):
            self.bit_mask_decimal = hex_to_decimal(hex_value)
        if self.bits != hex_to_bits(hex_value):
            self.bits = hex_to_bits(hex_value)

    def update_bits(self, _context):
        try:
            binary_str = bits_to_binary(self.bits)
            if self.placeholder != binary_to_hex(binary_str):
                self.placeholder = binary_to_hex(binary_str)
        except ValueError:
            pass

    def update_binary(self, _context):
        try:
            binary_str = self.bit_mask_binary
            if self.placeholder != binary_to_hex(binary_str):
                self.placeholder = binary_to_hex(binary_str)
        except ValueError:
            pass

    def update_hex(self, _context):
        try:
            if self.placeholder != self.bit_mask_hex:
                self.placeholder = self.bit_mask_hex
        except ValueError:
            pass

    def update_decimal(self, _context):
        try:
            decimal_value = int(self.bit_mask_decimal)
            binary_str = bin(decimal_value)[2:].zfill(32)
            if self.placeholder != binary_to_hex(binary_str):
                self.placeholder = binary_to_hex(binary_str)
        except ValueError:
            pass

    def update_change_all(self, _context):
        if self.clear_all:
            if self.placeholder != "0":
                self.bits = [False] * 32
            self.clear_all = False
        elif self.set_all:
            if self.placeholder != "ffffffff":
                self.bits = [True] * self.used_bits + [False] * (32 - self.used_bits)
            self.set_all = False
        elif self.invert_all:
            self.bits = [not bit if i < self.used_bits else False for i, bit in enumerate(self.bits)]
            self.invert_all = False

    placeholder: bpy.props.StringProperty(default="", update=update_placeholder)
    bits: bpy.props.BoolVectorProperty(name="Bits", size=32, default=[0] * 32, update=update_bits)
    bit_mask_binary: bpy.props.StringProperty(default="", update=update_binary)
    bit_mask_hex: bpy.props.StringProperty(default="", update=update_hex)
    bit_mask_decimal: bpy.props.StringProperty(default="", update=update_decimal)
    clear_all: bpy.props.BoolProperty(default=False, update=update_change_all)
    set_all: bpy.props.BoolProperty(default=False, update=update_change_all)
    invert_all: bpy.props.BoolProperty(default=False, update=update_change_all)

    def invoke(self, context: bpy.types.Context, _event):
        if self.internal_value:
            hex_value = self.internal_value
            self.internal_value = ""
        else:
            hex_value = get_i3d_attribute(context.object, self.target_prop)

        if not is_valid_hex(hex_value):
            # Open a dialog to continue with default prop value & to let user know their input was invalid
            bpy.ops.i3dio.handle_invalid_bit_mask('INVOKE_DEFAULT', target=self.target_prop, used_bits=self.used_bits)
            return {"CANCELLED"}
        self.placeholder = hex_value
        title = f"Bit Mask Editor - {' '.join(word.capitalize() for word in self.target_prop.split('_'))}"

        width = {"weather_required_mask": 750, "weather_prevent_mask": 750, "viewer_spaciality_required_mask": 950,
                 "viewer_spaciality_prevent_mask": 950}.get(self.target_prop, 400)
        return context.window_manager.invoke_props_dialog(self, width=width, title=title)

    def draw(self, _context):
        layout = self.layout
        bit_names = get_bit_names(self.target_prop)

        grid = layout.grid_flow(row_major=True, columns=8, even_columns=True, even_rows=True, align=True)
        for i in range(31, -1, -1):  # 31 to 0 NOTE: seems to be layed out a bit different for most bit editors in GE10
            row = grid.row(align=True)
            row.enabled = i < self.used_bits or self.target_prop != "nav_mesh_mask"
            row.prop(self, "bits", index=i, text=f"{i} {bit_names[i] if i < len(bit_names) else ''}")

        layout.separator(factor=2, type='LINE')
        layout.prop(self, "bit_mask_binary", text="Binary")
        layout.prop(self, "bit_mask_hex", text="Hex")
        layout.prop(self, "bit_mask_decimal", text="Decimal")
        row = layout.row(align=False)
        row.alignment = 'LEFT'
        row.prop(self, "set_all", text="Set All", toggle=True, icon='CHECKBOX_HLT')
        row.prop(self, "clear_all", text="Clear All", toggle=True, icon='CHECKBOX_DEHLT')
        row.prop(self, "invert_all", text="Invert All", toggle=True, icon='ARROW_LEFTRIGHT')

    def execute(self, context):
        # Save the hex value to the input property
        set_i3d_attribute(context.object, self.target_prop, self.placeholder)
        return {"FINISHED"}


def parse_flags_from_xml(file_path: Path, categories: list[str]) -> dict:
    if not file_path.exists():
        return {}

    tree = xml_i3d.parse(file_path)
    if not tree:
        return {}

    root = tree.getroot()
    return {category.tag: {flag.get('bit'): flag.get('name') for flag in category.findall('flag')
                           if flag.get('bit') and flag.get('name')} for category in root if category.tag in categories}


def get_visibility_condition_flags():
    data_path = Path(bpy.context.preferences.addons[base_package].preferences.fs_data_path)
    shared_dir = data_path.parent / "shared"
    vis_con_flags_path = shared_dir / "visibilityConditionFlags.xml"

    global VISIBILITY_CONDITION_FLAGS
    VISIBILITY_CONDITION_FLAGS = parse_flags_from_xml(vis_con_flags_path, ["weatherFlags", "viewerSpatialityFlags"])
    return VISIBILITY_CONDITION_FLAGS


def register():
    get_visibility_condition_flags()
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
