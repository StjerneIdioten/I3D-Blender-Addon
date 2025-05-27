from __future__ import annotations
from dataclasses import dataclass, fields
from pathlib import Path
import bpy

from .. import xml_i3d
from .. import __package__ as base_package


MATERIAL_TEMPLATES: dict[str, MaterialTemplate] = {}
BRAND_MATERIAL_TEMPLATES: dict[str, BrandMaterialTemplate] = {}


def get_material_template(name: str) -> MaterialTemplate | None:
    """Get a material template by name."""
    return MATERIAL_TEMPLATES.get(name)


def get_brand_material_template(name: str) -> BrandMaterialTemplate | None:
    """Get a brand material template by name."""
    return BRAND_MATERIAL_TEMPLATES.get(name)


def material_template_to_material(
    params,
    textures,
    template,
    allowed_params={"colorScale", "clearCoatIntensity", "clearCoatSmoothness",
                    "smoothnessScale", "metalnessScale", "porosity"},
    allowed_textures={"detailDiffuse", "detailNormal", "detailSpecular"},
    skip_if_already_set=False
) -> None:
    """
    Apply parameters/textures from a MaterialTemplate or BrandMaterialTemplate to the given params/textures.
    If `skip_if_already_set` is True, only assign if not set.
    """
    for f in fields(template):
        prop_name = f.name
        value = getattr(template, prop_name)
        if prop_name in allowed_params:
            if value is None:
                if not (skip_if_already_set and params.get(prop_name) is not None):
                    params[prop_name] = params.id_properties_ui(prop_name).as_dict().get('default')
            else:
                if not (skip_if_already_set and params.get(prop_name) is not None):
                    params[prop_name] = list(value) if isinstance(value, (tuple, list)) else [value]
        elif prop_name in allowed_textures:
            tex = next((t for t in textures if t.name == prop_name), None)
            if tex is not None:
                tex.source = value if value else tex.default_source


@dataclass
class MaterialTemplate:
    # For "None", use shader defaults (or should we just ignore it?)
    # value = shader_settings.shader_material_params[pname]
    # default = shader_settings.shader_material_params.id_properties_ui(pname).as_dict().get('default')
    name: str
    category: str
    iconPath: Path
    detailDiffuse: str
    detailNormal: str
    detailSpecular: str
    colorScale: tuple[float, float, float] | None = None
    clearCoatIntensity: float | None = None
    clearCoatSmoothness: float | None = None
    smoothnessScale: float | None = None
    metalnessScale: float | None = None
    porosity: float | None = None


@dataclass
class BrandMaterialTemplate:
    # For "None", use shader defaults (or should we just ignore it?)
    # value = shader_settings.shader_material_params[pname]
    # default = shader_settings.shader_material_params.id_properties_ui(pname).as_dict().get('default')
    name: str
    usage: int  # not sure what this is for
    brand: str | None = None
    description: str | None = None
    parentTemplate: MaterialTemplate | None = None  # Not sure if using MaterialTemplate is correct?
    colorScale: tuple[float, float, float] | None = None
    clearCoatIntensity: float | None = None
    clearCoatSmoothness: float | None = None
    smoothnessScale: float | None = None
    metalnessScale: float | None = None
    porosity: float | None = None


classes = []


def register(cls):
    classes.append(cls)
    return cls


@register
class BrandTemplateItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()
    brand: bpy.props.StringProperty()
    description: bpy.props.StringProperty()


@register
class MaterialTemplateItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()
    category: bpy.props.StringProperty()


@register
class I3DMaterialTemplates(bpy.types.PropertyGroup):
    material_templates: bpy.props.CollectionProperty(type=MaterialTemplateItem)
    brand_templates: bpy.props.CollectionProperty(type=BrandTemplateItem)


@register
class I3D_IO_OT_refresh_material_templates(bpy.types.Operator):
    bl_idname = "i3dio.refresh_material_templates"
    bl_label = "Refresh Material Templates"
    bl_description = "Reload material templates from the data path"

    def execute(self, _context):
        parse_templates(None)
        return {'FINISHED'}


def _float(val):
    try:
        return float(val) if val is not None else None
    except Exception:
        return None


def parse_material_templates(path: Path) -> dict[str, MaterialTemplate]:
    tree = xml_i3d.parse(path)
    root = tree.getroot()
    templates = {}
    for tmpl in root.findall("template"):
        color_scale = None
        if 'colorScale' in tmpl.attrib:
            color_scale = tuple(map(float, tmpl.attrib['colorScale'].split()))
        templates[tmpl.attrib["name"]] = MaterialTemplate(
            name=tmpl.attrib["name"],
            category=tmpl.attrib.get("category", ""),
            iconPath=path.parent / tmpl.attrib.get("iconFilename", ""),
            detailDiffuse=tmpl.attrib.get("detailDiffuse", ""),
            detailNormal=tmpl.attrib.get("detailNormal", ""),
            detailSpecular=tmpl.attrib.get("detailSpecular", ""),
            colorScale=color_scale,
            clearCoatIntensity=_float(tmpl.attrib.get("clearCoatIntensity")),
            clearCoatSmoothness=_float(tmpl.attrib.get("clearCoatSmoothness")),
            smoothnessScale=_float(tmpl.attrib.get("smoothnessScale")),
            metalnessScale=_float(tmpl.attrib.get("metalnessScale")),
            porosity=_float(tmpl.attrib.get("porosity")),
        )
    return templates


def parse_brand_material_templates(
        path: Path, all_material_templates: dict[str, MaterialTemplate]) -> dict[str, BrandMaterialTemplate]:
    tree = xml_i3d.parse(path)
    root = tree.getroot()
    templates = {}
    for tmpl in root.findall("template"):
        color_scale = None
        if 'colorScale' in tmpl.attrib:
            color_scale = tuple(map(float, tmpl.attrib['colorScale'].split()))
        parent_template = tmpl.attrib.get('parentTemplate')
        templates[tmpl.attrib["name"]] = BrandMaterialTemplate(
            name=tmpl.attrib["name"],
            brand=tmpl.attrib.get("brand"),
            usage=int(tmpl.attrib.get("usage", "0")),
            description=tmpl.attrib.get("description"),
            parentTemplate=all_material_templates.get(parent_template) if parent_template else None,
            colorScale=color_scale,
            clearCoatIntensity=_float(tmpl.attrib.get("clearCoatIntensity")),
            clearCoatSmoothness=_float(tmpl.attrib.get("clearCoatSmoothness")),
            smoothnessScale=_float(tmpl.attrib.get("smoothnessScale")),
            metalnessScale=_float(tmpl.attrib.get("metalnessScale")),
            porosity=_float(tmpl.attrib.get("porosity")),
        )
    return templates


@bpy.app.handlers.persistent
def parse_templates(_dummy) -> None:
    data_path = bpy.context.preferences.addons[base_package].preferences.fs_data_path
    if not data_path:
        return
    material_tmpl_path = Path(data_path) / 'shared' / 'detailLibrary' / 'materialTemplates.xml'
    brand_tmpl_path = Path(data_path) / 'shared' / 'brandMaterialTemplates.xml'
    if not material_tmpl_path.exists() or not brand_tmpl_path.exists():
        return
    global MATERIAL_TEMPLATES, BRAND_MATERIAL_TEMPLATES
    MATERIAL_TEMPLATES = parse_material_templates(material_tmpl_path)
    BRAND_MATERIAL_TEMPLATES = parse_brand_material_templates(brand_tmpl_path, MATERIAL_TEMPLATES)

    for name, template in MATERIAL_TEMPLATES.items():
        item = bpy.context.scene.i3dio_material_templates.material_templates.add()
        item.name = name
        item.category = template.category
    for name, template in BRAND_MATERIAL_TEMPLATES.items():
        item = bpy.context.scene.i3dio_material_templates.brand_templates.add()
        item.name = name
        item.brand = template.brand if template.brand else ""
        item.description = template.description if template.description else ""


_register, _unregister = bpy.utils.register_classes_factory(classes)


def register():
    _register()
    bpy.types.Scene.i3dio_material_templates = bpy.props.PointerProperty(type=I3DMaterialTemplates)
    bpy.app.handlers.load_post.append(parse_templates)


def unregister():
    _unregister()
    del bpy.types.Scene.i3dio_material_templates
    bpy.app.handlers.load_post.remove(parse_templates)
