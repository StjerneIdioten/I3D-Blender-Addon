from __future__ import annotations
from dataclasses import dataclass, fields
from pathlib import Path
import bpy

from .. import xml_i3d
from .helper_functions import get_fs_data_path


MATERIAL_TEMPLATES: dict[str, MaterialTemplate] = {}
BRAND_MATERIAL_TEMPLATES: dict[str, BrandMaterialTemplate] = {}


def get_template(name: str, brand: bool = False) -> MaterialTemplate | BrandMaterialTemplate | None:
    """Get a material or brand material template by name."""
    return (BRAND_MATERIAL_TEMPLATES if brand else MATERIAL_TEMPLATES).get(name)


def template_to_material(
    params,
    textures,
    template,
    allowed_params={"colorScale", "clearCoatIntensity", "clearCoatSmoothness",
                    "smoothnessScale", "metalnessScale", "porosity"},
    allowed_textures={"detailDiffuse", "detailNormal", "detailSpecular"}
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
                params[prop_name] = params.id_properties_ui(prop_name).as_dict().get('default')
            else:
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
class I3D_IO_OT_template_search_popup(bpy.types.Operator):
    bl_idname = "i3dio.template_search_popup"
    bl_label = "Select Template"
    bl_description = "Search and apply material templates"
    bl_options = {'INTERNAL', 'UNDO'}
    bl_property = "template_name"

    @classmethod
    def poll(cls, context):
        return context.material

    def enum_items(self, context):
        global MATERIAL_TEMPLATES, BRAND_MATERIAL_TEMPLATES
        templates = (BRAND_MATERIAL_TEMPLATES if self.is_brand else MATERIAL_TEMPLATES).values()
        return [(item.name, item.name, "") for item in templates]

    template_name: bpy.props.EnumProperty(items=enum_items)
    is_brand: bpy.props.BoolProperty(default=False, options={'HIDDEN'})
    single_param: bpy.props.StringProperty(default="", options={'HIDDEN'})  # Used inline with single params in UI

    def execute(self, context):
        if not (template := get_template(self.template_name, self.is_brand)):
            self.report({'ERROR'}, f"Template '{self.template_name}' not found.")
            return {'CANCELLED'}
        params = context.material.i3d_attributes.shader_material_params
        textures = context.material.i3d_attributes.shader_material_textures

        if self.single_param:  # Updating single param only, no need for parent inheritance
            template_to_material(params, textures, template, allowed_params={self.single_param}, allowed_textures=[])
        else:
            if (parent := getattr(template, 'parentTemplate', None)) is not None:
                template_to_material(params, textures, parent)
            template_to_material(params, textures, template)

        if context.area:
            context.area.tag_redraw()

        self.report({'INFO'}, f"Set {'brand' if self.is_brand else 'material'} template to: {self.template_name}")
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'FINISHED'}


def _float(val):
    try:
        return float(val) if val is not None else None
    except Exception:
        return None


def _parse_template_common(tmpl) -> dict:
    return dict(
        name=tmpl.attrib["name"],
        colorScale=tuple(map(float, tmpl.attrib['colorScale'].split())) if 'colorScale' in tmpl.attrib else None,
        clearCoatIntensity=_float(tmpl.attrib.get("clearCoatIntensity")),
        clearCoatSmoothness=_float(tmpl.attrib.get("clearCoatSmoothness")),
        smoothnessScale=_float(tmpl.attrib.get("smoothnessScale")),
        metalnessScale=_float(tmpl.attrib.get("metalnessScale")),
        porosity=_float(tmpl.attrib.get("porosity")),
    )


def parse_material_templates(path: Path) -> dict[str, MaterialTemplate]:
    tree = xml_i3d.parse(path)
    root = tree.getroot()
    templates = {}
    for tmpl in root.findall("template"):
        args = _parse_template_common(tmpl)
        args.update(
            category=tmpl.attrib.get("category", ""),
            iconPath=path.parent / tmpl.attrib.get("iconFilename", ""),
            detailDiffuse=tmpl.attrib.get("detailDiffuse", ""),
            detailNormal=tmpl.attrib.get("detailNormal", ""),
            detailSpecular=tmpl.attrib.get("detailSpecular", ""),
        )
        templates[args["name"]] = MaterialTemplate(**args)
    return templates


def parse_brand_material_templates(
        path: Path, all_material_templates: dict[str, MaterialTemplate]) -> dict[str, BrandMaterialTemplate]:
    tree = xml_i3d.parse(path)
    root = tree.getroot()
    templates = {}
    for tmpl in root.findall("template"):
        args = _parse_template_common(tmpl)
        parent_template = tmpl.attrib.get('parentTemplate')
        args.update(
            brand=tmpl.attrib.get("brand"),
            usage=int(tmpl.attrib.get("usage", "0")),
            description=tmpl.attrib.get("description"),
            parentTemplate=all_material_templates.get(parent_template) if parent_template else None,
        )
        templates[args["name"]] = BrandMaterialTemplate(**args)
    return templates


@bpy.app.handlers.persistent
def parse_templates(_dummy) -> None:
    if not (data_path := get_fs_data_path(as_path=True)):
        return
    material_tmpl_path = data_path / 'shared' / 'detailLibrary' / 'materialTemplates.xml'
    brand_tmpl_path = data_path / 'shared' / 'brandMaterialTemplates.xml'
    if not material_tmpl_path.exists() or not brand_tmpl_path.exists():
        return
    global MATERIAL_TEMPLATES, BRAND_MATERIAL_TEMPLATES
    MATERIAL_TEMPLATES = parse_material_templates(material_tmpl_path)
    BRAND_MATERIAL_TEMPLATES = parse_brand_material_templates(brand_tmpl_path, MATERIAL_TEMPLATES)


_register, _unregister = bpy.utils.register_classes_factory(classes)


def register():
    _register()
    bpy.app.handlers.load_post.append(parse_templates)


def unregister():
    _unregister()
    bpy.app.handlers.load_post.remove(parse_templates)
