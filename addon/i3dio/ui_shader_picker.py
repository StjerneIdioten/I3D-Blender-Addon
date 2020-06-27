import xml.etree.ElementTree as ET
import bpy
from bpy.types import (Panel)
from bpy.props import (
    StringProperty,
    PointerProperty,
    EnumProperty,
    BoolProperty,
    FloatVectorProperty,
    FloatProperty,
    CollectionProperty
)

classes = []

# A module value to represent what the field shows when a shader is not selected
shader_unselected_default_text = ''
shader_no_variations = 'NONE'


def register(cls):
    classes.append(cls)
    return cls


@register
class I3DShaderParameter(bpy.types.PropertyGroup):
    name: StringProperty(default='Unnamed Attribute')
    type: EnumProperty(items=[('float', '', ''), ('float2', '', ''), ('float3', '', ''), ('float4', '', '')])
    data_float_1: FloatProperty()
    data_float_2: FloatVectorProperty(size=2)
    data_float_3: FloatVectorProperty(size=3)
    data_float_4: FloatVectorProperty(size=4)


@register
class I3DShaderTexture(bpy.types.PropertyGroup):
    name: StringProperty(default='Unnamed Attribute')
    enabled: BoolProperty(default=False)
    source: StringProperty(name='Texture source',
                           description='Path to the texture',
                           subtype='FILE_PATH',
                           default=''
                           )


@register
class I3DShaderVariation(bpy.types.PropertyGroup):
    name: StringProperty(default='Error')


@register
class I3DLoadCustomShader(bpy.types.Operator):
    """Can load in and generate a custom class for a shader, so settings can be set for export"""
    bl_idname = 'i3dio.load_custom_shader'
    bl_label = 'Load custom shader'
    bl_description = ''
    bl_options = {'INTERNAL'}

    def execute(self, context):

        attributes = context.object.active_material.i3d_attributes

        try:
            tree = ET.parse(bpy.path.abspath(attributes.source))
        except ET.ParseError as e:
            print(f"Shader file is not correct xml, failed with error: {e}")
            attributes.source = shader_unselected_default_text
            attributes.variations.clear()
            attributes.shader_parameters.clear()
            attributes.shader_textures.clear()
            attributes.variation = shader_no_variations
        else:
            root = tree.getroot()
            if root.tag != 'CustomShader':
                print(f"File is xml, but not a properly formatted shader file! Aborting")
                attributes.source = shader_unselected_default_text
                attributes.variations.clear()
                attributes.shader_parameters.clear()
                attributes.shader_textures.clear()
                attributes.variation = shader_no_variations
            else:
                attributes.variations.clear()
                variations = root.find('Variations')

                if variations is not None:
                    for variation in variations:
                        new_variation = attributes.variations.add()
                        new_variation.name = variation.attrib['name']

                    attributes.variation = variations[0].attrib['name']
                else:
                    attributes.variation = shader_no_variations

        return {'FINISHED'}


def parameter_element_as_dict(parameter):
    parameter_dictionary = {'name': parameter.attrib['name'],
                            'default_values': parameter.attrib['defaultValue'].split(),
                            'type': parameter.attrib['type']
                            }
    return parameter_dictionary


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

        try:
            tree = ET.parse(bpy.path.abspath(shader.source))
        except (ET.ParseError, FileNotFoundError) as e:
            print(f"Shader file is no longer valid: {e}")
            shader.source = shader_unselected_default_text
            shader.variations.clear()
            shader.shader_parameters.clear()
            shader.shader_textures.clear()
            shader.variation = shader_no_variations
        else:
            shader.shader_parameters.clear()
            shader.shader_textures.clear()
            root = tree.getroot()

            # TODO: This should not be run every time the variation is changed, but instead stored somewhere
            parameters = root.find('Parameters')
            grouped_parameters = {}
            for parameter in parameters:
                group_name = parameter.attrib['group']
                group = grouped_parameters.setdefault(group_name, [])
                group.append(parameter_element_as_dict(parameter))

            variations = root.find('Variations')
            variation = variations.find(f"./Variation[@name='{shader.variation}']")
            if variation is not None:
                parameter_groups = variation.attrib['groups'].split()
                for group in parameter_groups:
                    parameter_group = grouped_parameters.get(group)
                    if parameter_group is not None:
                        for parameter in grouped_parameters[group]:
                            param = shader.shader_parameters.add()
                            param.name = parameter['name']
                            param.type = parameter['type']
                            data = tuple(map(float, parameter['default_values']))
                            if param.type == 'float':
                                param.data_float_1 = data
                            elif param.type == 'float2':
                                param.data_float_2 = data
                            elif param.type == 'float3':
                                param.data_float_3 = data
                            else:
                                param.data_float_4 = data

        return {'FINISHED'}


@register
class I3DMaterialShader(bpy.types.PropertyGroup):

    def source_setter(self, value):
        #if self['source'] != value:
        self['source'] = value
        if self['source'] != shader_unselected_default_text:
            bpy.ops.i3dio.load_custom_shader()
        print(f"Set shader source to '{value}'")
        print(f"Variation: {self.variation}")

    def source_getter(self):
        return self.get('source', shader_unselected_default_text)

    def variation_items_update(self, context):
        items = []
        if self.variations:
            for variation in self.variations:
                items.append((f'{variation.name}', f'{variation.name}', f"The shader variation '{variation.name}'"))
        else:
            items.append((shader_no_variations, 'No Variations', 'There are no variations defined in the shader'))

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
        print(f"set the variation to '{value}', which is {self.variation}")
        if self.variation != shader_no_variations:
            bpy.ops.i3dio.load_custom_shader_variation()

    def variation_getter(self):
        return self.get('variation', shader_no_variations)

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


@register
class I3D_IO_PT_shader(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_label = "I3D Shader Settings"
    bl_context = 'material'

    @classmethod
    def poll(cls, context):
        return context.object is not None

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        material = bpy.context.active_object.active_material

        layout.prop(material.i3d_attributes, 'source')
        if material.i3d_attributes.variations:
            layout.prop(material.i3d_attributes, 'variation')


@register
class I3D_IO_PT_shader_attributes(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_label = "Attributes"
    bl_context = 'material'
    bl_parent_id = 'I3D_IO_PT_shader'

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.active_material.i3d_attributes.shader_parameters

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        parameters = bpy.context.active_object.active_material.i3d_attributes.shader_parameters
        for parameter in parameters:
            if parameter.type == 'float':
                property_type = 'data_float_1'
            elif parameter.type == 'float2':
                property_type = 'data_float_2'
            elif parameter.type == 'float3':
                property_type = 'data_float_3'
            else:
                property_type = 'data_float_4'

            layout.prop(parameter, property_type, text=parameter.name)


@register
class I3D_IO_PT_shader_textures(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_label = "Textures"
    bl_context = 'material'
    bl_parent_id = 'I3D_IO_PT_shader'

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        # properties = bpy.context.active_object.active_material.i3d_attributes.shader_textures
        # for texture_name in properties.__annotations__.keys():
        #     texture = getattr(properties, texture_name)
        #     if texture.enabled:
        #         layout.prop(texture, 'source', text=texture.name)

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.active_material.i3d_attributes.shader_textures


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Material.i3d_attributes = PointerProperty(type=I3DMaterialShader)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Material.i3d_attributes

