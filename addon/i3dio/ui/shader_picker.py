import bpy
from bpy.types import Panel
from bpy.props import (
    StringProperty,
    PointerProperty,
    EnumProperty,
    FloatVectorProperty,
    FloatProperty,
    CollectionProperty,
    BoolProperty
)

from .. import xml_i3d
from pathlib import Path
from enum import Enum

from bpy.app.handlers import (persistent, load_post)
from .. import __package__ as base_package
from collections import namedtuple

classes = []

# A module value to represent what the field shows when a shader is not selected
SHADER_NO_VARIATION = 'None'
SHADER_PARAMETER_MAX_DECIMALS = 3  # 0-6 per blender properties documentation
SHADER_DEFAULT = 'NO_SHADER'

SHADERS = {}
SHADER_ENUM_ITEMS_DEFAULT = (f'{SHADER_DEFAULT}', 'No Shader', 'No Shader Selected')
SHADERS_ENUM_ITEMS = [SHADER_ENUM_ITEMS_DEFAULT]

ShaderMetadata = namedtuple('Shader', ['path', 'parameters', 'textures', 'vertex_attributes', 'variations'])


class ShaderParameterType(Enum):
    FLOAT = 'float'
    FLOAT2 = 'float2'
    FLOAT3 = 'float3'
    FLOAT4 = 'float4'


class ShaderManager:
    def __init__(self, material):
        self.attributes = material.i3d_attributes

    def clear_shader_data(self, clear_all=False):
        self.attributes.shader_material_parameters.clear()
        self.attributes.shader_material_textures.clear()
        self.attributes.required_vertex_attributes.clear()
        if clear_all:
            self.attributes.shader_variations.clear()

    def update_shader(self, shader_name):
        self.clear_shader_data(clear_all=True)
        self.attributes.shader_name = shader_name
        self.attributes.shader_variations.add().name = SHADER_NO_VARIATION
        self.attributes.shader_variation_name = SHADER_NO_VARIATION
        if shader_name != SHADER_DEFAULT:
            # Add all variations
            for variation in SHADERS[shader_name].variations:
                self.attributes.shader_variations.add().name = variation

            # Add base parameters and textures
            for param in SHADERS[shader_name].parameters.get('base', []):
                self.add_shader_parameter(param)
            for texture in SHADERS[shader_name].textures.get('base', []):
                self.add_shader_texture(texture)

    def update_variation(self, shader_name, shader_variation_name):
        self.clear_shader_data()
        if shader_name == SHADER_DEFAULT:
            return

        shader = SHADERS[shader_name]

        # Add base parameters and textures when no variation is selected
        if shader_variation_name == SHADER_NO_VARIATION or shader_variation_name == '':
            for param in shader.parameters.get('base', []):
                self.add_shader_parameter(param)
            for texture in shader.textures.get('base', []):
                self.add_shader_texture(texture)
            self.set_vertex_attributes(shader, groups=['base'])
            return

        # Add variation-specific parameters and textures
        variation = shader.variations.get(shader_variation_name, [])
        for group in variation:
            for param in shader.parameters.get(group, []):
                self.add_shader_parameter(param)
            for texture in shader.textures.get(group, []):
                self.add_shader_texture(texture)
        self.set_vertex_attributes(shader, groups=variation)

    def add_shader_parameter(self, parameter):
        new_param = self.attributes.shader_material_parameters.add()
        new_param.name = parameter['name']
        new_param.type = parameter['type']
        data = tuple(map(float, parameter['default_value']))
        match parameter['type']:
            case ShaderParameterType.FLOAT.value:
                new_param.data_float_1 = data[0]
            case ShaderParameterType.FLOAT2.value:
                new_param.data_float_2 = data
            case ShaderParameterType.FLOAT3.value:
                new_param.data_float_3 = data
            case ShaderParameterType.FLOAT4.value:
                new_param.data_float_4 = data

    def add_shader_texture(self, texture):
        new_texture = self.attributes.shader_material_textures.add()
        new_texture.name = texture['name']
        new_texture.default_source = texture.get('default_file', '')

    def set_vertex_attributes(self, shader, groups):
        required_attributes = {name for name, group in shader.vertex_attributes.items() if group in groups}
        self.attributes.required_vertex_attributes.clear()
        for name in required_attributes:
            attr = self.attributes.required_vertex_attributes.add()
            attr.name = name


def register(cls):
    classes.append(cls)
    return cls


@register
class I3DRequiredVertexAttribute(bpy.types.PropertyGroup):
    name: StringProperty()


@register
class I3DShaderParameter(bpy.types.PropertyGroup):
    name: StringProperty(default='Unnamed Attribute')
    type: EnumProperty(items=[('float', '', ''), ('float2', '', ''), ('float3', '', ''), ('float4', '', '')])
    data_float_1: FloatProperty(precision=SHADER_PARAMETER_MAX_DECIMALS)
    data_float_2: FloatVectorProperty(size=2, precision=SHADER_PARAMETER_MAX_DECIMALS)
    data_float_3: FloatVectorProperty(size=3, precision=SHADER_PARAMETER_MAX_DECIMALS)
    data_float_4: FloatVectorProperty(size=4, precision=SHADER_PARAMETER_MAX_DECIMALS)


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


@register
class I3DShaderVariation(bpy.types.PropertyGroup):
    name: StringProperty(default=SHADER_NO_VARIATION)


def update_shader(material, shader_name):
    if material is None:
        raise ValueError("Material must be provided")
    manager = ShaderManager(material)
    manager.update_shader(shader_name)


def update_variation(material, shader_name, shader_variation_name):
    if material is None:
        raise ValueError("Material must be provided")
    manager = ShaderManager(material)
    manager.update_variation(shader_name, shader_variation_name)


@register
class I3DMaterialShader(bpy.types.PropertyGroup):
    def shader_items_update(self, _context):
        return SHADERS_ENUM_ITEMS

    def shader_setter(self, selected_index):
        existing_shader = self.get('shader', 0)
        if existing_shader != selected_index:
            self['shader'] = selected_index
            shader_name = SHADERS_ENUM_ITEMS[selected_index][0]
            update_shader(self.id_data, shader_name)

    def shader_getter(self):
        return self.get('shader', 0)

    shader: EnumProperty(
        name='Shader',
        description='The shader to use for this material',
        default=0,
        items=shader_items_update,
        options=set(),
        update=None,
        get=shader_getter,
        set=shader_setter,
    )

    # Just for easy access to the shader name
    shader_name: StringProperty(name='NO_SHADER')

    # Variations
    def variation_setter(self, variation):
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
            update_variation(self.id_data, shader_name, variation)

    def variation_getter(self):
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

    shader_material_parameters: CollectionProperty(type=I3DShaderParameter)
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
        col.prop(i3d_attributes, 'shader', text="Shader")
        col.prop_search(i3d_attributes, 'shader_variation_name', i3d_attributes, 'shader_variations', text="Variation")

        if i3d_attributes.required_vertex_attributes:
            column = layout.column(align=True)
            column.separator(factor=2.5, type='LINE')
            column.label(text="Required Vertex Attributes:")
            for attr in i3d_attributes.required_vertex_attributes:
                column.label(text=attr.name, icon='DOT')
            column.separator(factor=2.5, type='LINE')

        if i3d_attributes.shader_material_parameters:
            draw_shader_material_parameters(layout, i3d_attributes)
        if i3d_attributes.shader_material_textures:
            draw_shader_material_textures(layout, i3d_attributes)


def draw_shader_material_parameters(layout: bpy.types.UILayout, i3d_attributes) -> None:
    header, panel = layout.panel('shader_material_parameters', default_closed=False)
    header.label(text="Shader Parameters")
    if panel:
        column = panel.column(align=False)
        parameters = i3d_attributes.shader_material_parameters
        for parameter in parameters:
            row = column.row(align=True)
            row.label(text=parameter.name)
            match parameter.type:
                case 'float':
                    row.prop(parameter, 'data_float_1', text="")
                    for _ in range(3):
                        row.label(text="")
                case 'float2':
                    row.prop(parameter, 'data_float_2', text="")
                    for _ in range(2):
                        row.label(text="")
                case 'float3':
                    row.prop(parameter, 'data_float_3', text="")
                    row.label(text="")
                case _:
                    row.prop(parameter, 'data_float_4', text="")


def draw_shader_material_textures(layout: bpy.types.UILayout, i3d_attributes) -> None:
    header, panel = layout.panel('shader_material_textures', default_closed=False)
    header.label(text="Shader Textures")
    if panel:
        column = panel.column(align=True)
        textures = i3d_attributes.shader_material_textures
        for texture in textures:
            placeholder = texture.default_source if texture.default_source else 'Texture not assigned'
            column.row(align=True).prop(texture, 'source', text=texture.name, placeholder=placeholder)


def parameter_element_as_dict(parameter):
    parameter_list = []

    try:
        if (param_type := parameter.attrib['type']) in ['float', 'float1']:
            param_type = ShaderParameterType.FLOAT
        else:
            param_type = ShaderParameterType(param_type)
        type_length = int(param_type.name[-1]) if param_type.name[-1].isdigit() else 1
    except ValueError:
        print(f"Shader Parameter type is unknown! {parameter.attrib.get('type', 'UNKNOWN')}")
        return parameter_list

    def parse_default(default):
        default_parsed = []
        if default is not None:
            default_parsed = default.split()
            # For some reason, Giants shaders has to specify their default values in terms of float4... Where the extra
            # parts compared with what the actual type length is, aren't in any way relevant.
            if len(default_parsed) > type_length:
                default_parsed = default_parsed[:type_length - 1]
        default_parsed += ['0'] * (type_length - len(default_parsed))
        return default_parsed

    if 'arraySize' in parameter.attrib:
        for child in parameter:
            parameter_list.append({
                'name': f"{parameter.attrib['name']}{child.attrib['index']}",
                'type': param_type.value,
                'default_value': parse_default(child.text)
            })
    else:
        parameter_list.append({
            'name': parameter.attrib['name'],
            'type': param_type.value,
            'default_value': parse_default(parameter.attrib.get('defaultValue'))
        })

    return parameter_list


def texture_element_as_dict(texture):
    texture_dictionary = {'name': texture.attrib['name'], 'default_file': texture.attrib.get('defaultFilename', '')}
    return texture_dictionary


def load_shader(path: Path):
    tree = xml_i3d.parse(path)
    if tree is None:
        return None
    shader = ShaderMetadata(path, {}, {}, {}, {})
    root = tree.getroot()
    parameters = root.find('Parameters')
    if parameters is not None:
        for p in parameters:
            if p.tag == 'Parameter':
                group = p.attrib.get('group', 'base')  # Default to "base" if no group is specified
                shader.parameters.setdefault(group, []).extend(parameter_element_as_dict(p))
    textures = root.find('Textures')
    if textures is not None:
        for t in textures:
            if t.tag == 'Texture' and t.attrib.get('defaultColorProfile') is not None:
                group = t.attrib.get('group', 'base')  # Default to "base" if no group is specified
                shader.textures.setdefault(group, []).append(texture_element_as_dict(t))
    vertex_attributes = root.find('VertexAttributes')
    if vertex_attributes is not None:
        for attr in vertex_attributes:
            if attr.tag == 'VertexAttribute':
                shader.vertex_attributes[attr.attrib['name']] = attr.attrib.get('group', 'base')
    variations = root.find('Variations')
    if variations is not None:
        for v in variations:
            if v.tag == 'Variation':
                # Some variations don't have a group defined, but should still use the 'base' group regardless
                shader.variations[v.attrib.get('name')] = v.attrib.get('groups', 'base').split()
    return shader


def locate_shaders_in_directory(dir: Path):
    return (shader_path for shader_path in dir.glob('*.xml'))


def populate_shader_cache():
    global SHADERS, SHADERS_ENUM_ITEMS
    shader_dir = Path(bpy.context.preferences.addons[base_package].preferences.fs_data_path) / 'shaders'
    if shader_dir.exists():
        SHADERS = {path.stem: load_shader(path) for path in locate_shaders_in_directory(shader_dir)}
    SHADERS_ENUM_ITEMS = [SHADER_ENUM_ITEMS_DEFAULT]
    SHADERS_ENUM_ITEMS.extend(
        [(name, name, str(shader.path)) for name, shader in SHADERS.items() if shader is not None]
    )


@persistent
def handle_old_shader_format(file):
    print("Handling old shader format", file)
    # Old -> new property names:
    # shader -> shader
    # variation -> shader_variation_name
    # shader_parameters -> shader_material_parameters
    # shader_textures -> shader_material_textures
    if not file:
        return

    for mat in bpy.data.materials:
        print("\n")
        print(f"Material: {mat.name}, {mat.i3d_attributes.get('source')}")
        if (old_source := mat.i3d_attributes.get('source')) is not None:
            old_parameters = mat.i3d_attributes.get('shader_parameters')
            old_variation = mat.i3d_attributes.get('variation')  # Old variation index (enum)
            old_variations = mat.i3d_attributes.get('variations')  # All variations from old selected shader
            old_textures = mat.i3d_attributes.get('shader_textures')
            attr = mat.i3d_attributes
            old_shader_path = Path(old_source)

            print(f"Shader is: {old_shader_path}")

            if old_shader_path in (s.path for s in SHADERS.values()):
                print(f"Setting shader, {old_shader_path.stem}")
                attr.shader = old_shader_path.stem
            elif old_shader_path.stem in SHADERS:
                # If path doesn't match, try to match by name,
                # could be a path from earlier game version or changed game path
                print(f"Setting shader from elif, {old_shader_path.stem}")
                attr.shader = old_shader_path.stem
            else:
                print(f"Shader not found: {old_shader_path.stem}")
                attr.shader = SHADER_DEFAULT
                continue  # Shader is not found, no reason to run through variations etc when no shader is set

            if old_variations is not None and old_variation is not None:
                if 0 <= old_variation < len(old_variations):
                    # Old variation was enum, we need to use the index to get the name through its stored variations
                    old_variation_name = old_variations[old_variation].get('name', SHADER_NO_VARIATION)
                    print(f"Setting variation to, {old_variation_name}")
                    attr.shader_variation_name = old_variation_name
                else:
                    print(f"Invalid old variation index: {old_variation}, falling back to default.")
                    attr.shader_variation_name = SHADER_NO_VARIATION
            else:
                print(f"No variations found for {mat.name}, falling back to default.")
                attr.shader_variation_name = SHADER_NO_VARIATION

            if old_parameters is not None:
                for old_param in old_parameters:
                    old_name = old_param.get('name' '')

                    existing_param = next((p for p in attr.shader_material_parameters if p.name == old_name), None)

                    if existing_param is not None:
                        existing_param.name = old_name

                        # Old type is stored as index because it was a enum. Ensure it's within bounds
                        old_type_index = min(old_param.get('type', 0), 3)
                        old_type = list(ShaderParameterType)[old_type_index].value
                        existing_param.type = old_type

                        if 'data_float_1' in old_param:
                            existing_param.data_float_1 = old_param['data_float_1']
                        elif 'data_float_2' in old_param:
                            existing_param.data_float_2 = old_param['data_float_2']
                        elif 'data_float_3' in old_param:
                            existing_param.data_float_3 = old_param['data_float_3']
                        elif 'data_float_4' in old_param:
                            existing_param.data_float_4 = old_param['data_float_4']
                        else:
                            print(f"Unhandled data type for parameter: {old_name}")

            if old_textures is not None:
                for old_texture in old_textures:
                    old_name = old_texture.get('name', '')
                    existing_texture = next((t for t in attr.shader_material_textures if t.name == old_name), None)
                    if existing_texture is not None:
                        existing_texture.name = old_name
                        print(f"Setting texture source for {old_name}")
                        old_texture_source = old_texture.get('source', '')
                        print(f"Old source: {old_texture_source}")
                        # If the texture source is different from the default_source, set it to the source
                        if old_texture_source != existing_texture.default_source:
                            existing_texture.source = old_texture_source

        else:
            print("Has no source")
    return


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Material.i3d_attributes = PointerProperty(type=I3DMaterialShader)
    load_post.append(handle_old_shader_format)
    populate_shader_cache()


def unregister():
    load_post.remove(handle_old_shader_format)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Material.i3d_attributes
