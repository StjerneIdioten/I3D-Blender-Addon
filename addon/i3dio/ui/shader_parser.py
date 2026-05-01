from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path

import bpy
from bpy.app.handlers import persistent, load_post

from .. import xml_i3d
from ..debugging import addon_logger
from ..utility import get_fs_data_path


logger = addon_logger.getChild("shader_parser")


@dataclass
class ShaderParameter:
    name: str
    component_count: int
    default_value: list[float]
    min_value: float = -xml_i3d.i3d_max
    max_value: float = xml_i3d.i3d_max
    description: str = ''
    template: str = 'default'


@dataclass
class ShaderTexture:
    name: str
    default_file: str
    template: str = 'default'


@dataclass
class ShaderMetadata:
    path: Path
    variations: dict[str, list[str]] = field(default_factory=dict)
    parameter_templates: dict[str, str] = field(default_factory=dict)
    parameters: dict[str, list[ShaderParameter]] = field(default_factory=dict)
    textures: dict[str, list[ShaderTexture]] = field(default_factory=dict)
    vertex_attributes: dict[str, str] = field(default_factory=dict)
    param_lookup: dict[str, ShaderParameter] = field(default_factory=dict)


ShaderDict = dict[str, ShaderMetadata]


SHADERS_GAME: ShaderDict = {}
SHADERS_CUSTOM: ShaderDict = {}


def get_shader_dict(use_custom: bool = False) -> ShaderDict:
    return SHADERS_CUSTOM if use_custom else SHADERS_GAME


def parse_shader_parameters(parameter: xml_i3d.XML_Element) -> list[ShaderParameter]:
    """Parses a shader parameter element and returns shader parameter data."""
    type_str = parameter.attrib.get('type', 'float4')
    component_count = {'float': 1, 'float1': 1, 'float2': 2, 'float3': 3, 'float4': 4}.get(type_str, 4)
    
    def _parse_float_list(value: str | None, default: float = 0.0) -> list[float]:
        if value is None:
            return [default] * component_count
        try:
            values = [float(x) for x in value.split()]
        except ValueError:
            return [default] * component_count
        # If too many, truncate; if too few, pad with default
        return (values + [default] * component_count)[:component_count]

    param_name = parameter.attrib['name']
    template = parameter.attrib.get('template', 'default')
    description = parameter.attrib.get("description", "").replace("\\n", "\n")

    default_value = _parse_float_list(parameter.attrib.get('defaultValue'))
    min_values = _parse_float_list(parameter.attrib.get('minValue'), min(-xml_i3d.i3d_max, min(default_value)))
    max_values = _parse_float_list(parameter.attrib.get('maxValue'), max(xml_i3d.i3d_max, max(default_value)))
    # Blender supports only a single min/max per prop, so if all are the same, use that; else fallback to i3d_max
    min_single = min_values[0] if all(x == min_values[0] for x in min_values) else -xml_i3d.i3d_max
    max_single = max_values[0] if all(x == max_values[0] for x in max_values) else xml_i3d.i3d_max

    def make_parameter(name: str, value: list[float]) -> ShaderParameter:
        return ShaderParameter(
            name=name,
            component_count=component_count,
            default_value=value,
            min_value=min_single,
            max_value=max_single,
            description=description,
            template=template
        )

    if parameter.attrib.get('arraySize') is None:
        return [make_parameter(param_name, default_value)]
    return [
        make_parameter(
            name=f"{param_name}{child.attrib.get('index', i)}",
            value=_parse_float_list(child.text),
        )
        for i, child in enumerate(parameter)
    ]


def parse_shader_texture(texture: xml_i3d.XML_Element) -> ShaderTexture:
    """Parses a shader texture element and returns shader texture data."""
    return ShaderTexture(
        name=texture.attrib['name'],
        default_file=texture.attrib.get('defaultFilename', ''),
        template=texture.attrib.get('template', 'default'),
    )


def load_shader(path: Path) -> ShaderMetadata | None:
    tree = xml_i3d.parse(path)
    if tree is None:
        return None
    root = tree.getroot()
    if root.tag != 'CustomShader':
        return None
    shader = ShaderMetadata(path)

    for variation in xml_i3d.iter_section(root, 'Variations', 'Variation'):
        # Some variations don't have a group defined, but should still use the 'base' group regardless
        shader.variations[variation.attrib.get('name')] = variation.attrib.get('groups', 'base').split()

    for template in xml_i3d.iter_section(root, 'ParameterTemplates', 'ParameterTemplate'):
        shader.parameter_templates[template.attrib['id']] = template.attrib['filename']

    for param in xml_i3d.iter_section(root, 'Parameters', 'Parameter'):
        shader.parameters.setdefault(param.attrib.get('group', 'base'), []).extend(parse_shader_parameters(param))

    for tex in xml_i3d.iter_section(root, 'Textures', 'Texture'):
        shader.textures.setdefault(tex.attrib.get('group', 'base'), []).append(parse_shader_texture(tex))

    for attr in xml_i3d.iter_section(root, 'VertexAttributes', 'VertexAttribute'):
        shader.vertex_attributes[attr.attrib['name']] = attr.attrib.get('group', 'base')

    # Add a lookup for parameters to easily access them by name
    shader.param_lookup = {param.name: param for group in shader.parameters.values() for param in group}
    return shader


def load_shaders_from_directory(directory: Path) -> ShaderDict:
    """Scans a directory for .xml shader files and returns a dict of shader_name -> ShaderMetadata"""
    return {path.stem: shader for path in directory.glob('*.xml') if (shader := load_shader(path))}


def populate_game_shaders() -> None:
    SHADERS_GAME.clear()

    shader_dir = get_fs_data_path(as_path=True) / 'shaders'
    if shader_dir.is_dir():
        SHADERS_GAME.update(load_shaders_from_directory(shader_dir))
    else:
        logger.warning("Game shader directory does not exist: %s", shader_dir)
    logger.info("Loaded %d game shaders", len(SHADERS_GAME))


def populate_custom_shaders() -> None:
    SHADERS_CUSTOM.clear()

    try:
        loaded_paths: set[Path] = set()
        for scene in bpy.data.scenes:
            for entry in scene.i3dio.custom_shader_folders:
                path = Path(bpy.path.abspath(entry.path))
                if path in loaded_paths:
                    continue
                loaded_paths.add(path)
                if path.is_dir():
                    SHADERS_CUSTOM.update(load_shaders_from_directory(path))
                else:
                    logger.warning("Custom shader folder does not exist: %s", entry.path)
    except Exception:
        logger.exception("Error reading custom shader folders")
    logger.info("Loaded %d custom shaders", len(SHADERS_CUSTOM))


@persistent
def populate_shader_cache_handler(_dummy) -> None:
    populate_game_shaders()
    populate_custom_shaders()


def register() -> None:
    if populate_shader_cache_handler not in load_post:
        load_post.append(populate_shader_cache_handler)


def unregister() -> None:
    if populate_shader_cache_handler in load_post:
        load_post.remove(populate_shader_cache_handler)
