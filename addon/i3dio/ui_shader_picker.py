import xml.etree.ElementTree as ET
import bpy
from bpy.types import (Panel)
from bpy.props import (
    StringProperty,
    PointerProperty,
    EnumProperty
)

classes = []


def register(cls):
    classes.append(cls)
    return cls


class I3DShader:
    def __init__(self, shader_path: str):
        self.parameters = {}
        self.variations = {}
        tree = ET.parse(shader_path)
        root = tree.getroot()
        variations = root.find('Variations')
        for variation in variations:
            print(f"{variation.tag}: name='{variation.attrib['name']}', groups='{variation.attrib['groups']}'")


@register
class I3DMaterialShader(bpy.types.PropertyGroup):

    def source_setter(self, value):
        #if self['source'] != value:
        self['source'] = value
        shader = I3DShader(bpy.path.abspath(value))
        print(f"Set shader source to '{value}'")

    def source_getter(self):
        return self.get('source', '')

    def variation_items_update(self, context):
        print("Updated shader variation")
        return (('VAR1', 'Variation1', 'First variation'),)

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




@register
class I3D_IO_PT_shader_attributes(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_label = "I3D Shader Attributes"
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


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Material.i3d_attributes = PointerProperty(type=I3DMaterialShader)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Material.i3d_attributes