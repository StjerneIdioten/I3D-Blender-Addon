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

valid_types = {
    'float': 'float',
    'float1': 'float',
    'float2': 'float2',
    'float3': 'float3',
    'float4': 'float4'
}


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


def clear_shader(context):
    attributes = context.object.active_material.i3d_attributes
    attributes.variations.clear()
    attributes.shader_parameters.clear()
    attributes.shader_textures.clear()


@register
class I3DLoadCustomShader(bpy.types.Operator):
    """Can load in and generate a custom class for a shader, so settings can be set for export"""
    bl_idname = 'i3dio.load_custom_shader'
    bl_label = 'Load custom shader'
    bl_description = ''
    bl_options = {'INTERNAL'}

    material_name: bpy.props.StringProperty(
        name="Material Name",
        description="Name of the material to update",
        default=""
    )

    def execute(self, context):
        # If a material name is provided, use that material.
        if self.material_name:
            if self.material_name not in bpy.data.materials:
                self.report({'ERROR'}, f"Material '{self.material_name}' not found.")
                return {'CANCELLED'}
            attributes = bpy.data.materials[self.material_name].i3d_attributes

        # If no material name is provided, use the active material of the active object.
        else:
            if not context.object or not context.object.active_material:
                self.report({'ERROR'}, "No active object with an active material found.")
                return {'CANCELLED'}
            attributes = context.object.active_material.i3d_attributes

        data_path = bpy.context.preferences.addons['i3dio'].preferences.fs_data_path

        if attributes.custom_shader != custom_shader_default:
            path = str(Path(attributes.custom_shader))
        else:
            path = str(Path(data_path) / "shaders" / f"{attributes.shader}.xml")

        file = attributes.shader
        tree = xml_i3d.parse(bpy.path.abspath(path))
        if tree is None:
            print(f"{file} is not correct xml")
            clear_shader(context)
        else:
            root = tree.getroot()
            if root.tag != 'CustomShader':
                print(f"{file} is xml, but not a properly formatted shader file! Aborting")
                clear_shader(context)
            else:
                attributes.variations.clear()
                base_variation = attributes.variations.add()
                base_variation.name = shader_no_variations
                attributes.variation = base_variation.name

                variations = root.find('Variations')

                if variations is not None:
                    for variation in variations:
                        new_variation = attributes.variations.add()
                        new_variation.name = variation.attrib['name']

        return {'FINISHED'}


def parameter_element_as_dict(parameter):
    parameter_list = []

    if parameter.attrib['type'] in ['float', 'float1']:
        type_length = 1
    elif parameter.attrib['type'] == 'float2':
        type_length = 2
    elif parameter.attrib['type'] == 'float3':
        type_length = 3
    elif parameter.attrib['type'] == 'float4':
        type_length = 4
    else:
        print("Shader Parameter type is unknown!")

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


@register
class I3DLoadCustomShaderVariation(bpy.types.Operator):
    bl_idname = 'i3dio.load_custom_shader_variation'
    bl_label = 'Load shader variation'
    bl_description = ''
    bl_options = {'INTERNAL'}

    material_name: bpy.props.StringProperty(
        name="Material Name",
        description="Name of the material to update",
        default=""
    )

    def execute(self, context):
        # If a material name is provided, use that material.
        if self.material_name:
            if self.material_name not in bpy.data.materials:
                self.report({'ERROR'}, f"Material '{self.material_name}' not found.")
                return {'CANCELLED'}
            attributes = bpy.data.materials[self.material_name].i3d_attributes

        # If no material name is provided, use the active material of the active object.
        else:
            if not context.object or not context.object.active_material:
                return {'FINISHED'}
            attributes = context.object.active_material.i3d_attributes

        data_path = bpy.context.preferences.addons['i3dio'].preferences.fs_data_path

        if attributes.custom_shader != custom_shader_default:
            path = str(Path(attributes.custom_shader))
        else:
            path = str(Path(data_path) / "shaders" / f"{attributes.shader}.xml")

        tree = xml_i3d.parse(bpy.path.abspath(path))
        if tree is None:
            print(f"{path} doesn't exist!")
            clear_shader(context)

        else:
            attributes.shader_parameters.clear()
            attributes.shader_textures.clear()
            root = tree.getroot()

            # TODO: This should not be run every time the variation is changed, but instead stored somewhere
            parameters = root.find('Parameters')
            grouped_parameters = {}
            if parameters is not None:
                for parameter in parameters:
                    group_name = parameter.attrib.get('group', 'mandatory')
                    group = grouped_parameters.setdefault(group_name, [])
                    group.extend(parameter_element_as_dict(parameter))

            textures = root.find('Textures')
            grouped_textures = {}
            if textures is not None:
                for texture in textures:
                    if texture.attrib.get('defaultColorProfile') is not None:
                        group_name = texture.attrib.get('group', 'mandatory')
                        group = grouped_textures.setdefault(group_name, [])
                        group.append(texture_element_as_dict(texture))

            if attributes.variation != shader_no_variations:
                variations = root.find('Variations')
                variation = variations.find(f"./Variation[@name='{attributes.variation}']")
                parameter_groups = ['mandatory'] + variation.attrib.get('groups', '').split()
            else:
                parameter_groups = ['mandatory', 'base']

            for group in parameter_groups:
                parameter_group = grouped_parameters.get(group)
                if parameter_group is not None:
                    for parameter in grouped_parameters[group]:
                        param = attributes.shader_parameters.add()
                        param.name = parameter['name']
                        param.type = valid_types.get(parameter['type'], None)
                        data = tuple(map(float, parameter['default_value']))
                        if param.type == 'float':
                            param.data_float_1 = data[0]
                        elif param.type == 'float2':
                            param.data_float_2 = data
                        elif param.type == 'float3':
                            param.data_float_3 = data
                        elif param.type == 'float4':
                            param.data_float_4 = data

                texture_group = grouped_textures.get(group)
                if texture_group is not None:
                    for texture in grouped_textures[group]:
                        tex = attributes.shader_textures.add()
                        tex.name = texture['name']
                        tex.source = texture['default_file']
                        tex.default_source = texture['default_file']

        return {'FINISHED'}


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


def populate_shader_cache():
    global SHADERS, SHADERS_ENUM_ITEMS
    shader_dir = Path(bpy.context.preferences.addons['i3dio'].preferences.fs_data_path) / 'shaders'
    if shader_dir.exists():
        SHADERS = {path.stem: load_shader(path) for path in locate_shaders_in_directory(shader_dir)}
    SHADERS_ENUM_ITEMS = [SHADER_ENUM_ITEMS_DEFAULT]
    SHADERS_ENUM_ITEMS.extend([(shader[0], shader[0], str(shader[1].path)) for shader in SHADERS.items()])


def locate_shaders_in_directory(dir: Path):
    return (shader_path for shader_path in dir.glob('*.xml'))


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


def update_shader(idx):
    global SHADERS
    attributes = bpy.context.object.active_material.i3d_attributes
    # Clear existing
    attributes.variations.clear()
    attributes.shader_parameters.clear()
    attributes.shader_textures.clear()
    # Load variations
    attributes.variation = shader_no_variations
    for v in SHADERS.values()[idx].variations:
        pass


@register
class I3DMaterialShader(bpy.types.PropertyGroup):
    def shader_items_update(self, context):
        global SHADER_ENUM_ITEMS
        return SHADERS_ENUM_ITEMS

    def shader_setter(self, selected_index):
        existing_shader = self.get('shader')
        if existing_shader != selected_index:
            self['shader'] = selected_index
            if existing_shader is not None:
                update_shader(selected_index)

    def shader_getter(self):
        return self.get('shader', 0)

    shader: EnumProperty(name='Shader',
                         description='The shader',
                         default=0,
                         items=shader_items_update,
                         options=set(),
                         update=None,
                         get=shader_getter,
                         set=shader_setter,
                         )
    shader_name: StringProperty(name='NO_SHADER')

    def variation_items_update(self, context):
        items = [VARIATIONS_ENUM_ITEMS_DEFAULT]
        # if self.shader is not None or self.shader != 'NO_SHADER':
        #    for variation in SHADERS.variations:
        #        items.append((f'{variation.name}', f'{variation.name}', f"The shader variation '{variation.name}'"))
        return items

    def variation_setter(self, value):
        if self.get('variation') == value:
            return
        self['variation'] = value

    def variation_getter(self):
        return self.get('variation', 0)

    variations_enum = []
    variation: EnumProperty(name='Variation',
                            description='The shader variation',
                            default=0,
                            items=variation_items_update,
                            options=set(),
                            update=None,
                            get=variation_getter,
                            set=variation_setter
                            )
    variation_name: StringProperty(name='NO_VARIATION')

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
        layout.use_property_split = True
        layout.use_property_decorate = False
        material = context.material

        layout.prop(material.i3d_attributes, 'shading_rate')
        layout.prop(material.i3d_attributes, 'alpha_blending')

        row = layout.row(align=True)
        row.use_property_split = False
        row.prop(material.i3d_attributes, 'shader', text="")
        row.prop(material.i3d_attributes, 'variation', text="")

        column = layout.column(align=True)
        column.use_property_split = False
        parameters = material.i3d_attributes.shader_parameters
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
        column.separator()
        textures = material.i3d_attributes.shader_textures
        for texture in textures:
            column.row(align=True).prop(texture, 'source', text=texture.name)


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
