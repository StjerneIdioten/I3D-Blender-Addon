from __future__ import annotations

from typing import TYPE_CHECKING

import bpy
from bpy_extras.node_shader_utils import PrincipledBSDFWrapper, ShaderImageTextureWrapper

from .... import utility
from ....ui.shader_parser import get_shader_dict
from ....ui.shader_picker import SHADER_DEFAULT
from .properties import resolve_material_properties

if TYPE_CHECKING:
    from ...ctx import ExportContext
    from ...resources.materials import MaterialEntry


def resolve_material_entries(ctx: ExportContext) -> None:
    for entry in ctx.materials.entries():
        resolve_material_properties(ctx, entry)
        _resolve_material_shading(ctx, entry)


def _resolve_material_shading(ctx: ExportContext, entry: MaterialEntry) -> None:
    """Populate Material XML (textures/colors/custom shader) from Blender material data."""
    mat = entry.blender_material
    if mat is None or not isinstance(mat, bpy.types.Material):
        return
    i3d_attrs = mat.i3d_attributes
    shader_name = i3d_attrs.shader_name
    vehicle_shader = shader_name == "vehicleShader"

    principled = PrincipledBSDFWrapper(mat, is_readonly=True)
    bsdf: bpy.types.ShaderNodeBsdfPrincipled = principled.node_principled_bsdf

    def _set_color(xml_key: str, socket_name: str, fallback) -> None:
        sock = bsdf.inputs.get(socket_name) if bsdf else None
        col = _linked_rgb_color(sock) or fallback
        entry.attrs.node.setdefault(xml_key, list(col)[:3])

    def _set_tex(tag: str, path: str) -> dict:
        attrs = entry.attrs.child(tag)
        attrs.setdefault("fileId", ctx.files.add_image(path))
        return attrs

    skip_diffuse = False
    # Emission (wins over diffuse if present)
    if (p := _image_path(principled.emission_color_texture)) is not None:
        _set_tex("Emissivemap", p)
        skip_diffuse = True
    elif principled.emission_strength > 0:
        _set_color("emissiveColor", "Emission Color", principled.emission_color)
        skip_diffuse = True

    # Base/diffuse
    if not skip_diffuse:
        if (p := _image_path(principled.base_color_texture)) is not None:
            _set_tex("Texture", p)
        elif not vehicle_shader:
            _set_color("diffuseColor", "Base Color", principled.base_color)

    # Normalmap
    if (p := _image_path(principled.normalmap_texture)) is not None:
        attrs = _set_tex("Normalmap", p)
        strength = principled.normalmap_strength
        if not utility.isclose_value(strength, 1.0):
            attrs.setdefault("bumpDepth", strength)

    # Gloss/specular
    if (p := _find_glossmap_path(mat, principled)) is not None:
        _set_tex("Glossmap", p)
    elif not vehicle_shader:
        entry.attrs.node.setdefault(
            "specularColor", [1.0 - float(principled.roughness), float(principled.specular), float(principled.metallic)]
        )

    # vehicleShader defaults
    if vehicle_shader:
        defaults = {
            "Texture": "$data/shared/white_diffuse.dds",
            "Glossmap": "$data/shared/default_vmask.dds",
            "Normalmap": "$data/shared/default_normal.dds",
        }
        for tag, path in defaults.items():
            if tag not in entry.attrs.children:
                _set_tex(tag, path)

    # Custom shader + variation + params/textures (from Material.i3d_attributes)
    if shader_name and shader_name != SHADER_DEFAULT:
        if shader_data := get_shader_dict(i3d_attrs.use_custom_shaders).get(shader_name):
            shader_file_id = ctx.files.add_shader(str(shader_data.path))
            entry.attrs.node["customShaderId"] = shader_file_id

            if shader_name == "mirrorShader":
                entry.attrs.child("Reflectionmap").update({"type": "planar", "refractiveIndex": 10, "bumpScale": 0.1})

        if (variation := i3d_attrs.shader_variation_name) != SHADER_DEFAULT:
            entry.attrs.node["customShaderVariation"] = variation

        _emit_custom_parameters(entry, i3d_attrs.shader_material_params)
        _emit_custom_textures(ctx, entry, i3d_attrs.shader_material_textures)


def _emit_custom_parameters(entry: "MaterialEntry", params) -> None:
    for name, value in params.items():
        default_value = params.id_properties_ui(name).as_dict().get("default")
        if not utility.isclose_value(value, default_value):
            entry.extra_children.append(("CustomParameter", {"name": name, "value": value}))


def _emit_custom_textures(ctx: "ExportContext", entry: "MaterialEntry", textures) -> None:
    for tex in textures:
        if "" != tex.source != tex.default_source:
            entry.extra_children.append(("Custommap", {"name": tex.name, "fileId": ctx.files.add_image(tex.source)}))


def _find_glossmap_path(mat: bpy.types.Material, principled: PrincipledBSDFWrapper) -> str | None:
    # Prefer explicit node called "glossmap" (legacy workflow)
    glossnode = None
    if nt := mat.node_tree:
        name_l = "glossmap"
        glossnode = next((n for n in nt.nodes if n.name.lower() == name_l or n.label.lower() == name_l), None)
    if glossnode is not None:
        match glossnode.bl_idname:
            case "ShaderNodeTexImage":
                return _image_path(glossnode)
            case "ShaderNodeSeparateColor":
                socket = glossnode.inputs.get("Color")
                if socket and socket.is_linked:
                    from_node = socket.links[0].from_node
                    if from_node and from_node.bl_idname == "ShaderNodeTexImage":
                        return _image_path(from_node)

    return _image_path(principled.specular_texture)


def _linked_rgb_color(socket: bpy.types.NodeSocket | None) -> list[float] | None:
    if not socket or not getattr(socket, "is_linked", False):
        return None
    from_node = socket.links[0].from_node
    if from_node and from_node.bl_idname == "ShaderNodeRGB":
        return list(from_node.outputs["Color"].default_value)
    return None


def _image_path(tex: ShaderImageTextureWrapper | bpy.types.ShaderNodeTexImage | None) -> str | None:
    if not tex or not (img := tex.image):
        return None
    return img.filepath_from_user() or img.filepath or None
