from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import bpy

from .. import xml_i3d
from .. import __package__ as base_package


MATERIAL_TEMPLATES = {}
BRAND_MATERIAL_TEMPLATES = {}


@dataclass
class MaterialTemplate:
    # For "None", use shader defaults (or should we just ignore it?)
    # value = shader_settings.shader_material_params[pname]
    # default = shader_settings.shader_material_params.id_properties_ui(pname).as_dict().get('default')
    name: str
    category: str
    icon_path: Path
    detail_diffuse: str
    detail_normal: str
    detail_specular: str
    color_scale: tuple[float, float, float] | None = None
    clear_coat_intensity: float | None = None
    clear_coat_smoothness: float | None = None
    smoothness_scale: float | None = None
    metalness_scale: float | None = None
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
    parent_template: MaterialTemplate | None = None  # Not sure if using MaterialTemplate is correct?
    color_scale: tuple[float, float, float] | None = None
    clear_coat_intensity: float | None = None
    clear_coat_smoothness: float | None = None
    smoothness_scale: float | None = None
    metalness_scale: float | None = None
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
    selected_material_template: bpy.props.StringProperty(name="Material Template", update=None)
    selected_brand_template: bpy.props.StringProperty(name="Brand Template", update=None)
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
            icon_path=path.parent / tmpl.attrib.get("iconFilename", ""),
            detail_diffuse=tmpl.attrib.get("detailDiffuse", ""),
            detail_normal=tmpl.attrib.get("detailNormal", ""),
            detail_specular=tmpl.attrib.get("detailSpecular", ""),
            color_scale=color_scale,
            clear_coat_intensity=_float(tmpl.attrib.get("clearCoatIntensity")),
            clear_coat_smoothness=_float(tmpl.attrib.get("clearCoatSmoothness")),
            smoothness_scale=_float(tmpl.attrib.get("smoothnessScale")),
            metalness_scale=_float(tmpl.attrib.get("metalnessScale")),
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
            parent_template=all_material_templates.get(parent_template) if parent_template else None,
            color_scale=color_scale,
            clear_coat_intensity=_float(tmpl.attrib.get("clearCoatIntensity")),
            clear_coat_smoothness=_float(tmpl.attrib.get("clearCoatSmoothness")),
            smoothness_scale=_float(tmpl.attrib.get("smoothnessScale")),
            metalness_scale=_float(tmpl.attrib.get("metalnessScale")),
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
