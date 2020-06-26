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
    FloatProperty
)

classes = []


def register(cls):
    classes.append(cls)
    return cls


@register
class I3DShaderParameter(bpy.types.PropertyGroup):
    name: StringProperty(default='Unnamed Attribute')
    enabled: BoolProperty(default=False)
    type: EnumProperty(items=[('FLOAT', '', ''), ('FLOAT4', '', '')])
    data_float: FloatProperty()
    data_float_min: FloatProperty()
    data_float_max: FloatProperty()
    data_float_4: FloatVectorProperty(size=4)
    data_float_4_min: FloatVectorProperty(size=4)
    data_float_4_max: FloatVectorProperty(size=4)


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
class I3DShaderProperties(bpy.types.PropertyGroup):
    attribute_0: PointerProperty(type=I3DShaderParameter)
    attribute_1: PointerProperty(type=I3DShaderParameter)
    attribute_2: PointerProperty(type=I3DShaderParameter)
    attribute_3: PointerProperty(type=I3DShaderParameter)
    attribute_4: PointerProperty(type=I3DShaderParameter)
    attribute_5: PointerProperty(type=I3DShaderParameter)
    attribute_6: PointerProperty(type=I3DShaderParameter)
    attribute_7: PointerProperty(type=I3DShaderParameter)
    attribute_8: PointerProperty(type=I3DShaderParameter)
    attribute_9: PointerProperty(type=I3DShaderParameter)
    attribute_10: PointerProperty(type=I3DShaderParameter)
    attribute_11: PointerProperty(type=I3DShaderParameter)
    attribute_12: PointerProperty(type=I3DShaderParameter)
    attribute_13: PointerProperty(type=I3DShaderParameter)
    attribute_14: PointerProperty(type=I3DShaderParameter)
    attribute_15: PointerProperty(type=I3DShaderParameter)
    attribute_16: PointerProperty(type=I3DShaderParameter)
    attribute_17: PointerProperty(type=I3DShaderParameter)
    attribute_18: PointerProperty(type=I3DShaderParameter)


@register
class I3DShaderTextures(bpy.types.PropertyGroup):
    texture_0: PointerProperty(type=I3DShaderTexture)
    texture_1: PointerProperty(type=I3DShaderTexture)
    texture_2: PointerProperty(type=I3DShaderTexture)
    texture_3: PointerProperty(type=I3DShaderTexture)
    texture_4: PointerProperty(type=I3DShaderTexture)
    texture_5: PointerProperty(type=I3DShaderTexture)
    texture_6: PointerProperty(type=I3DShaderTexture)
    texture_7: PointerProperty(type=I3DShaderTexture)
    texture_8: PointerProperty(type=I3DShaderTexture)
    texture_9: PointerProperty(type=I3DShaderTexture)
    texture_10: PointerProperty(type=I3DShaderTexture)
    texture_11: PointerProperty(type=I3DShaderTexture)


@register
class I3DLoadCustomShader(bpy.types.Operator):
    """Can load in and generate a custom class for a shader, so settings can be set for export"""
    bl_idname = 'i3dio.load_custom_shader'
    bl_label = 'Load custom shader'
    bl_description = ''
    bl_options = set()

    def execute(self, context):

        properties = bpy.context.active_object.active_material.i3d_attributes.shader_properties
        textures = bpy.context.active_object.active_material.i3d_attributes.shader_textures

        for attribute_name in properties.__annotations__.keys():
            attribute = getattr(properties, attribute_name)
            attribute.enabled = bool(random.getrandbits(1))
            attribute.name = ''.join(random.choice(string.ascii_letters) for i in range(8))
            attribute.type = random.choice(['FLOAT', 'FLOAT4'])

        for texture_name in textures.__annotations__.keys():
            texture = getattr(textures, texture_name)
            texture.enabled = bool(random.getrandbits(1))
            texture.name = ''.join(random.choice(string.ascii_letters) for i in range(8))

        print('Ran the operator')

        return {'FINISHED'}


@register
class I3DMaterialShader(bpy.types.PropertyGroup):

    def source_setter(self, value):
        #if self['source'] != value:
        self['source'] = value
        print(f"Set shader source to '{value}'")
        #bpy.context.object.active_material.i3d_attributes.shader_properties.bl_rna.properties['attribute_0'].description = 'Hård penis'
        #bpy.context.object.active_material.i3d_attributes.shader_properties.attribute_1 = bpy.props.FloatVectorProperty(name='miav', default='kat')
        #print(bpy.context.object.active_material.i3d_attributes.shader_properties.bl_rna.properties['attribute_0'].description)
        #stuff = bpy.context.object.active_material.i3d_attributes.bl_rna.properties
        #for s in stuff:
        #   print(s)
        #for prop_key in prop_group.__annotations__.keys():
            #print(prop_key)
        bpy.ops.i3dio.load_custom_shader()

    def source_getter(self):
        return self.get('source', '')

    def variation_items_update(self, context):
        #print("Updated shader variation")
        return (('VAR1', 'Variation1', 'First variation'),('VAR2', 'Variation2', 'Second variation'))

    source: StringProperty(name='Shader Source',
                           description='Path to the shader',
                           subtype='FILE_PATH',
                           default='',
                           set=source_setter,
                           get=source_getter
                           )

    variation: EnumProperty(name='Variation',
                            description='The shader variation',
                            default=None,
                            items=variation_items_update,
                            options=set(),
                            update=None,
                            get=None,
                            set=None
                            )

    shader_properties: PointerProperty(type=I3DShaderProperties)

    shader_textures: PointerProperty(type=I3DShaderTextures)


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
        return context.object is not None

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        properties = bpy.context.active_object.active_material.i3d_attributes.shader_properties
        for attribute_name in properties.__annotations__.keys():
            attribute = getattr(properties, attribute_name)
            if attribute.enabled:
                if attribute.type == 'FLOAT4':
                    attribute_type = 'data_float_4'
                else:
                    attribute_type = 'data_float'

                layout.prop(attribute, attribute_type, text=attribute.name)


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

        properties = bpy.context.active_object.active_material.i3d_attributes.shader_textures
        for texture_name in properties.__annotations__.keys():
            texture = getattr(properties, texture_name)
            if texture.enabled:
                layout.prop(texture, 'source', text=texture.name)

    @classmethod
    def poll(cls, context):
        return context.object is not None

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Material.i3d_attributes = PointerProperty(type=I3DMaterialShader)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Material.i3d_attributes

