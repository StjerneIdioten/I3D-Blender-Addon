import math
from typing import ClassVar
import bpy
import mathutils
from bpy_extras.node_shader_utils import PrincipledBSDFWrapper, ShaderImageTextureWrapper
from .. import utility, xml_i3d
from ..i3d import I3D
from ..ui.shader_picker import SHADER_DEFAULT
from ..ui.shader_parser import get_shader_dict
from .node import Node


class Material(Node):
    ELEMENT_TAG: ClassVar[str] = 'Material'
    NAME_FIELD_NAME: ClassVar[str] = 'name'
    ID_FIELD_NAME: ClassVar[str] = 'materialId'

    def __init__(self, id_: int, i3d: I3D, blender_material: bpy.types.Material):
        self.blender_material = blender_material
        self.i3d_attrs = blender_material.i3d_attributes
        super().__init__(id_, i3d, None)

    @property
    def name(self):
        return self.blender_material.name

    @property
    def element(self):
        return self.xml_elements['Node']

    @element.setter
    def element(self, value):
        self.xml_elements['Node'] = value

    def is_normalmapped(self) -> bool:
        return 'Normalmap' in self.xml_elements

    def requires_color_attribute(self) -> bool:
        """Returns True if the shader assigned to this material requires a color attribute (vertex color)."""
        return any("color" in attr.name.lower() for attr in self.i3d_attrs.required_vertex_attributes)

    def get_slot_name(self) -> str | None:
        """Returns the material slot name if it's set, otherwise returns the material name."""
        if self.i3d_attrs.use_material_slot_name:
            return self.i3d_attrs.material_slot_name or self.blender_material.name
        return None

    def populate_xml_element(self) -> None:
        vehicle_shader = (self.i3d_attrs.shader_name == "vehicleShader")
        principled = PrincipledBSDFWrapper(self.blender_material, is_readonly=True)
        bsdf = principled.node_principled_bsdf

        emission_tex_path = self._image_path(principled.emission_color_texture)
        skip_diffuse = False
        if emission_tex_path:
            self._write_texture_to_xml(emission_tex_path, 'Emissivemap')
            skip_diffuse = True
        elif principled.emission_strength > 0:
            emis_color = (
                self._linked_rgb_color(bsdf.inputs['Emission Color'] if bsdf else None) or principled.emission_color
            )
            self._write_color(emis_color, 'emissiveColor')
            skip_diffuse = True

        if not skip_diffuse:
            base_tex_path = self._image_path(principled.base_color_texture)
            if base_tex_path:
                self._write_texture_to_xml(base_tex_path, 'Texture')
            else:
                base_col = self._linked_rgb_color(bsdf.inputs['Base Color'] if bsdf else None) or principled.base_color
                self._write_color(base_col, 'diffuseColor')

        normalmap_tex_path = self._image_path(principled.normalmap_texture)
        if normalmap_tex_path:
            bump_depth = principled.normalmap_strength if principled.normalmap_strength != 1.0 else None
            self._write_texture_to_xml(normalmap_tex_path, 'Normalmap', bump_depth)

        gloss_path = None
        if glossnode := self._find_node_by_name('glossmap'):
            match glossnode.bl_idname:
                case "ShaderNodeTexImage":
                    gloss_path = self._image_path(glossnode)
                case "ShaderNodeSeparateColor":
                    input = glossnode.inputs['Color']
                    if input.is_linked and (source := input.links[0].from_node).bl_idname == "ShaderNodeTexImage":
                        gloss_path = self._image_path(source)
        else:
            gloss_path = self._image_path(principled.specular_texture)

        if gloss_path:
            self._write_texture_to_xml(gloss_path, 'Glossmap')
        elif not gloss_path and not vehicle_shader:
            self._write_color([1.0 - principled.roughness, principled.specular, principled.metallic], 'specularColor')

        if vehicle_shader:
            if "Texture" not in self.xml_elements:
                self.logger.info("No Texture found, using default white diffuse texture")
                self._write_texture_to_xml("$data/shared/white_diffuse.dds", "Texture")
            if "Glossmap" not in self.xml_elements:
                self.logger.info("No Glossmap found, using default vmask texture")
                self._write_texture_to_xml("$data/shared/default_vmask.dds", "Glossmap")
            if "Normalmap" not in self.xml_elements:
                self.logger.info("No Normalmap found, using default normalmap texture")
                self._write_texture_to_xml("$data/shared/default_normal.dds", "Normalmap")

        self._write_properties()
        self._export_shader_settings()

    def _write_properties(self):
        try:
            xml_i3d.write_i3d_properties(self.blender_material, self.i3d_attrs, self.xml_elements)
        except AttributeError:
            pass

    def _export_shader_settings(self) -> None:
        if self.i3d_attrs.shader_name != SHADER_DEFAULT:
            shaders = get_shader_dict(self.i3d_attrs.use_custom_shaders)
            shader_path = str(shaders[self.i3d_attrs.shader_name].path)
            shader_file_id = self.i3d.add_file_shader(shader_path)
            self._write_attribute('customShaderId', shader_file_id)
            self.logger.debug(f"Shader: '{self.i3d_attrs.shader_name}' with ID: {shader_file_id}")

            if self.i3d_attrs.shader_name == "mirrorShader":
                params = {'type': 'planar', 'refractiveIndex': '10', 'bumpScale': '0.1'}
                xml_i3d.SubElement(self.element, 'Reflectionmap', params)

            if self.i3d_attrs.shader_variation_name != SHADER_DEFAULT:
                self._write_attribute('customShaderVariation', self.i3d_attrs.shader_variation_name)
            for pname in self.i3d_attrs.shader_material_params.keys():
                parameter_dict = {'name': pname}
                value = self.i3d_attrs.shader_material_params[pname]
                default = self.i3d_attrs.shader_material_params.id_properties_ui(pname).as_dict().get('default')
                if len(value) == 1:
                    if not math.isclose(value[0], default[0], abs_tol=1e-7):
                        parameter_dict['value'] = f'{value[0]:.6g}'
                        xml_i3d.SubElement(self.element, 'CustomParameter', parameter_dict)
                else:
                    if not utility.vector_compare(mathutils.Vector(value), mathutils.Vector(default)):
                        parameter_dict['value'] = ' '.join(f'{v:.6g}' for v in value)
                        xml_i3d.SubElement(self.element, 'CustomParameter', parameter_dict)

            for texture in self.i3d_attrs.shader_material_textures:
                self.logger.debug(f"Texture: '{texture.source}', default: {texture.default_source}")
                if '' != texture.source != texture.default_source:
                    texture_dict = {'name': texture.name, 'fileId': str(self.i3d.add_file_image(texture.source))}
                    xml_i3d.SubElement(self.element, 'Custommap', texture_dict)

    def _write_texture_to_xml(self, texture_path: str, xml_key: str, bump_depth: float = None) -> None:
        """Handles writing texture file references to XML."""
        self.logger.debug(f"Has {xml_key}: {utility.as_fs_relative_path(texture_path).as_posix()!r}")
        file_id = self.i3d.add_file_image(texture_path)
        self.xml_elements[xml_key] = xml_i3d.SubElement(self.element, xml_key)
        self._write_attribute('fileId', file_id, xml_key)
        if bump_depth is not None:
            self._write_attribute('bumpDepth', "{0:.6g}".format(bump_depth), xml_key)

    def _write_color(self, color: list[float], xml_key: str) -> None:
        self._write_attribute(xml_key, " ".join(map('{0:.6g}'.format, color)))

    def _find_node_by_name(self, name: str) -> bpy.types.Node | None:
        if not self.blender_material.node_tree:
            return None
        return next((node for node in self.blender_material.node_tree.nodes
                     if node.name.lower() == name or node.label.lower() == name), None)

    def _linked_rgb_color(self, socket: bpy.types.NodeSocket) -> list[float] | None:
        """If the socket is linked to a RGB node, return its color, otherwise None."""
        if not socket or not socket.is_linked:
            return None
        from_node = socket.links[0].from_node
        if from_node.bl_idname == 'ShaderNodeRGB':
            return from_node.outputs['Color'].default_value
        return None

    @staticmethod
    def _image_path(tex: ShaderImageTextureWrapper | bpy.types.ShaderNodeTexImage | None) -> str | None:
        if not tex or not tex.image:
            return None
        return tex.image.filepath_from_user() or (tex.image.filepath if tex.image.filepath else None)
