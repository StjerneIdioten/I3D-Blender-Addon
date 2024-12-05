import bpy

from .node import Node

from .. import (
    utility, xml_i3d
)
from ..ui import shader_picker

from ..i3d import I3D


class Material(Node):
    ELEMENT_TAG = 'Material'
    NAME_FIELD_NAME = 'name'
    ID_FIELD_NAME = 'materialId'

    def __init__(self, id_: int, i3d: I3D, blender_material: bpy.types.Material):
        self.blender_material = blender_material
        super().__init__(id_, i3d, None)

    @property
    def name(self):
        return self.blender_material.name

    @property
    def element(self):
        return self.xml_elements['node']

    @element.setter
    def element(self, value):
        self.xml_elements['node'] = value

    def is_normalmapped(self):
        return 'Normalmap' in self.xml_elements

    def populate_xml_element(self):
        if self.blender_material.use_nodes:
            self._resolve_with_nodes()
        else:
            self._resolve_without_nodes()
        self._export_shader_settings()
        self._write_properties()

    def _resolve_with_nodes(self):
        main_node = self.blender_material.node_tree.nodes.get('Principled BSDF')
        if main_node is not None:
            self._diffuse_from_nodes(main_node)
            self._normal_from_nodes(main_node)
            self._specular_from_nodes(main_node)
            self._emissive_from_nodes(main_node)
        else:
            self.logger.warning(f"Uses nodes but Principled BSDF node is not found!")

        gloss_node = self.blender_material.node_tree.nodes.get('Glossmap')
        specular_socket = main_node.inputs['Specular IOR Level']
        if gloss_node is not None:
            try:
                if gloss_node.type == "SEPARATE_COLOR":
                    gloss_image_path = gloss_node.inputs['Color'].links[0].from_node.image.filepath
                elif gloss_node.type == "TEX_IMAGE":
                    gloss_image_path = gloss_node.image.filepath
                else:
                    raise AttributeError(f"Has an improperly setup Glossmap")
            except (AttributeError, IndexError, KeyError):
                self.logger.exception(f"Has an improperly setup Glossmap")
            else:
                self.logger.debug(f"Has Glossmap '{utility.as_fs_relative_path(gloss_image_path)}'")
                file_id = self.i3d.add_file_image(gloss_image_path)
                self.xml_elements['Glossmap'] = xml_i3d.SubElement(self.element, 'Glossmap')
                self._write_attribute('fileId', file_id, 'Glossmap')
        elif specular_socket.is_linked:
            connected_node = specular_socket.links[0].from_node
            if connected_node.type == "TEX_IMAGE":
                if connected_node.image is None:
                    self.logger.error(f"Specular node has no image")
                else:
                    self.logger.debug(f"Has Glossmap '{utility.as_fs_relative_path(connected_node.image.filepath)}'")
                    file_id = self.i3d.add_file_image(connected_node.image.filepath)
                    self.xml_elements['Glossmap'] = xml_i3d.SubElement(self.element, 'Glossmap')
                    self._write_attribute('fileId', file_id, 'Glossmap')
            else:
                self.logger.debug(f"Specular node is not a TEX_IMAGE node")
        else:
            self.logger.debug(f"Has no Glossmap")

    def _specular_from_nodes(self, node):
        specular = [1.0 - node.inputs['Roughness'].default_value,
                    node.inputs['Specular IOR Level'].default_value,
                    node.inputs['Metallic'].default_value]
        self._write_specular(specular)

    def _normal_from_nodes(self, node):
        normal_node_socket = node.inputs['Normal']
        if normal_node_socket.is_linked:
            try:
                normal_image_path = normal_node_socket.links[0].from_node.inputs['Color'].links[0] \
                    .from_node.image.filepath
            except (AttributeError, IndexError, KeyError):
                self.logger.exception(f"Has an improperly setup Normalmap")
            else:
                self.logger.debug(f"Has Normalmap '{utility.as_fs_relative_path(normal_image_path)}'")
                file_id = self.i3d.add_file_image(normal_image_path)
                self.xml_elements['Normalmap'] = xml_i3d.SubElement(self.element, 'Normalmap')
                self._write_attribute('fileId', file_id, 'Normalmap')
        else:
            self.logger.debug(f"Has no Normalmap")

    def _diffuse_from_nodes(self, node):
        color_socket = node.inputs['Base Color']
        diffuse = color_socket.default_value
        if color_socket.is_linked:
            try:
                color_connected_node = color_socket.links[0].from_node
                if color_connected_node.bl_idname == 'ShaderNodeRGB':
                    diffuse = color_connected_node.outputs[0].default_value
                    diffuse_image_path = None
                else:
                    diffuse_image_path = color_connected_node.image.filepath
            except (AttributeError, IndexError, KeyError):
                self.logger.exception(f"Has an improperly setup Texture")
            else:
                if diffuse_image_path is not None:
                    self.logger.debug(f"Has diffuse texture '{utility.as_fs_relative_path(diffuse_image_path)}'")
                    file_id = self.i3d.add_file_image(diffuse_image_path)
                    self.xml_elements['Texture'] = xml_i3d.SubElement(self.element, 'Texture')
                    self._write_attribute('fileId', file_id, 'Texture')
        else:
            # Write the diffuse colors
            emission_socket = node.inputs['Emission Color']
            if not emission_socket.is_linked:
                self._write_diffuse(diffuse)

    def _emissive_from_nodes(self, node):
        emission_socket = node.inputs['Emission Color']
        emission_c = emission_socket.default_value
        emissive_path = None
        if emission_socket.is_linked:
            try:
                color_connected_node = emission_socket.links[0].from_node
                if color_connected_node.bl_idname == 'ShaderNodeRGB':
                    emission_c = color_connected_node.outputs[0].default_value
                else:
                    emissive_path = emission_socket.links[0].from_node.image.filepath
            except (AttributeError, IndexError, KeyError):
                self.logger.exception(f"Has an improperly setup Texture")
            else:
                if emissive_path is not None:
                    self.logger.info("Has Emissivemap")
                    file_id = self.i3d.add_file_image(emissive_path)
                    self.xml_elements['Emissive'] = xml_i3d.SubElement(self.element, 'Emissivemap')
                    self._write_attribute('fileId', file_id, 'Emissive')
                    return
            self.logger.debug("Has no Emissivemap")

        has_emission = node.inputs['Emission Strength'].default_value == 0.0
        if not has_emission:
            self.logger.debug("Write emissiveColor")
            self._write_emission(emission_c)

    def _resolve_without_nodes(self):
        material = self.blender_material
        self._write_diffuse(material.diffuse_color)
        self._write_specular([1.0 - material.roughness, 1, material.metallic])
        self.logger.debug(f"Does not use nodes")

    def _write_diffuse(self, diffuse_color):
        self._write_attribute('diffuseColor', "{0:.6f} {1:.6f} {2:.6f} {3:.6f}".format(*diffuse_color))

    def _write_specular(self, specular_color):
        self._write_attribute('specularColor', "{0:.6f} {1:.6f} {2:.6f}".format(*specular_color))

    def _write_emission(self, emission_color):
        self._write_attribute('emissiveColor', "{0:.6f} {1:.6f} {2:.6f} {3:.6f}".format(*emission_color))

    def _write_properties(self):
        # Alpha blending
        if self.blender_material.surface_render_method == 'BLENDED':
            self._write_attribute('alphaBlending', True)

    def _export_shader_settings(self):
        shader_settings = self.blender_material.i3d_attributes
        if shader_settings.source != shader_picker.shader_unselected_default_text:
            shader_file_id = self.i3d.add_file_shader(shader_settings.source)
            self._write_attribute('customShaderId', shader_file_id)
            if shader_settings.source.endswith("mirrorShader.xml"):
                params = {'type': 'planar', 'refractiveIndex': '10', 'bumpScale': '0.1'}
                xml_i3d.SubElement(self.element, 'Reflectionmap', params)

            if shader_settings.variation != shader_picker.shader_no_variation:
                self._write_attribute('customShaderVariation', shader_settings.variation)
            for parameter in shader_settings.shader_parameters:
                parameter_dict = {'name': parameter.name}
                if parameter.type == 'float':
                    value = [parameter.data_float_1]
                elif parameter.type == 'float2':
                    value = parameter.data_float_2
                elif parameter.type == 'float3':
                    value = parameter.data_float_3
                elif parameter.type == 'float4':
                    value = parameter.data_float_4
                else:
                    value = []

                value = ' '.join(map('{0:.6f}'.format, value))
                parameter_dict['value'] = value

                xml_i3d.SubElement(self.element, 'CustomParameter', parameter_dict)

            for texture in shader_settings.shader_textures:
                self.logger.debug(f"Texture: '{texture.source}', default: {texture.default_source}")
                if '' != texture.source != texture.default_source:
                    texture_dict = {'name': texture.name}
                    texture_id = self.i3d.add_file_image(texture.source)
                    texture_dict['fileId'] = str(texture_id)

                    xml_i3d.SubElement(self.element, 'Custommap', texture_dict)
