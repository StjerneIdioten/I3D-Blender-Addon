from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path

import bpy
from bpy.app.handlers import (persistent, load_post)

from .helper_functions import get_fs_data_path
from .. import xml_i3d


SHADERS_GAME: ShaderDict = {}
SHADERS_CUSTOM: ShaderDict = {}


@dataclass
class ShaderParameter:
    name: str
    type: int
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
    parameters: dict[str, list[ShaderParameter]] = field(default_factory=dict)
    textures: dict[str, list[ShaderTexture]] = field(default_factory=dict)
    vertex_attributes: dict[str, str] = field(default_factory=dict)
    param_lookup: dict[str, ShaderParameter] = field(default_factory=dict)


ShaderDict = dict[str, ShaderMetadata]


def get_shader_dict(use_custom: bool = False) -> ShaderDict:
    return SHADERS_CUSTOM if use_custom else SHADERS_GAME


def parse_shader_parameters(parameter: xml_i3d.XML_Element) -> list[ShaderParameter]:
    """Parses a shader parameter element and returns a list of dictionaries with parameter data."""
    parameter_list: list[ShaderParameter] = []

    type_str = parameter.attrib.get('type', 'float4')
    type_length = {'float': 1, 'float1': 1, 'float2': 2, 'float3': 3, 'float4': 4}.get(type_str, 4)

    def _parse_floats(val: str | None, default: float = 0.0) -> list[float]:
        if val is None:
            return [default] * type_length
        try:
            vals = [float(x) for x in val.split()]
            # If too many, truncate; if too few, pad with default
            return vals[:type_length] + [default] * (type_length - len(vals))
        except Exception:
            return [default] * type_length

    param_name = parameter.attrib['name']
    template = parameter.attrib.get('template', 'default')
    default_value = _parse_floats(parameter.attrib.get('defaultValue'))
    min_str = parameter.attrib.get('minValue')
    max_str = parameter.attrib.get('maxValue')
    min_value = _parse_floats(min_str) if min_str else [min(-xml_i3d.i3d_max, min(default_value))] * type_length
    max_value = _parse_floats(max_str) if max_str else [max(xml_i3d.i3d_max, max(default_value))] * type_length
    # Blender supports only a single min/max per prop, so if all are the same, use that; else fallback to i3d_max
    min_single = min_value[0] if all(x == min_value[0] for x in min_value) else -xml_i3d.i3d_max
    max_single = max_value[0] if all(x == max_value[0] for x in max_value) else xml_i3d.i3d_max

    description = parameter.attrib.get('description', '')
    if parameter.attrib.get('arraySize') is not None:
        for child in parameter:
            child_default = _parse_floats(child.text)
            parameter_list.append(ShaderParameter(
                name=f"{param_name}{child.attrib.get('index', '')}",
                type=type_length,
                default_value=child_default,
                min_value=min_single,
                max_value=max_single,
                description=description,
                template=template
            ))
    else:
        parameter_list.append(ShaderParameter(
            name=param_name,
            type=type_length,
            default_value=default_value,
            min_value=min_single,
            max_value=max_single,
            description=description,
            template=template
        ))

    return parameter_list


def parse_shader_texture(texture: xml_i3d.XML_Element) -> ShaderTexture:
    """Parses a shader texture element and returns a dictionary with texture data."""
    return ShaderTexture(name=texture.attrib['name'], default_file=texture.attrib.get('defaultFilename', ''),
                         template=texture.attrib.get('template', 'default'))


def load_shader(path: Path) -> ShaderMetadata | None:
    tree = xml_i3d.parse(path)
    if tree is None:
        return None
    root = tree.getroot()
    if root.tag != 'CustomShader':
        return None
    shader = ShaderMetadata(path)

    if (variations := root.find('Variations')) is not None:
        for v in variations:
            if v.tag == 'Variation':
                # Some variations don't have a group defined, but should still use the 'base' group regardless
                shader.variations[v.attrib.get('name')] = v.attrib.get('groups', 'base').split()

    if (parameters := root.find('Parameters')) is not None:
        for p in parameters:
            if p.tag == 'Parameter':  # Default to "base" if no group is specified
                shader.parameters.setdefault(p.attrib.get('group', 'base'), []).extend(parse_shader_parameters(p))

    if (textures := root.find('Textures')) is not None:
        for t in textures:
            if t.tag == 'Texture':  # Default to "base" if no group is specified
                shader.textures.setdefault(t.attrib.get('group', 'base'), []).append(parse_shader_texture(t))

    if (vertex_attributes := root.find('VertexAttributes')) is not None:
        for attr in vertex_attributes:
            if attr.tag == 'VertexAttribute':
                shader.vertex_attributes[attr.attrib['name']] = attr.attrib.get('group', 'base')

    # Add a lookup for parameters to easily access them by name
    shader.param_lookup = {param.name: param for group in shader.parameters.values() for param in group}
    return shader


def load_shaders_from_directory(directory: Path) -> dict:
    """Scans a directory for .xml shader files and returns a dict of shader_name -> ShaderMetadata"""
    return {path.stem: shader for path in directory.glob('*.xml') if (shader := load_shader(path))}


def populate_game_shaders() -> None:
    global SHADERS_GAME
    SHADERS_GAME.clear()

    shader_dir = get_fs_data_path(as_path=True) / 'shaders'
    if shader_dir.exists():
        SHADERS_GAME.update(load_shaders_from_directory(shader_dir))
    print(f"Loaded {len(SHADERS_GAME)} game shaders")


def populate_custom_shaders() -> None:
    global SHADERS_CUSTOM
    SHADERS_CUSTOM.clear()

    try:
        for scene in bpy.data.scenes:
            for entry in scene.i3dio.custom_shader_folders:
                path = Path(bpy.path.abspath(entry.path))
                if path.exists():
                    SHADERS_CUSTOM.update(load_shaders_from_directory(path))
                else:
                    print(f"[Custom Shader] Folder does not exist: {entry.path}")
    except Exception as e:
        print("Error reading custom shader folders:", e)
    print(f"Loaded {len(SHADERS_CUSTOM)} custom shaders")


@persistent
def populate_shader_cache_handler(_dummy) -> None:
    populate_game_shaders()
    populate_custom_shaders()


def register():
    load_post.append(populate_shader_cache_handler)


def unregister():
    load_post.remove(populate_shader_cache_handler)
