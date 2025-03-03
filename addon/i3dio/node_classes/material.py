import bpy
from dataclasses import dataclass
from .. import utility, xml_i3d
from ..i3d import I3D
from ..ui import shader_picker
from .node import Node


@dataclass
class SocketData:
    texture_path: str | None
    bump_depth: float | None
    color: list[float] | None


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

    def is_normalmapped(self) -> bool:
        return 'Normalmap' in self.xml_elements

    def populate_xml_element(self) -> None:
        material = self.blender_material
        if material.use_nodes:
            self._resolve_with_nodes()
        else:
            self._write_color(material.diffuse_color, 'diffuseColor')
            self._write_color([1.0 - material.roughness, 1, material.metallic], 'specularColor')
            self.logger.debug("Does not use nodes")

        self._export_shader_settings()
        self._write_properties()

    def _resolve_with_nodes(self) -> None:
        if (bsdf := next((node for node in self.blender_material.node_tree.nodes
                          if node.bl_idname == "ShaderNodeBsdfPrincipled"), None)) is None:
            self.logger.warning("Uses nodes but Principled BSDF node is not found!")
            return
        self.logger.debug("Uses nodes and has Principled BSDF node")

        self.skip_diffuse = False
        self.has_emission_texture = False
        self.has_glossmap = False

        # Process emission first, since it influences diffuse color
        self._process_material_input('Emission Color', 'Emissivemap', bsdf, use_emission=True)
        # Only export diffuse if Emission Color has no input node
        if not self.has_emission_texture:
            self._process_material_input('Base Color', 'Texture', bsdf)
        self._process_material_input('Normal', 'Normalmap', bsdf)
        self._glossmap_from_nodes(bsdf)
        if not self.has_glossmap:
            self._write_color([1.0 - bsdf.inputs['Roughness'].default_value,
                               bsdf.inputs['Specular IOR Level'].default_value,
                               bsdf.inputs['Metallic'].default_value], 'specularColor')

    def _process_material_input(self, socket_name: str, xml_key: str, node, use_emission=False) -> None:
        """Processes a material property and exports texture or color data."""
        if (socket := node.inputs.get(socket_name)) is None:
            return
        socket_data = self._extract_socket_data(socket)

        # If Emission has no texture and Emission Strength is 0, skip exporting
        if use_emission and not socket_data.texture_path and node.inputs['Emission Strength'].default_value == 0:
            self.logger.debug("Ignoring Emission Color because Emission Strength == 0")
            return

        if socket_data.texture_path:  # Export texture if present
            self._write_texture_to_xml(socket_data.texture_path, xml_key, socket_data.bump_depth)
            if use_emission:
                self.skip_diffuse = True  # If emission has a texture, skip exporting diffuse color
                self.has_emission_texture = True

        elif socket_data.color:  # Export color if no texture is present
            if use_emission:
                self.skip_diffuse = True  # If emission has a color, skip exporting diffuse color
                self._write_color(socket_data.color, 'emissiveColor')
            elif not self.skip_diffuse and xml_key == 'Texture':
                self._write_color(socket_data.color, 'diffuseColor')

    def _extract_socket_data(self, socket: bpy.types.NodeSocket) -> SocketData:
        """Extracts texture path or color data from a given BSDF socket."""
        texture_path = None
        bump_depth = None  # Only used for Normal Map textures
        color = None
        if socket.is_linked:
            try:
                connected_node = socket.links[0].from_node
                # Texture node directly connected to BSDF
                if connected_node.bl_idname == "ShaderNodeTexImage" and connected_node.image:
                    texture_path = connected_node.image.filepath

                # Normal Map node (ShaderNodeTexImage → ShaderNodeNormalMap → BSDF Input)
                if connected_node.bl_idname == "ShaderNodeNormalMap" and connected_node.inputs['Color'].is_linked:
                    normal_map_input = connected_node.inputs['Color'].links[0].from_node
                    if normal_map_input.bl_idname == "ShaderNodeTexImage" and normal_map_input.image:
                        texture_path = normal_map_input.image.filepath
                        if (strength := connected_node.inputs['Strength'].default_value) != 1.0:
                            bump_depth = strength

                # Color sockets can have a ShaderNodeRGB connected to them for color input
                if connected_node.bl_idname == "ShaderNodeRGB":
                    color = connected_node.outputs['Color'].default_value

            except (AttributeError, IndexError, KeyError) as e:
                self.logger.exception(f"Failed to extract socket data for {socket.name}: {e}")
        # If no texture path or color was found, use the default value of the socket
        if not (texture_path or color):
            self.logger.debug(f"Has no texture or color for {socket.name}, using default value")
            color = socket.default_value
        return SocketData(texture_path, bump_depth, color)

    def _find_node_by_name(self, name: str) -> bpy.types.Node:
        return next((node for node in self.blender_material.node_tree.nodes
                     if node.name.lower() == name or node.label.lower() == name), None)

    def _extract_glossmap_data(self, gloss_node: bpy.types.Node) -> SocketData | None:
        """Extracts texture data from a detected glossmap node."""
        if gloss_node.bl_idname == "ShaderNodeTexImage" and gloss_node.image:
            return SocketData(gloss_node.image.filepath, None, None)
        if gloss_node.bl_idname == "ShaderNodeSeparateColor":
            return self._extract_socket_data(gloss_node.inputs.get('Color'))
        return None

    def _glossmap_from_nodes(self, bsdf: bpy.types.ShaderNodeBsdfPrincipled) -> None:
        """Handles special glossmap node lookup and extraction."""
        gloss_node = self._find_node_by_name('glossmap')
        gloss_socket_data = self._extract_glossmap_data(gloss_node) if gloss_node else None

        # If no named Glossmap node was found, check the Specular IOR Level input
        if not (gloss_socket_data and gloss_socket_data.texture_path):
            gloss_socket_data = self._extract_socket_data(bsdf.inputs.get("Specular IOR Level"))

        if gloss_socket_data and gloss_socket_data.texture_path:
            self._write_texture_to_xml(gloss_socket_data.texture_path, 'Glossmap')
            self.has_glossmap = True
        else:
            self.logger.debug("Has no Glossmap")

    def _write_texture_to_xml(self, texture_path: str, xml_key: str, bump_depth: float = None) -> None:
        """Handles writing texture file references to XML."""
        if texture_path:
            self.logger.debug(f"Has {xml_key}: '{utility.as_fs_relative_path(texture_path)}'")
            file_id = self.i3d.add_file_image(texture_path)
            self.xml_elements[xml_key] = xml_i3d.SubElement(self.element, xml_key)
            self._write_attribute('fileId', file_id, xml_key)
            if bump_depth is not None:
                self._write_attribute('bumpDepth', "{0:.6f}".format(bump_depth), xml_key)

    def _write_color(self, color: list[float], xml_key: str) -> None:
        self._write_attribute(xml_key, " ".join(map('{0:.6f}'.format, color)))

    def _write_properties(self):
        # Alpha blending
        if self.blender_material.i3d_attributes.alpha_blending:
            self._write_attribute('alphaBlending', True)
        # Shading rate
        if (shading_rate := self.blender_material.i3d_attributes.shading_rate) != '1x1':
            self._write_attribute('shadingRate', shading_rate)

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
