import xml.etree.ElementTree as ET
import random
import string
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
    type: EnumProperty(items=[('FLOAT1', '', ''), ('FLOAT2', '', ''), ('FLOAT3', '', ''), ('FLOAT4', '', '')])
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
    bl_options = set()

    def execute(self, context):

        # properties = bpy.context.active_object.active_material.i3d_attributes.shader_properties
        # textures = bpy.context.active_object.active_material.i3d_attributes.shader_textures

        # for attribute_name in properties.__annotations__.keys():
        #     attribute = getattr(properties, attribute_name)
        #     attribute.enabled = bool(random.getrandbits(1))
        #     attribute.name = ''.join(random.choice(string.ascii_letters) for i in range(8))
        #     attribute.type = random.choice(['FLOAT', 'FLOAT4'])
        #
        # for texture_name in textures.__annotations__.keys():
        #     texture = getattr(textures, texture_name)
        #     texture.enabled = bool(random.getrandbits(1))
        #     texture.name = ''.join(random.choice(string.ascii_letters) for i in range(8))

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

        print('Ran the operator')

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
        print(f"set the variation to '{value}'")

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

    #shader_properties: PointerProperty(type=I3DShaderProperties)
    shader_parameters: CollectionProperty(type=I3DShaderParameter)

    #shader_textures: PointerProperty(type=I3DShaderTextures)
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

        # properties = bpy.context.active_object.active_material.i3d_attributes.shader_properties
        # for attribute_name in properties.__annotations__.keys():
        #     attribute = getattr(properties, attribute_name)
        #     if attribute.enabled:
        #         if attribute.type == 'FLOAT4':
        #             attribute_type = 'data_float_4'
        #         else:
        #             attribute_type = 'data_float'
        #
        #         layout.prop(attribute, attribute_type, text=attribute.name)


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

