from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path

import bpy
from bpy.types import Panel
from bpy.props import (
    StringProperty,
    PointerProperty,
    EnumProperty,
    CollectionProperty,
    BoolProperty
)
from bpy.app.handlers import (persistent, load_post)

from .helper_functions import get_fs_data_path, detect_fs_version, is_version_compatible, humanize_template
from .. import xml_i3d


# A module value to represent what the field shows when a shader is not selected
SHADER_NO_VARIATION = 'None'
SHADER_PARAMETER_MAX_DECIMALS = 3  # 0-6 per blender properties documentation
SHADER_DEFAULT = 'NO_SHADER'

SHADERS_GAME: ShaderDict = {}
SHADERS_CUSTOM: ShaderDict = {}
SHADER_ENUM_ITEMS_DEFAULT = (f'{SHADER_DEFAULT}', 'No Shader', 'No Shader Selected')
SHADER_ENUMS_GAME = [SHADER_ENUM_ITEMS_DEFAULT]
SHADER_ENUMS_CUSTOM = [SHADER_ENUM_ITEMS_DEFAULT]


@dataclass
class ShaderParameter:
    name: str
    type: int
    default_value: list[float]
    min_value: float = -xml_i3d.i3d_max
    max_value: float = xml_i3d.i3d_max
    description: str = ''
    template: str = 'default'


@dataclass
class ShaderTexture:
    name: str
    default_file: str
    template: str = 'default'


@dataclass
class ShaderMetadata:
    path: Path
    variations: dict[str, list[str]] = field(default_factory=dict)
    parameters: dict[str, list[ShaderParameter]] = field(default_factory=dict)
    textures: dict[str, list[ShaderTexture]] = field(default_factory=dict)
    vertex_attributes: dict[str, str] = field(default_factory=dict)
    param_lookup: dict[str, ShaderParameter] = field(default_factory=dict)


ShaderDict = dict[str, ShaderMetadata]


def get_shader_dict(use_custom: bool) -> ShaderDict:
    return SHADERS_CUSTOM if use_custom else SHADERS_GAME


def _clone_shader_texture(tex: I3DShaderTexture) -> dict:
    return {'name': tex.name, 'source': tex.source, 'default_source': tex.default_source}


class ShaderManager:
    def __init__(self, material: bpy.types.Material) -> None:
        self.attributes = material.i3d_attributes
        self.shader_dict = get_shader_dict(self.attributes.use_custom_shaders)
        self.dynamic_params = self.attributes.shader_material_params
        self.cached_textures = {t.name: _clone_shader_texture(t) for t in self.attributes.shader_material_textures}

    def clear_shader_data(self, clear_all: bool = False) -> None:
        self.attributes.shader_material_textures.clear()
        self.attributes.required_vertex_attributes.clear()
        if clear_all:
            self._cleanup_unused_params(set())  # When clearing all, remove all params
            self.attributes.shader_variations.clear()

    def _add_shader_groups(self, shader: ShaderMetadata, group_names: list[str]) -> set[str]:
        """Adds parameters and textures from the specified groups. Returns used param names."""
        used_params = set()
        for group in group_names:
            for param in shader.parameters.get(group, []):
                self.add_shader_parameter(param)
                used_params.add(param.name)
            for texture in shader.textures.get(group, []):
                self.add_shader_texture(texture)
        return used_params

    def _cleanup_unused_params(self, used_params: set[str]) -> None:
        """Remove any params not in the current used set."""
        for param in list(self.dynamic_params.keys()):  # Use list to avoid runtime error
            if param not in used_params:
                del self.dynamic_params[param]

    def update_shader(self, shader_name: str) -> None:
        self.clear_shader_data(clear_all=True)
        self.attributes.shader_name = shader_name
        self.attributes.shader_variations.add().name = SHADER_NO_VARIATION
        self.attributes.shader_variation_name = SHADER_NO_VARIATION

        if shader_name == SHADER_DEFAULT or not (shader := self.shader_dict.get(shader_name)):
            return

        for variation in shader.variations:  # Add all variations to the collection
            self.attributes.shader_variations.add().name = variation
        self._add_shader_groups(shader, ['base'])  # Always add the base group (default for all shaders)
        # No need to cleanup for new shader, dynamic_params will always be empty before

    def update_variation(self, shader_name: str, shader_variation_name: str) -> None:
        if shader_name == SHADER_DEFAULT or not (shader := self.shader_dict.get(shader_name)):
            return
        self.clear_shader_data()
        groups = shader.variations.get(shader_variation_name) or ['base']
        used_params = self._add_shader_groups(shader, groups)
        self._cleanup_unused_params(used_params)
        self.set_vertex_attributes(shader, groups)

    def add_shader_parameter(self, parameter: ShaderParameter) -> None:
        if parameter.name in self.dynamic_params:
            return  # Preserve the parameter value when switching shader variations
        self.dynamic_params[parameter.name] = parameter.default_value
        ui = self.dynamic_params.id_properties_ui(parameter.name)
        ui.clear()
        ui.update(default=parameter.default_value, min=parameter.min_value,
                  max=parameter.max_value, description=parameter.description)

    def add_shader_texture(self, texture: ShaderTexture) -> None:
        new_texture = self.attributes.shader_material_textures.add()
        new_texture.name = texture.name
        new_texture.default_source = texture.default_file
        new_texture.template = texture.template
        if (cached := self.cached_textures.get(new_texture.name)) and cached['source'] != new_texture.default_source:
            new_texture.source = cached['source']

    def set_vertex_attributes(self, shader: ShaderMetadata, groups: list[str]) -> None:
        required_attributes = {name for name, group in shader.vertex_attributes.items() if group in groups}
        self.attributes.required_vertex_attributes.clear()
        for name in required_attributes:
            self.attributes.required_vertex_attributes.add().name = name


classes = []


def register(cls):
    classes.append(cls)
    return cls


@register
class I3DRequiredVertexAttribute(bpy.types.PropertyGroup):
    name: StringProperty()


@register
class I3DShaderTexture(bpy.types.PropertyGroup):
    name: StringProperty(default='Unnamed Texture')
    source: StringProperty(
        name='Texture source',
        description='Path to the texture',
        subtype='FILE_PATH',
        default=''
    )
    default_source: StringProperty()
    template: StringProperty()


@register
class I3DShaderDynamicParams(bpy.types.PropertyGroup):
    # Shader parameter system inspired by Blender OSL node/camera dynamic property design.
    # See: Cycles OSL implementation for similar dynamic, per-shader, per-property metadata-driven UI.
    pass


@register
class I3DShaderVariation(bpy.types.PropertyGroup):
    name: StringProperty(default=SHADER_NO_VARIATION)


@register
class I3DMaterialShader(bpy.types.PropertyGroup):
    def shader_items_update(self, _context) -> list[tuple[str, str, str]]:
        return SHADER_ENUMS_CUSTOM if self.use_custom_shaders else SHADER_ENUMS_GAME

    def shader_setter(self, selected_index: int) -> None:
        existing_shader = self.get('shader', 0)
        if existing_shader != selected_index:
            self['shader'] = selected_index
            shader_enums = SHADER_ENUMS_CUSTOM if self.use_custom_shaders else SHADER_ENUMS_GAME
            shader_name = shader_enums[selected_index][0]
            ShaderManager(self.id_data).update_shader(shader_name)

    def shader_getter(self):
        return self.get('shader', 0)

    def noop_update(self, _context) -> None:
        return

    shader: EnumProperty(
        name='Shader',
        description='The shader to use for this material',
        default=0,
        items=shader_items_update,
        update=noop_update,  # Required to ensure depsgraph sync after file load (if material is migrated)
        get=shader_getter,
        set=shader_setter,
    )

    # Just for easy access to the shader name
    shader_name: StringProperty(name=SHADER_DEFAULT)

    def custom_shaders_update(self, _context) -> None:
        self['shader'] = 0
        self.shader_name = SHADER_DEFAULT
        ShaderManager(self.id_data).update_shader(SHADER_DEFAULT)

    use_custom_shaders: BoolProperty(
        name='Use Custom Shaders',
        description='Use a custom shaders instead of the game shaders',
        default=False,
        update=custom_shaders_update
    )

    # Variations
    def variation_setter(self, variation: str) -> None:
        shader_name = self.get('shader_name', SHADER_DEFAULT)
        if shader_name == SHADER_DEFAULT:  # If no shader is selected, reset variation safely
            if self.get('shader_variation_name', '') != SHADER_NO_VARIATION:
                self['shader_variation_name'] = SHADER_NO_VARIATION
            return
        if not variation:  # Convert empty variation to default
            variation = SHADER_NO_VARIATION
        # Prevent recursion when setting the same variation
        if self.get('shader_variation_name', SHADER_NO_VARIATION) != variation:
            self['shader_variation_name'] = variation
            ShaderManager(self.id_data).update_variation(shader_name, variation)

    def variation_getter(self) -> str:
        if not len(self.shader_variations):
            return ""  # No variations available, return empty string to avoid red field in prop search
        return self.get('shader_variation_name', SHADER_NO_VARIATION)

    shader_variation_name: StringProperty(
        name="Selected Variation",
        description="The selected variation for the current shader",
        default=SHADER_NO_VARIATION,
        get=variation_getter,
        set=variation_setter
    )
    shader_variations: CollectionProperty(type=I3DShaderVariation)

    shader_material_params: PointerProperty(type=I3DShaderDynamicParams)
    shader_material_textures: CollectionProperty(type=I3DShaderTexture)
    required_vertex_attributes: CollectionProperty(type=I3DRequiredVertexAttribute)

    alpha_blending: BoolProperty(
        name='Alpha Blending',
        description='Enable alpha blending for this material',
        default=False
    )

    shading_rate: EnumProperty(
        name='Shading Rate',
        description='Shading Rate',
        items=[
            ('1x1', '1x1', '1x1'),
            ('1x2', '1x2', '1x2'),
            ('2x1', '2x1', '2x1'),
            ('2x2', '2x2', '2x2'),
            ('2x4', '2x4', '2x4'),
            ('4x2', '4x2', '4x2'),
            ('4x4', '4x4', '4x4')
        ],
        default='1x1'
    )


@register
class I3D_IO_PT_material_shader(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_label = "I3D Material & Shader Settings"
    bl_context = 'material'

    @classmethod
    def poll(cls, context):
        return context.material

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = False
        layout.use_property_decorate = False
        material = context.material
        i3d_attributes = material.i3d_attributes

        main_props = layout.column(align=True)
        main_props.use_property_split = True
        main_props.prop(i3d_attributes, 'shading_rate')
        main_props.prop(i3d_attributes, 'alpha_blending')

        layout.separator(type='LINE')

        row = layout.row(align=True)
        col = row.column(align=False)

        # Only "Valid" legacy key we care about is the "source" key, which is the old shader path
        if (old_shader_source := i3d_attributes.get('source')) and old_shader_source.endswith('.xml'):
            box = col.box()
            box.label(text="Old shader source found:")
            box.label(text=old_shader_source)
            box.label(text="If you want to convert this shader to new format, run the operator")

        custom_shaders_col = col.column(align=True)
        custom_shaders_col.enabled = len(context.scene.i3dio.shader_folders) > 0
        custom_shaders_col.prop(i3d_attributes, 'use_custom_shaders')
        col.prop(i3d_attributes, 'shader', text="Shader")
        col.prop_search(i3d_attributes, 'shader_variation_name', i3d_attributes, 'shader_variations', text="Variation")

        if i3d_attributes.required_vertex_attributes:
            column = layout.column(align=True)
            column.separator(factor=2.5, type='LINE')
            column.label(text="Required Vertex Attributes:")
            row = column.row(align=True)
            for attr in i3d_attributes.required_vertex_attributes:
                row.label(text=attr.name, icon='DOT')
            column.separator(factor=2.5, type='LINE')

        if i3d_attributes.shader_name not in (SHADER_DEFAULT, ""):
            draw_shader_group_panels(layout, i3d_attributes)


def draw_shader_group_panel(layout: bpy.types.UILayout, idname: str, header_label: str, i3d_attributes,
                            params: list[str], textures: list[I3DShaderTexture]) -> None:
    if params:
        param_header, param_panel = layout.panel(idname + "_params", default_closed=False)
        param_header.label(text=f"{header_label}Parameters")
        if not param_panel:
            return
        param_arrays = [i3d_attributes.shader_material_params[param] for param in params]
        max_param_length = max((len(arr) for arr in param_arrays), default=4)
        column = param_panel.column(align=False)
        for param in params:
            row = column.row(align=True)
            row.prop(i3d_attributes.shader_material_params, f'["{param}"]')
            for _ in range(max_param_length - len(i3d_attributes.shader_material_params[param])):
                row.label(text="")  # pad with empty text to make everything align
    if textures:
        texture_header, texture_panel = layout.panel(idname + "_textures", default_closed=False)
        texture_header.label(text=f"{header_label}Textures")
        if not texture_panel:
            return
        column = texture_panel.column(align=False)
        for texture in textures:
            placeholder = texture.default_source if texture.default_source else 'Texture not assigned'
            column.row(align=True).prop(texture, 'source', text=texture.name, placeholder=placeholder)


def draw_shader_group_panels(layout: bpy.types.UILayout, i3d_attributes) -> None:
    shader_dict = get_shader_dict(i3d_attributes.use_custom_shaders)
    shader_data = shader_dict.get(i3d_attributes.shader_name)
    lookup = shader_data.param_lookup

    params_by_template = {}
    for pname in i3d_attributes.shader_material_params.keys():
        if (param := lookup.get(pname)) is not None:
            params_by_template.setdefault(param.template, []).append(pname)
    textures_by_template = {}
    for texture in i3d_attributes.shader_material_textures:
        textures_by_template.setdefault(texture.template, []).append(texture)

    all_templates = set(params_by_template) | set(textures_by_template)
    all_templates = list(all_templates)
    priority_template = "brandColor"
    all_templates = [priority_template] + [t for t in all_templates if t != priority_template]

    single_template = len(all_templates) == 1
    for template in all_templates:
        params = params_by_template.get(template, [])
        textures = textures_by_template.get(template, [])
        group_label = "" if single_template else humanize_template(template) + " "
        idname = f"shader_material_{template.lower()}"
        draw_shader_group_panel(layout, idname, group_label, i3d_attributes, params, textures)


def parse_shader_parameters(parameter: xml_i3d.XML_Element) -> list[ShaderParameter]:
    """Parses a shader parameter element and returns a list of dictionaries with parameter data."""
    parameter_list: list[ShaderParameter] = []

    type_str = parameter.attrib.get('type', 'float4')
    type_length = {'float': 1, 'float1': 1, 'float2': 2, 'float3': 3, 'float4': 4}.get(type_str, 4)

    def _parse_floats(val: str | None, default: float = 0.0) -> list[float]:
        if val is None:
            return [default] * type_length
        try:
            vals = [float(x) for x in val.split()]
            # If too many, truncate; if too few, pad with default
            return vals[:type_length] + [default] * (type_length - len(vals))
        except Exception:
            return [default] * type_length

    param_name = parameter.attrib['name']
    template = parameter.attrib.get('template', 'default')
    default_value = _parse_floats(parameter.attrib.get('defaultValue'))
    min_str = parameter.attrib.get('minValue')
    max_str = parameter.attrib.get('maxValue')
    min_value = _parse_floats(min_str) if min_str else [min(-xml_i3d.i3d_max, min(default_value))] * type_length
    max_value = _parse_floats(max_str) if max_str else [max(xml_i3d.i3d_max, max(default_value))] * type_length
    # Blender supports only a single min/max per prop, so if all are the same, use that; else fallback to i3d_max
    min_single = min_value[0] if all(x == min_value[0] for x in min_value) else -xml_i3d.i3d_max
    max_single = max_value[0] if all(x == max_value[0] for x in max_value) else xml_i3d.i3d_max

    description = parameter.attrib.get('description', '')
    if parameter.attrib.get('arraySize') is not None:
        for child in parameter:
            child_default = _parse_floats(child.text)
            parameter_list.append(ShaderParameter(
                name=f"{param_name}{child.attrib.get('index', '')}",
                type=type_length,
                default_value=child_default,
                min_value=min_single,
                max_value=max_single,
                description=description,
                template=template
            ))
    else:
        parameter_list.append(ShaderParameter(
            name=param_name,
            type=type_length,
            default_value=default_value,
            min_value=min_single,
            max_value=max_single,
            description=description,
            template=template
        ))

    return parameter_list


def parse_shader_texture(texture: xml_i3d.XML_Element) -> ShaderTexture:
    """Parses a shader texture element and returns a dictionary with texture data."""
    return ShaderTexture(name=texture.attrib['name'], default_file=texture.attrib.get('defaultFilename', ''),
                         template=texture.attrib.get('template', 'default'))


def load_shader(path: Path) -> ShaderMetadata | None:
    tree = xml_i3d.parse(path)
    if tree is None:
        return None
    root = tree.getroot()
    if root.tag != 'CustomShader':
        return None
    shader = ShaderMetadata(path)

    if (variations := root.find('Variations')) is not None:
        for v in variations:
            if v.tag == 'Variation':
                # Some variations don't have a group defined, but should still use the 'base' group regardless
                shader.variations[v.attrib.get('name')] = v.attrib.get('groups', 'base').split()

    if (parameters := root.find('Parameters')) is not None:
        for p in parameters:
            if p.tag == 'Parameter':  # Default to "base" if no group is specified
                shader.parameters.setdefault(p.attrib.get('group', 'base'), []).extend(parse_shader_parameters(p))

    if (textures := root.find('Textures')) is not None:
        for t in textures:
            if t.tag == 'Texture':  # Default to "base" if no group is specified
                shader.textures.setdefault(t.attrib.get('group', 'base'), []).append(parse_shader_texture(t))

    if (vertex_attributes := root.find('VertexAttributes')) is not None:
        for attr in vertex_attributes:
            if attr.tag == 'VertexAttribute':
                shader.vertex_attributes[attr.attrib['name']] = attr.attrib.get('group', 'base')

    # Add a lookup for parameters to easily access them by name
    shader.param_lookup = {param.name: param for group in shader.parameters.values() for param in group}
    return shader


def load_shaders_from_directory(directory: Path) -> dict:
    """Scans a directory for .xml shader files and returns a dict of shader_name -> ShaderMetadata"""
    return {path.stem: shader for path in directory.glob('*.xml') if (shader := load_shader(path))}


def populate_game_shaders() -> None:
    global SHADERS_GAME, SHADER_ENUMS_GAME
    SHADERS_GAME.clear()

    shader_dir = get_fs_data_path(as_path=True) / 'shaders'
    if shader_dir.exists():
        SHADERS_GAME.update(load_shaders_from_directory(shader_dir))

    SHADER_ENUMS_GAME = [SHADER_ENUM_ITEMS_DEFAULT]
    SHADER_ENUMS_GAME.extend([(name, name, str(shader.path)) for name, shader in SHADERS_GAME.items()])
    print(f"Loaded {len(SHADERS_GAME)} game shaders")


def populate_custom_shaders() -> None:
    global SHADERS_CUSTOM, SHADER_ENUMS_CUSTOM
    SHADERS_CUSTOM.clear()

    try:
        for scene in bpy.data.scenes:
            for entry in scene.i3dio.shader_folders:
                path = Path(bpy.path.abspath(entry.path))
                if path.exists():
                    SHADERS_CUSTOM.update(load_shaders_from_directory(path))
                else:
                    print(f"[Custom Shader] Folder does not exist: {entry.path}")
    except Exception as e:
        print("Error reading custom shader folders:", e)

    SHADER_ENUMS_CUSTOM = [SHADER_ENUM_ITEMS_DEFAULT]
    SHADER_ENUMS_CUSTOM.extend([(name, name, str(shader.path)) for name, shader in SHADERS_CUSTOM.items()])
    print(f"Loaded {len(SHADERS_CUSTOM)} custom shaders")


@persistent
def populate_shader_cache_handler(_dummy) -> None:
    populate_game_shaders()
    populate_custom_shaders()


def _debug_print(message: str) -> None:
    if True:
        print(message)


def _migrate_shader_source(i3d_attr, old_shader_path: Path) -> bool:
    old_shader_stem = old_shader_path.stem
    old_version = detect_fs_version(old_shader_path)
    current_version = detect_fs_version(get_fs_data_path(as_path=True))

    # Check if the shader path matches any of the game shaders
    if any(old_shader_path == s.path for s in SHADERS_GAME.values()):
        _debug_print(f"[ShaderUpgrade] Found game shader: {old_shader_stem} through path match")
        i3d_attr.shader = old_shader_stem
    elif old_shader_stem in SHADERS_GAME:  # Check if the shader name matches any of the game shaders
        if not is_version_compatible(old_version, current_version) and old_shader_stem == "vehicleShader":
            # Conversion for vehicleShader from 19/22 to 25 is a more involved process and need to be handled separately
            _debug_print(f"[ShaderUpgrade] Found game shader: {old_shader_stem} through name match, but not compatible")
            return False
        _debug_print(f"[ShaderUpgrade] Found game shader: {old_shader_stem} through name match")
        i3d_attr.shader = old_shader_stem
    elif old_shader_path.exists():  # We have to assume this is a custom shader
        _debug_print(f"[ShaderUpgrade] Found custom shader: {old_shader_stem} through path match to directory")
        if old_shader_stem not in SHADERS_CUSTOM:
            shader_folder_item = bpy.context.scene.i3dio.shader_folders.add()
            shader_folder_item.name = old_shader_path.parent.stem
            shader_folder_item.path = str(old_shader_path.parent)  # Add folder where the shader is located
        i3d_attr.use_custom_shaders = True
        i3d_attr.shader = old_shader_stem
    else:  # No shader found
        _debug_print(f"[ShaderUpgrade] No shader found for: {old_shader_stem}")
        return False
    return True


@persistent
def migrate_old_shader_format(file) -> None:
    _debug_print(f"[ShaderUpgrade] Handling old shader format for: {file}")
    # Old -> new property names:
    # source -> shader
    # variation -> shader_variation_name
    # shader_parameters -> shader_material_params
    # shader_textures -> shader_material_textures
    if not file or not get_fs_data_path():
        return

    for mat in bpy.data.materials:
        i3d_attr = mat.i3d_attributes
        if not (old_source := i3d_attr.get('source')) or not old_source.endswith('.xml'):
            continue  # No old source, nothing to do

        _debug_print(f"\nMaterial: {mat.name}, has old source: {old_source}")
        old_shader_path = Path(bpy.path.abspath(old_source))
        if not _migrate_shader_source(i3d_attr, old_shader_path):
            continue  # Shader not found, skip this material
        del i3d_attr['source']  # Remove old source if new shader was found

        if (old_variation := i3d_attr.get('variation')) is not None and \
                (old_variations := i3d_attr.get('variations')) is not None:
            if 0 <= old_variation < len(old_variations):
                # Old variation was enum, we need to use the index to get the name through its stored variations
                old_variation_name = old_variations[old_variation].get('name', SHADER_NO_VARIATION)
                if old_variation_name not in i3d_attr.shader_variations:
                    _debug_print(f"Variation {old_variation_name} not found in shader variations, skipping.")
                    continue  # Skip if the variation is not in the new list
                _debug_print(f"Setting variation to, {old_variation_name}")
                i3d_attr.shader_variation_name = old_variation_name
            else:
                _debug_print(f"Invalid old variation index: {old_variation}, skipping.")
            del i3d_attr['variations']  # Remove variation(s) here for both cases,
            del i3d_attr['variation']   # because if index is invalid there is no use for it anyways

        if (old_parameters := i3d_attr.get('shader_parameters')) is not None:
            for old_param in old_parameters:
                old_name = old_param.get('name', '')
                if old_name not in i3d_attr.shader_material_params:
                    _debug_print(f"Parameter {old_name} not found in shader, skipping.")
                    continue  # Skip parameters that are not in the shader dict
                key_map = {'data_float_1': 1, 'data_float_2': 2, 'data_float_3': 3, 'data_float_4': 4}
                values = None
                for key, length in key_map.items():
                    if key in old_param:
                        data = old_param[key]
                        if isinstance(data, (float, int)):
                            values = [float(data)]
                        else:
                            values = [float(v) for v in data]
                        values = (values + [0.0] * length)[:length]
                        break
                if values is None:
                    _debug_print(f"Unhandled data type for parameter: {old_name}")
                    continue
                try:
                    i3d_attr.shader_material_params[old_name] = values
                except Exception as e:
                    _debug_print(f"Failed to migrate parameter '{old_name}': {e}")
            # Always remove old parameters after migration to prevent leftover legacy data.
            del i3d_attr['shader_parameters']

        if (old_textures := i3d_attr.get('shader_textures')) is not None:
            for old_texture in old_textures:
                old_name = old_texture.get('name', '')
                existing_texture = next((t for t in i3d_attr.shader_material_textures if t.name == old_name), None)
                if existing_texture is not None:
                    existing_texture.name = old_name
                    _debug_print(f"Setting texture source for {old_name}")
                    old_texture_source = old_texture.get('source', '')
                    _debug_print(f"Old source: {old_texture_source}")
                    # Only override if the texture source differs from the default
                    if old_texture_source != existing_texture.default_source:
                        existing_texture.source = old_texture_source
            # Always remove old textures after migration to prevent leftover legacy data.
            del i3d_attr['shader_textures']


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Material.i3d_attributes = PointerProperty(type=I3DMaterialShader)
    load_post.append(populate_shader_cache_handler)
    load_post.append(migrate_old_shader_format)


def unregister():
    load_post.remove(migrate_old_shader_format)
    load_post.remove(populate_shader_cache_handler)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Material.i3d_attributes
