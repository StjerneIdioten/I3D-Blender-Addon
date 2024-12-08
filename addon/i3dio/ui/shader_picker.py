import bpy
from bpy.types import (Panel)
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

classes = []

# A module value to represent what the field shows when a shader is not selected
shader_unselected_default_text = ''
shader_no_variation = 'None'
shader_parameter_max_decimals = 3  # 0-6 per blender properties documentation

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


@register
class I3DShaderVariation(bpy.types.PropertyGroup):
    name: StringProperty(default='Error')


def clear_shader(context):
    attributes = context.object.active_material.i3d_attributes
    attributes.source = shader_unselected_default_text
    attributes.variations.clear()
    attributes.shader_parameters.clear()
    attributes.shader_textures.clear()
    attributes.variation = shader_no_variation


@register
class I3DLoadCustomShader(bpy.types.Operator):
    """Can load in and generate a custom class for a shader, so settings can be set for export"""
    bl_idname = 'i3dio.load_custom_shader'
    bl_label = 'Load custom shader'
    bl_description = ''
    bl_options = {'INTERNAL'}

    def execute(self, context):

        attributes = context.object.active_material.i3d_attributes

        tree = xml_i3d.parse(bpy.path.abspath(attributes.source))
        if tree is None:
            print("Shader file is not correct xml")
            clear_shader(context)
        else:
            root = tree.getroot()
            if root.tag != 'CustomShader':
                print("File is xml, but not a properly formatted shader file! Aborting")
                clear_shader(context)
            else:
                attributes.variations.clear()
                base_variation = attributes.variations.add()
                base_variation.name = shader_no_variation
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
    """This function can load the parameters for a given shader variation, assumes that the source is valid,
       such that this operation will never fail"""
    bl_idname = 'i3dio.load_custom_shader_variation'
    bl_label = 'Load custom shader variation'
    bl_description = ''
    bl_options = {'INTERNAL'}

    def execute(self, context):

        shader = context.object.active_material.i3d_attributes

        tree = xml_i3d.parse(bpy.path.abspath(shader.source))
        if tree is None:
            print("Shader file is no longer valid")
            clear_shader(context)
        else:
            shader.shader_parameters.clear()
            shader.shader_textures.clear()
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

            if shader.variation != shader_no_variation:
                variations = root.find('Variations')
                variation = variations.find(f"./Variation[@name='{shader.variation}']")
                parameter_groups = ['mandatory'] + variation.attrib.get('groups', '').split()
            else:
                parameter_groups = ['mandatory', 'base']

            for group in parameter_groups:
                parameter_group = grouped_parameters.get(group)
                if parameter_group is not None:
                    for parameter in grouped_parameters[group]:
                        param = shader.shader_parameters.add()
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
                        tex = shader.shader_textures.add()
                        tex.name = texture['name']
                        tex.source = texture['default_file']
                        tex.default_source = texture['default_file']

        return {'FINISHED'}


@register
class I3DMaterialShader(bpy.types.PropertyGroup):

    def source_setter(self, value):
        try:
            self['source']
        except KeyError:
            self['source'] = value
            if self['source'] != shader_unselected_default_text:
                bpy.ops.i3dio.load_custom_shader()
        else:
            if self['source'] != value:
                self['source'] = value
                if self['source'] != shader_unselected_default_text:
                    bpy.ops.i3dio.load_custom_shader()

    def source_getter(self):
        return self.get('source', shader_unselected_default_text)

    def variation_items_update(self, context):
        items = []
        if self.variations:
            for variation in self.variations:
                items.append((f'{variation.name}', f'{variation.name}', f"The shader variation '{variation.name}'"))

        return items

    source: StringProperty(name='Shader Source',
                           description='Path to the shader',
                           subtype='FILE_PATH',
                           default=shader_unselected_default_text,
                           set=source_setter,
                           get=source_getter
                           )

    def variation_setter(self, value):
        self['variation'] = value
        bpy.ops.i3dio.load_custom_shader_variation()

    def variation_getter(self):
        return self.get('variation', shader_no_variation)

    variation: EnumProperty(name='Variation',
                            description='The shader variation',
                            default=None,
                            items=variation_items_update,
                            options=set(),
                            update=None,
                            get=variation_getter,
                            set=variation_setter
                            )

    variations: CollectionProperty(type=I3DShaderVariation)
    shader_parameters: CollectionProperty(type=I3DShaderParameter)
    shader_textures: CollectionProperty(type=I3DShaderTexture)

    alpha_blending: BoolProperty(
        name='Alpha Blending',
        description='Enable alpha blending for this material',
        default=False
    )


@register
class I3D_IO_PT_material_shader(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_label = "I3D Material & Shader Settings"
    bl_context = 'material'

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.active_material is not None

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = False
        layout.use_property_decorate = False
        material = context.active_object.active_material

        layout.prop(material.i3d_attributes, 'alpha_blending')
        layout.prop(material.i3d_attributes, 'source')

        if material.i3d_attributes.variations:
            layout.prop(material.i3d_attributes, 'variation')

        draw_shader_parameters(layout, material)
        draw_shader_textures(layout, material)


def draw_shader_parameters(layout: bpy.types.UILayout, material: bpy.types.Material) -> None:
    if material.i3d_attributes.shader_parameters:
        header, panel = layout.panel("shader_paramters", default_closed=False)
        header.label(text="Shader Parameters")
        if panel:
            column = panel.column(align=True)
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


def draw_shader_textures(layout: bpy.types.UILayout, material: bpy.types.Material) -> None:
    if material.i3d_attributes.shader_textures:
        header, panel = layout.panel("shader_textures", default_closed=False)
        header.label(text="Textures")
        if panel:
            panel.use_property_split = False
            panel.use_property_decorate = False

            column = panel.column(align=True)
            textures = material.i3d_attributes.shader_textures
            for texture in textures:
                column.row(align=True).prop(texture, 'source', text=texture.name)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Material.i3d_attributes = PointerProperty(type=I3DMaterialShader)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Material.i3d_attributes
