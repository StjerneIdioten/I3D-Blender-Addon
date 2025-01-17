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

from bpy.app.handlers import (persistent, load_post)
from .. import __package__ as base_package
from collections import namedtuple

classes = []

# A module value to represent what the field shows when a shader is not selected
shader_no_variations = 'NO_VARIATIONS'
shader_parameter_max_decimals = 3  # 0-6 per blender properties documentation
custom_shader_default = ''
SHADERS = {}
SHADER_ENUM_ITEMS_DEFAULT = ('NO_SHADER', 'no shader', 'No Shader Selected')
SHADERS_ENUM_ITEMS = [SHADER_ENUM_ITEMS_DEFAULT]
VARIATIONS_ENUM_ITEMS_DEFAULT = ('NO_VARIATIONS', 'no variation', 'No Variation Selected')

ShaderMetadata = namedtuple('Shader', ['path', 'parameters', 'textures', 'variations'])


def register(cls):
    classes.append(cls)
    return cls


@register
class I3DShaderParameter(bpy.types.PropertyGroup):
    name: StringProperty(default='Unnamed Attribute')
    type: EnumProperty(items=[('float', '', ''), ('float2', '', ''), ('float3', '', ''), ('float4', '', '')])
    data_float_1: FloatProperty(precision=shader_parameter_max_decimals)
    data_float_2: FloatVectorProperty(size=2, precision=shader_parameter_max_decimals)
    data_float_3: FloatVectorProperty(size=3, precision=shader_parameter_max_decimals)
    data_float_4: FloatVectorProperty(size=4, precision=shader_parameter_max_decimals)


@register
class I3DShaderTexture(bpy.types.PropertyGroup):
    name: StringProperty(default='Unnamed Texture')
    source: StringProperty(name='Texture source',
                           description='Path to the texture',
                           subtype='FILE_PATH',
                           default=''
                           )
    default_source: StringProperty()


@register
class I3DShaderVariation(bpy.types.PropertyGroup):
    name: StringProperty(default='Unnamed Variation')


def update_shader(shader_name):
    global SHADERS, SHADERS_ENUM_ITEMS
    attributes = bpy.context.material.i3d_attributes
    attributes.shader_parameters.clear()
    attributes.shader_textures.clear()
    attributes.shader_name = shader_name
    attributes.shader_variations.clear()
    attributes.shader_variations.add().name = shader_no_variations
    attributes.variation_name = shader_no_variations
    for variation in SHADERS[shader_name].variations:
        attributes.shader_variations.add().name = variation


def update_variation(shader_name, variation_name):
    global SHADERS
    attributes = bpy.context.material.i3d_attributes
    attributes.shader_parameters.clear()
    attributes.shader_textures.clear()
    shader = SHADERS[shader_name]
    variation = shader.variations[variation_name]
    print(f"Updating variation {variation_name} for shader {shader_name}, with {len(variation)} groups")
    for group in variation:
        print(f"Group: {group}")
        for parameter in shader.parameters.get(group, []):
            new_parameter = attributes.shader_parameters.add()
            new_parameter.name = parameter['name']
            new_parameter.type = parameter['type']
            data = tuple(map(float, parameter['default_value']))
            match parameter['type']:
                case 'float':
                    new_parameter.data_float_1 = data
                case 'float2':
                    new_parameter.data_float_2 = data
                case 'float3':
                    new_parameter.data_float_3 = data
                case 'float4':
                    new_parameter.data_float_4 = data
            print(f"Parameter: {parameter['name']}, {parameter['type']}, {parameter['default_value']}")


@register
class I3DMaterialShader(bpy.types.PropertyGroup):
    def shader_items_update(self, _context):
        return SHADERS_ENUM_ITEMS

    def shader_setter(self, selected_index):
        existing_shader = self.get('shader')
        if existing_shader != selected_index:
            self['shader'] = selected_index
            if existing_shader is not None:
                update_shader(self.shader)

    def shader_getter(self):
        return self.get('shader', 0)

    shader: EnumProperty(
        name='Shader',
        description='The shader',
        default=0,
        items=shader_items_update,
        options=set(),
        update=None,
        get=shader_getter,
        set=shader_setter,
    )
    shader_name: StringProperty(name='NO_SHADER')

    # Variations
    shader_variations: CollectionProperty(type=I3DShaderVariation)

    def variation_setter(self, new_name):
        if self['variation_name'] != new_name:
            self['variation_name'] = new_name
            if new_name != shader_no_variations:
                update_variation(self['shader_name'], new_name)

    def variation_getter(self):
        return self.get('variation_name', shader_no_variations)

    variation_name: StringProperty(
        name="Selected Variation",
        get=variation_getter,
        set=variation_setter
    )

    shader_parameters: CollectionProperty(type=I3DShaderParameter)
    shader_textures: CollectionProperty(type=I3DShaderTexture)

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
        col.prop_search(i3d_attributes, 'variation_name', i3d_attributes, 'shader_variations', text="Variation")

        header, panel = layout.panel('shader_parameters', default_closed=False)
        header.label(text="Shader Parameters")
        if panel:
            column = panel.column(align=True)
            parameters = i3d_attributes.shader_parameters
            for parameter in parameters:
                match parameter.type:
                    case 'float':
                        property_type = 'data_float_1'
                    case 'float2':
                        property_type = 'data_float_2'
                    case 'float3':
                        property_type = 'data_float_3'
                    case _:
                        property_type = 'data_float_4'
                column.row(align=True).prop(parameter, property_type, text=parameter.name)

        """ column.separator()
        textures = i3d_attributes.shader_textures
        for texture in textures:
            column.row(align=True).prop(texture, 'source', text=texture.name) """


def parameter_element_as_dict(parameter):
    parameter_list = []

    match parameter.attrib['type']:
        case 'float' | 'float1':
            type_length = 1
        case 'float2':
            type_length = 2
        case 'float3':
            type_length = 3
        case 'float4':
            type_length = 4
        case _:
            print(f"Shader Parameter type is unknown! {parameter.attrib['type']}")

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
            parameter_list.append({'name': f"{parameter.attrib['name']}{child.attrib['index']}",
                                   'type': parameter.attrib['type'],
                                   'default_value': parse_default(child.text)})
    else:
        parameter_list.append({'name': parameter.attrib['name'],
                               'type': parameter.attrib['type'],
                               'default_value': parse_default(parameter.attrib.get('defaultValue'))})

    return parameter_list


def texture_element_as_dict(texture):
    texture_dictionary = {'name': texture.attrib['name'],
                          'default_file': texture.attrib.get('defaultFilename', '')
                          }
    return texture_dictionary


def load_shader(path: Path):
    tree = xml_i3d.parse(path)
    if tree is None:
        return None
    shader = ShaderMetadata(path, {}, {}, {})
    root = tree.getroot()
    parameters = root.find('Parameters')
    if parameters is not None:
        for p in parameters:
            if p.tag == 'Parameter':
                shader.parameters.setdefault(p.attrib.get('group'), []).extend(parameter_element_as_dict(p))
    textures = root.find('Textures')
    if textures is not None:
        for t in textures:
            if t.tag == 'Texture' and t.attrib.get('defaultColorProfile') is not None:
                shader.textures.setdefault(t.attrib.get('group'), []).extend(texture_element_as_dict(t))
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
    SHADERS_ENUM_ITEMS.extend([(shader[0], shader[0], str(shader[1].path)) for shader in SHADERS.items()])


@persistent
def handle_old_shader_format(file):
    global SHADERS

    if not file:
        return

    for mat in bpy.data.materials:
        if (source := mat.i3d_attributes.get('source')) is not None:
            attr = mat.i3d_attributes
            shader_path = Path(source)

            if shader_path in (s.path for s in SHADERS.values()):
                attr.shader = shader_path.stem
            # Handle shader that doesn't exist anymore
            print(f"{attr.get('variations')[attr.get('variation')].get('name')}")

        else:
            print("Has no source")
            if (variation := mat.i3d_attributes.get('variation_name')) is not None:
                print(f"V: {variation}")
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
