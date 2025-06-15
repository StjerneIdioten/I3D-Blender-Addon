from __future__ import annotations
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

from ..utility import get_fs_data_path
from .shader_parser import (get_shader_dict, ShaderParameter, ShaderTexture)
from .helper_functions import (detect_fs_version, is_version_compatible, humanize_template)
from .shader_migration_utils import (COLOR_MASK_VARIATIONS, migrate_variation,
                                     migrate_material_parameters, migrate_material_textures)
from .material_templates import TEMPLATES_GROUP_NAMES
from .. import __package__ as base_package


SHADER_DEFAULT = ''


def _clone_shader_texture(tex: I3DShaderTexture) -> dict:
    return {k: getattr(tex, k) for k in ('name', 'source', 'default_source')}


class ShaderManager:
    """Manages synchronization of material attributes and UI with parsed shader data."""
    def __init__(self, material: bpy.types.Material) -> None:
        self.attributes = material.i3d_attributes
        self.shader_dict = get_shader_dict(self.attributes.use_custom_shaders)
        self.dynamic_params = self.attributes.shader_material_params
        self.cached_textures = {t.name: _clone_shader_texture(t) for t in self.attributes.shader_material_textures}
        self.shader = self.shader_dict.get(self.attributes.shader_name, None)

    def clear_shader_data(self, clear_all: bool = False) -> None:
        self.attributes.shader_material_textures.clear()
        self.attributes.required_vertex_attributes.clear()
        if clear_all:
            self._cleanup_unused_params(set())  # When clearing all, remove all params
            self.attributes.shader_variation_name = SHADER_DEFAULT
            self.attributes.shader_variations.clear()

    def _add_shader_groups(self, group_names: list[str]) -> set[str]:
        """Adds parameters and textures from the specified groups. Returns used param names."""
        used_params = set()
        for group in group_names:
            for param in self.shader.parameters.get(group, []):
                self.add_shader_parameter(param)
                used_params.add(param.name)
            for texture in self.shader.textures.get(group, []):
                self.add_shader_texture(texture)
        for attr_name, attr_group in self.shader.vertex_attributes.items():
            if attr_group in group_names:
                self.attributes.required_vertex_attributes.add().name = attr_name
        return used_params

    def _cleanup_unused_params(self, used_params: set[str]) -> None:
        """Remove any params not in the current used set."""
        for param in list(self.dynamic_params.keys()):  # Use list to avoid runtime error
            if param not in used_params:
                del self.dynamic_params[param]

    def update_shader(self) -> None:
        self.clear_shader_data(clear_all=True)
        attr = self.attributes
        if not self.shader:
            attr.shader_name = SHADER_DEFAULT  # Set to default to prevent errors in panels
            return
        attr.shader_game_version = "" if attr.use_custom_shaders else detect_fs_version(str(self.shader.path)) or ""

        for variation in self.shader.variations:  # Add all variations to the collection
            attr.shader_variations.add().name = variation
        self._add_shader_groups(['base'])  # Always add the base group (default for all shaders)

    def update_variation(self, shader_variation_name: str) -> None:
        self.clear_shader_data()
        if not self.shader:
            self.attributes.shader_variation_name = SHADER_DEFAULT
            return
        groups = self.shader.variations.get(shader_variation_name) or ['base']
        used_params = self._add_shader_groups(groups)
        self._cleanup_unused_params(used_params)

    def add_shader_parameter(self, parameter: ShaderParameter) -> None:
        if parameter.name not in self.dynamic_params:  # Preserve existing param value when switching shader variations
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
    source: StringProperty(name='Texture source', description='Path to the texture', default='', subtype='FILE_PATH')
    default_source: StringProperty()
    template: StringProperty()


@register
class I3DShaderDynamicParams(bpy.types.PropertyGroup):
    """Dynamic container for shader parameter values (populated at runtime via id_properties)."""
    pass


@register
class I3DShaderVariation(bpy.types.PropertyGroup):
    name: StringProperty(default=SHADER_DEFAULT)


@register
class I3DMaterialShader(bpy.types.PropertyGroup):
    shader_game_version: StringProperty(options={'HIDDEN'})  # Used for migrating shaders between game versions

    def _custom_shaders_update(self, _context) -> None:
        self['shader_name'] = SHADER_DEFAULT
        ShaderManager(self.id_data).update_shader()

    use_custom_shaders: BoolProperty(
        name='Use Custom Shaders',
        description='Enable to use custom shaders instead of game shaders',
        default=False,
        update=_custom_shaders_update
    )

    def _shader_name_getter(self) -> str:
        return self.get('shader_name', SHADER_DEFAULT)

    def _shader_name_setter(self, shader_name: str) -> None:
        if shader_name != self.get('shader_name', SHADER_DEFAULT):
            self['shader_name'] = shader_name
            ShaderManager(self.id_data).update_shader()

    def _shader_name_search(self, _context, _search: str) -> list[str]:
        shader_dict = get_shader_dict(self.use_custom_shaders)
        return [name for name in shader_dict]

    shader_name: StringProperty(
        name='Shader',
        description='The shader to use for this material',
        get=_shader_name_getter,
        set=_shader_name_setter,
        search=_shader_name_search
    )

    def _variation_getter(self) -> str:
        return self.get('shader_variation_name', SHADER_DEFAULT)

    def _variation_setter(self, variation_name: str) -> None:
        if variation_name == self.get('shader_variation_name', SHADER_DEFAULT):
            return  # No change, return to avoid RecursionError
        if variation_name in [v.name for v in self.shader_variations] or variation_name == SHADER_DEFAULT:
            self['shader_variation_name'] = variation_name
            ShaderManager(self.id_data).update_variation(variation_name)
            return
        self['shader_variation_name'] = SHADER_DEFAULT
        ShaderManager(self.id_data).update_variation(SHADER_DEFAULT)

    def _shader_variation_name_search(self, _context, _search: str) -> list[str]:
        return [variation.name for variation in self.shader_variations]

    shader_variation_name: StringProperty(
        name="Variation",
        description="The selected variation for the current shader",
        get=_variation_getter,
        set=_variation_setter,
        search=_shader_variation_name_search
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
        data_path = get_fs_data_path()
        game_version = detect_fs_version(data_path) or ""

        if game_version == "25":
            layout.operator('i3dio.create_material_from_template_popup')  # TODO: Find a more suitable place for this

        main_props = layout.column(align=True)
        main_props.use_property_split = True
        main_props.prop(i3d_attributes, 'shading_rate')
        main_props.prop(i3d_attributes, 'alpha_blending')

        layout.separator(type='LINE')

        row = layout.row(align=True)
        col = row.column(align=False)

        if not data_path:
            box = col.box()
            box.label(text="No game data path set", icon='ERROR')
            box.prop(context.preferences.addons[base_package].preferences, 'fs_data_path')

        # Only "Valid" legacy key we care about is the "source" key, which is the old shader path
        if game_version and i3d_attributes.shader_game_version != game_version and \
                ('source' in i3d_attributes or i3d_attributes.shader_name != SHADER_DEFAULT):
            box = col.box()
            box.label(text="Old vehicleShader found:")
            if (old_shader_source := i3d_attributes.get('source')):
                box.label(text=old_shader_source)
            else:
                box.label(text=i3d_attributes.shader_name)
            box.label(text="If you want to convert this shader to new format, run the operator")
            box.operator('i3dio.udim_to_mat_template', text="Convert to Material Template...")

        shaderdefault = i3d_attributes.shader_name == SHADER_DEFAULT
        row = col.row(align=True)
        row.prop(i3d_attributes, 'shader_name', placeholder="No Shader", icon='FILE_BLANK' if shaderdefault else 'FILE')
        row = row.row(align=True)
        row.enabled = any(folder.path for folder in context.scene.i3dio.custom_shader_folders)
        row.prop(i3d_attributes, 'use_custom_shaders', text="", icon='EVENT_C')
        col = col.column(align=True)
        col.enabled = i3d_attributes.shader_name != SHADER_DEFAULT
        col.prop(i3d_attributes, 'shader_variation_name', placeholder="None", icon='EVENT_V')

        if i3d_attributes.required_vertex_attributes:
            column = layout.column(align=True)
            column.separator(factor=2.5, type='LINE')
            column.label(text="Required Vertex Attributes:")
            row = column.row(align=True)
            for attr in i3d_attributes.required_vertex_attributes:
                row.label(text=attr.name, icon='DOT')
            column.separator(factor=2.5, type='LINE')

        if not shaderdefault:
            draw_shader_group_panels(layout, i3d_attributes)


def draw_shader_group_panel(layout: bpy.types.UILayout, idname: str, header_label: str, i3d_attributes,
                            params: list[str], textures: list[I3DShaderTexture]) -> None:
    if params:
        param_header, param_panel = layout.panel(idname + "_params", default_closed=False)
        param_header.label(text=f"{header_label}Parameters")
        if idname == "shader_material_brandcolor":
            op = param_header.operator('i3dio.template_search_popup', text="", icon="EVENT_M", emboss=False)
            op.is_brand = False
            op.single_param = ""
            op = param_header.operator('i3dio.template_search_popup', text="", icon="EVENT_B", emboss=False)
            op.is_brand = True
            op.single_param = ""
        if not param_panel:
            return
        param_arrays = [i3d_attributes.shader_material_params[param] for param in params]
        max_param_length = max((len(arr) for arr in param_arrays), default=4)
        column = param_panel.column(align=False)
        for param in params:
            row = column.row(align=True)
            row.prop(i3d_attributes.shader_material_params, f'["{param}"]')
            if idname == "shader_material_brandcolor":
                op = row.operator('i3dio.template_search_popup', text="", icon="EVENT_B")
                op.is_brand = True
                op.single_param = param
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
        friendly_name = TEMPLATES_GROUP_NAMES.get(template, humanize_template(template))
        group_label = "" if single_template else friendly_name + " "
        idname = f"shader_material_{template.lower()}"
        draw_shader_group_panel(layout, idname, group_label, i3d_attributes, params, textures)


DEBUG = True


def _print(message: str) -> None:
    if DEBUG:
        print(message)


@persistent
def migrate_old_shader_format(file) -> None:
    # Old -> new property names:
    # source -> shader_name
    # variation -> shader_variation_name
    # shader_parameters -> shader_material_params
    # shader_textures -> shader_material_textures
    fs_data_path = get_fs_data_path()
    if not file or not fs_data_path:
        return
    _print(f"[ShaderUpgrade] Handling old shader format for: {file}")

    for mat in bpy.data.materials:
        i3d_attr = mat.i3d_attributes
        if not (old_source := i3d_attr.get('source')) or not old_source.endswith('.xml'):
            continue  # No old source, nothing to do

        old_shader_path = Path(bpy.path.abspath(old_source))
        old_shader_stem = old_shader_path.stem
        old_version = detect_fs_version(str(old_shader_path))
        current_version = detect_fs_version(fs_data_path)
        version_compatible = is_version_compatible(old_version, current_version)

        if not old_shader_stem:
            continue  # No shader, nothing to do

        old_variation_name = ""
        if (old_variation_index := i3d_attr.get('variation')) is not None and \
                (old_variations := i3d_attr.get('variations')) is not None:
            if 0 <= old_variation_index < len(old_variations):
                old_variation_name = old_variations[old_variation_index].get('name')
            del i3d_attr['variation']  # Remove old variation index
            del i3d_attr['variations']  # Remove old variations list

        if any(old_shader_path == s.path for s in get_shader_dict().values()):
            _print(f"[ShaderUpgrade] Found game shader: {old_shader_stem} through path match")
            i3d_attr.shader_name = old_shader_stem
        elif old_shader_stem in get_shader_dict():  # Check if the shader name matches any of the game shaders
            # Special handling for incompatible vehicleShaders
            if old_shader_stem == "vehicleShader" and not version_compatible:
                _print("[ShaderUpgrade] Skipping vehicleShader")
                # Store old variation name to be handled later
                i3d_attr['temp_old_variation_name'] = old_variation_name
                continue
            # For all other game shaders, proceed
            _print(f"[ShaderUpgrade] Found game shader: {old_shader_stem} by name. Old variation: {old_variation_name}")
            i3d_attr.shader_name = old_shader_stem
        elif old_shader_path.exists():  # We have to assume this is a custom shader
            _print(f"[ShaderUpgrade] Found custom shader: {old_shader_stem} through path match to directory")
            if old_shader_stem not in get_shader_dict(True):
                shader_folder_item = bpy.context.scene.i3dio.custom_shader_folders.add()
                shader_folder_item.name = old_shader_path.parent.stem
                shader_folder_item.path = str(old_shader_path.parent)
            i3d_attr.use_custom_shaders = True
            i3d_attr.shader_name = old_shader_stem
        else:  # No shader found
            _print(f"[ShaderUpgrade] No shader found for: {old_shader_stem}")
            continue  # No shader found, nothing to do
        del i3d_attr['source']  # New shader is set, remove old source

        is_incompatible_vehicle = (old_shader_stem == "vehicleShader" and not version_compatible)
        migrate_variation(i3d_attr, old_variation_name, is_incompatible_vehicle)
        migrate_material_parameters(i3d_attr)
        migrate_material_textures(i3d_attr)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Material.i3d_attributes = PointerProperty(type=I3DMaterialShader)
    load_post.append(migrate_old_shader_format)


def unregister():
    load_post.remove(migrate_old_shader_format)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Material.i3d_attributes
