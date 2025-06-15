from __future__ import annotations
from dataclasses import dataclass, fields, field
from pathlib import Path
import bpy

from .. import xml_i3d
from ..utility import get_fs_data_path
from .helper_functions import humanize_template

TEMPLATES_GROUP_NAMES: dict[str, str] = {}  # template_id -> friendly name
MATERIAL_TEMPLATES: dict[str, MaterialTemplate] = {}
BRAND_MATERIAL_TEMPLATES: dict[str, BrandMaterialTemplate] = {}
preview_collections = {}


@dataclass
class TemplateBase:
    """Base class for shared material template attributes defined in XML files."""
    name: str = "UnknownTemplate"
    colorScale: tuple[float, float, float] = (1.0, 1.0, 1.0)
    clearCoatIntensity: float = 0.0
    clearCoatSmoothness: float = 0.0
    smoothnessScale: float = 1.0
    metalnessScale: float = 1.0
    porosity: float = 0.0

    def _initialize_from_elem(self, elem: xml_i3d.XML_Element):
        """Overwrites instance attributes with values explicitly defined in the provided XML element's attributes."""
        type_converters = {
            "colorScale": lambda v: tuple(float(c) for c in v.split()),
            "clearCoatIntensity": float,
            "clearCoatSmoothness": float,
            "smoothnessScale": float,
            "metalnessScale": float,
            "porosity": float
        }
        for attr_name, attr_value in elem.attrib.items():
            if attr_name in type_converters:
                setattr(self, attr_name, type_converters[attr_name](attr_value))
            elif attr_name == "name":
                setattr(self, attr_name, attr_value)


@dataclass
class MaterialTemplate(TemplateBase):
    category: str = "default"
    detailDiffuse: str = "$data/shared/detailLibrary/nonMetallic/default_diffuse.dds"
    detailNormal: str = "$data/shared/detailLibrary/nonMetallic/default_normal.dds"
    detailSpecular: str = "$data/shared/detailLibrary/nonMetallic/default_specular.dds"

    @classmethod
    def from_elem(cls, elem: xml_i3d.XML_Element) -> MaterialTemplate:
        """Create a MaterialTemplate instance from an XML element."""
        instance = cls()
        instance._initialize_from_elem(elem)
        instance.category = elem.attrib.get("category", cls.category)
        for field_name in ("detailDiffuse", "detailNormal", "detailSpecular"):
            if field_name in elem.attrib:
                setattr(instance, field_name, elem.attrib[field_name])
        return instance


@dataclass
class BrandMaterialTemplate(MaterialTemplate):
    usage: int = 0  # NOTE: useful for blender?
    brand: str = ""
    description: str = ""
    parentTemplate: str = ""
    declared_fields: set[str] = field(default_factory=set, repr=False)

    @classmethod
    def from_elem(cls, elem: xml_i3d.XML_Element, default_parent: str) -> BrandMaterialTemplate:
        """Create a BrandMaterialTemplate instance from an XML element."""
        parent_template_name = elem.attrib.get("parentTemplate", default_parent)
        parent_template = get_template_by_name(parent_template_name)
        parent_props = {f.name: getattr(parent_template, f.name) for f in fields(MaterialTemplate)}
        instance = cls(**parent_props)
        instance._initialize_from_elem(elem)
        instance.usage = int(elem.attrib.get("usage", 0))
        instance.brand = elem.attrib.get("brand", "")
        instance.description = elem.attrib.get("description", "")
        instance.parentTemplate = parent_template_name
        # Track which fields were actually declared in the XML element
        instance.declared_fields = set(elem.attrib)
        return instance


def _parse_material_templates(path: Path) -> dict[str, MaterialTemplate]:
    tree = xml_i3d.parse(path)
    root = tree.getroot()
    template_id = root.attrib.get("id")
    template_name = root.attrib.get("name")
    if template_id and template_name:
        TEMPLATES_GROUP_NAMES[template_id] = template_name
    templates = {}
    for tmpl in root.findall("template"):
        if name := tmpl.attrib.get("name"):
            templates[name] = MaterialTemplate.from_elem(tmpl)
    return templates


def _parse_brand_material_templates(path: Path) -> dict[str, BrandMaterialTemplate]:
    tree = xml_i3d.parse(path)
    root = tree.getroot()
    template_id = root.attrib.get("id")
    template_name = root.attrib.get("name")
    if template_id and template_name:
        TEMPLATES_GROUP_NAMES[template_id] = template_name
    default_parent = root.attrib.get("parentTemplateDefault", "calibratedPaint")
    templates = {}
    for tmpl in root.findall("template"):
        if name := tmpl.attrib.get("name"):  # Just to be safe
            if (new_template := BrandMaterialTemplate.from_elem(tmpl, default_parent)):
                templates[name] = new_template
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
    MATERIAL_TEMPLATES = _parse_material_templates(material_tmpl_path)
    BRAND_MATERIAL_TEMPLATES = _parse_brand_material_templates(brand_tmpl_path)

    if 'material_templates' in preview_collections:
        bpy.utils.previews.remove(preview_collections['material_templates'])
        del preview_collections['material_templates']
    pcoll = bpy.utils.previews.new()
    template_icons_dir = data_path / 'shared' / 'detailLibrary' / 'icons'
    for icon_path in sorted(template_icons_dir.glob("*.png")):
        pcoll.load(icon_path.stem, str(icon_path), 'IMAGE')
    preview_collections['material_templates'] = pcoll


def brand_name_from_color(color: tuple[float, float, float]) -> str | None:
    """Get the brand material name based on the color scale."""
    rounded_color = tuple(round(c, 4) for c in color)  # Round to 4 decimal places for comparison
    for template in BRAND_MATERIAL_TEMPLATES.values():
        if template.colorScale and tuple(template.colorScale) == rounded_color:
            return template.name
    return None


def get_template_by_name(name: str) -> MaterialTemplate | BrandMaterialTemplate | None:
    """Get a material or brand material template by name."""
    return MATERIAL_TEMPLATES.get(name) or BRAND_MATERIAL_TEMPLATES.get(name)


def apply_template_to_material(params, textures, template,
                               allowed_params=None, allowed_textures=None, overlay_only_declared=False) -> None:
    """Applies params and textures from a template to the given material property collections."""
    if allowed_params is None:
        allowed_params = {"colorScale", "clearCoatIntensity", "clearCoatSmoothness",
                          "smoothnessScale", "metalnessScale", "porosity"}
    if allowed_textures is None:
        allowed_textures = {"detailDiffuse", "detailNormal", "detailSpecular"}

    declared_fields = getattr(template, 'declared_fields', None) if overlay_only_declared else None

    for f in fields(template):
        prop_name = f.name
        if prop_name not in allowed_params and prop_name not in allowed_textures:
            continue
        if overlay_only_declared and declared_fields is not None and prop_name not in declared_fields:
            continue  # Skip non-explicit fields if overlay mode
        if (value := getattr(template, prop_name, None)) is None:
            continue
        if prop_name in allowed_params:
            params[prop_name] = list(value) if isinstance(value, (tuple, list)) else [value]
        elif prop_name in allowed_textures:
            tex = next((t for t in textures if t.name == prop_name), None)
            if tex is not None and value and value != tex.default_source:
                tex.source = value


classes = []


def register(cls):
    classes.append(cls)
    return cls


def group_templates_by_category(templates: list[MaterialTemplate]) -> dict[str, dict[str, list[MaterialTemplate]]]:
    """Return nested dict: {main_cat: {subcat: [templates]}}"""
    grouped = {}
    for tmpl in templates:
        cats = tmpl.category.split('/') if tmpl.category else ["Uncategorized"]
        main, *subs = cats
        d = grouped.setdefault(main, {})
        subcat = '/'.join(subs) if subs else None
        d.setdefault(subcat, []).append(tmpl)
    return grouped


@register
class I3D_IO_OT_create_material_from_template_popup(bpy.types.Operator):
    bl_idname = "i3dio.create_material_from_template_popup"
    bl_label = "Create Material from Template"
    bl_description = "Create a new material based on a template"
    bl_options = {'INTERNAL', 'UNDO'}

    assignment_mode: bpy.props.EnumProperty(
        name="Assignment Mode",
        description="How to assign the created material",
        items=[
            ('SLOT', "Material Slot", "Add to new material slot"),
            ('ACTIVE_OBJECT', "Active Object", "Assign to the active object"),
            ('SELECTED_OBJECTS', "Selected Objects", "Assign to all selected objects"),
            ('SELECTED_MESHES', "Selected Meshes", "Assign material to all selected triangles in selected meshes")
        ],
        default='SLOT'
    )

    def draw(self, _context):
        layout = self.layout
        box = layout.box()
        box.label(text="Choose how the material will be assigned to objects:")
        box.row().prop(self, "assignment_mode", expand=True)

        grouped = group_templates_by_category(MATERIAL_TEMPLATES.values())
        for main_cat, subdict in grouped.items():
            header, main_panel = layout.panel(f"cat_{main_cat}", default_closed=False)
            header.label(text=humanize_template(main_cat), icon='FILE_FOLDER')
            if not main_panel:
                continue
            for subcat, templates in sorted(subdict.items()):
                if subcat:
                    subheader, subpanel = main_panel.panel(f"subcat_{main_cat}_{subcat}", default_closed=True)
                    subheader.label(text=f"{humanize_template(subcat)}", icon='DOT')
                    if not subpanel:
                        continue
                    target_layout = subpanel
                else:
                    target_layout = main_panel

                grid = target_layout.grid_flow(row_major=True, columns=5, even_columns=True, even_rows=True)
                for template in sorted(templates, key=lambda t: t.name.lower()):
                    cell = grid.column().box()
                    icon_id = preview_collections['material_templates'].get(template.name).icon_id
                    cell.template_icon(icon_id, scale=8.0)
                    op = cell.operator("i3dio.create_material_from_template", text=humanize_template(template.name))
                    op.template_name = template.name
                    op.assignment_mode = self.assignment_mode
        layout.row(align=True).template_popup_confirm("", text="", cancel_text="Close")

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context: bpy.types.Context, _event):
        return context.window_manager.invoke_props_dialog(self, width=800)


@register
class I3D_IO_OT_create_material_from_template(bpy.types.Operator):
    bl_idname = "i3dio.create_material_from_template"
    bl_label = "Create Material from Template"
    bl_description = "Create a new material based on a template"
    bl_options = {'INTERNAL', 'UNDO'}

    template_name: bpy.props.StringProperty(default="plasticPaintedShinyBlack", options={'HIDDEN'})
    assignment_mode: bpy.props.EnumProperty(
        name="Assignment Mode",
        description="How to assign the created material",
        items=[
            ('SLOT', "Material Slot", "Add to new material slot"),
            ('ACTIVE_OBJECT', "Active Object", "Assign to the active object"),
            ('SELECTED_OBJECTS', "Selected Objects", "Assign to all selected objects"),
            ('SELECTED_MESHES', "Selected Meshes", "Assign material to all selected triangles in selected meshes")
        ],
        default='SLOT'
    )

    def execute(self, context):
        if not (template := get_template_by_name(self.template_name)):
            self.report({'ERROR'}, f"Template '{self.template_name}' not found.")
            return {'CANCELLED'}
        mat_name = f"{template.name}_mat"
        new_material = bpy.data.materials.get(mat_name)
        if not new_material:
            new_material = bpy.data.materials.new(name=mat_name)
            new_material.use_nodes = True
            i3d_attrs = new_material.i3d_attributes
            i3d_attrs.shader_name = 'vehicleShader'
            apply_template_to_material(i3d_attrs.shader_material_params, i3d_attrs.shader_material_textures, template)

        match self.assignment_mode:
            case 'SLOT':
                obj = context.active_object
                if obj and new_material.name not in [mat.name for mat in obj.data.materials]:
                    obj.data.materials.append(new_material)
            case 'ACTIVE_OBJECT':
                obj = context.active_object
                if obj:
                    obj.data.materials.clear()
                    obj.data.materials.append(new_material)
            case 'SELECTED_OBJECTS':
                for obj in context.selected_objects:
                    if obj.type == 'MESH':
                        obj.data.materials.clear()
                        obj.data.materials.append(new_material)
            case 'SELECTED_MESHES':
                original_mode = None
                active_object = context.view_layer.objects.active
                if active_object and active_object.mode != 'OBJECT' and bpy.ops.object.mode_set.poll():
                    original_mode = active_object.mode
                    bpy.ops.object.mode_set(mode='OBJECT')

                selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
                if not selected_meshes:
                    self.report({'ERROR'}, "No selected mesh objects found.")
                    return {'CANCELLED'}
                for obj in selected_meshes:
                    # Ensure the material is present
                    if new_material.name not in [mat.name for mat in obj.data.materials]:
                        obj.data.materials.append(new_material)
                    mat_index = obj.data.materials.find(new_material.name)
                    for poly in obj.data.polygons:
                        if poly.select:
                            poly.material_index = mat_index

                if active_object and original_mode:
                    if bpy.ops.object.mode_set.poll():
                        bpy.ops.object.mode_set(mode=original_mode)

        self.report({'INFO'}, f"Created material from template: {template.name}")
        return {'FINISHED'}


@register
class I3D_IO_OT_template_search_popup(bpy.types.Operator):
    bl_idname = "i3dio.template_search_popup"
    bl_label = "Select Template"
    bl_description = ("Search and apply material templates.\n"
                      "• Hold Shift: Skip color scale\n"
                      "• Hold Ctrl: Only apply color scale\n")
    bl_options = {'INTERNAL', 'UNDO'}
    bl_property = "template_name"

    @classmethod
    def description(cls, _context, properties):
        if properties.single_param:
            return f"Set single parameter: {properties.single_param}"
        return ("Search and apply material templates.\n"
                "• Hold Shift: Skip color scale\n"
                "• Hold Ctrl: Only apply color scale\n")

    @classmethod
    def poll(cls, context):
        return context.material

    def enum_items(self, _context):
        templates = (BRAND_MATERIAL_TEMPLATES if self.is_brand else MATERIAL_TEMPLATES).values()
        return [(item.name, item.name, "") for item in templates]

    template_name: bpy.props.EnumProperty(items=enum_items)
    is_brand: bpy.props.BoolProperty(default=False, options={'HIDDEN'})
    single_param: bpy.props.StringProperty(default="", options={'HIDDEN'})  # Used inline with single params in UI
    skip_color_scale: bpy.props.BoolProperty(default=False, options={'HIDDEN'})
    only_color_scale: bpy.props.BoolProperty(default=False, options={'HIDDEN'})

    def execute(self, context):
        allowed_params = {"colorScale", "clearCoatIntensity", "clearCoatSmoothness",
                          "smoothnessScale", "metalnessScale", "porosity"}
        allowed_textures = {"detailDiffuse", "detailNormal", "detailSpecular"}
        info_parts = []

        if self.skip_color_scale:
            allowed_params.discard("colorScale")
            info_parts.append("skipped colorScale")
        if self.only_color_scale:
            allowed_params = {"colorScale"}
            allowed_textures = set()
            info_parts.append("only applied colorScale")

        if not (template := get_template_by_name(self.template_name)):
            self.report({'ERROR'}, f"Template '{self.template_name}' not found.")
            return {'CANCELLED'}
        params = context.material.i3d_attributes.shader_material_params
        textures = context.material.i3d_attributes.shader_material_textures

        if self.single_param:  # Updating single param only, no need for parent inheritance
            apply_template_to_material(params, textures, template,
                                       allowed_params={self.single_param}, allowed_textures=[])
            info_parts.append(f"Only set param: {self.single_param}")
        else:
            if (parent := getattr(template, 'parentTemplate', None)) is not None:
                info_parts.append(f"Applied parent template: {parent}")
            apply_template_to_material(params, textures, template, allowed_params, allowed_textures)

        if context.area:
            context.area.tag_redraw()

        info_str = " | ".join(info_parts)
        msg = f"Set {'brand' if self.is_brand else 'material'} template: {self.template_name}"
        if info_str:
            msg = f"{msg} [{info_str}]"
        self.report({'INFO'}, msg)
        return {'FINISHED'}

    def invoke(self, context, event):
        if not self.single_param:
            self.skip_color_scale = event.shift and not event.ctrl  # If shift is pressed, skip colorScale
            self.only_color_scale = event.ctrl and not event.shift  # If ctrl is pressed, only colorScale
        context.window_manager.invoke_search_popup(self)
        return {'FINISHED'}


_register, _unregister = bpy.utils.register_classes_factory(classes)


def register():
    _register()
    bpy.app.handlers.load_post.append(parse_templates)


def unregister():
    _unregister()
    bpy.app.handlers.load_post.remove(parse_templates)
    for pcoll in preview_collections.values():
        bpy.utils.previews.remove(pcoll)
    preview_collections.clear()
