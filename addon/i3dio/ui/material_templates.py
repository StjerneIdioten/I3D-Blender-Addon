from __future__ import annotations
from dataclasses import dataclass, fields
from pathlib import Path
import bpy

from .. import xml_i3d
from .helper_functions import get_fs_data_path, humanize_template


MATERIAL_TEMPLATES: dict[str, MaterialTemplate] = {}
BRAND_MATERIAL_TEMPLATES: dict[str, BrandMaterialTemplate] = {}

preview_collections = {}


def get_template(name: str, brand: bool = False) -> MaterialTemplate | BrandMaterialTemplate | None:
    """Get a material or brand material template by name."""
    return (BRAND_MATERIAL_TEMPLATES if brand else MATERIAL_TEMPLATES).get(name)


def template_to_material(params, textures, template, allowed_params=None, allowed_textures=None) -> None:
    """
    Apply parameters/textures from a MaterialTemplate or BrandMaterialTemplate to the given params/textures.
    If `skip_if_already_set` is True, only assign if not set.
    """
    if allowed_params is None:
        allowed_params = {"colorScale", "clearCoatIntensity", "clearCoatSmoothness",
                          "smoothnessScale", "metalnessScale", "porosity"}
    if allowed_textures is None:
        allowed_textures = {"detailDiffuse", "detailNormal", "detailSpecular"}
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
    name: str
    usage: int  # NOTE: not sure what this is for
    brand: str | None = None
    description: str | None = None
    parentTemplate: MaterialTemplate | None = None
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
                    icon_id = preview_collections['material_templates'].get(template.iconPath.stem).icon_id
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
        if not (template := get_template(self.template_name)):
            self.report({'ERROR'}, f"Template '{self.template_name}' not found.")
            return {'CANCELLED'}
        mat_name = f"{template.name}_mat"
        new_material = bpy.data.materials.get(mat_name)
        if not new_material:
            new_material = bpy.data.materials.new(name=mat_name)
            new_material.use_nodes = True
            i3d_attrs = new_material.i3d_attributes
            i3d_attrs.shader = 'vehicleShader'
            params = i3d_attrs.shader_material_params
            textures = i3d_attrs.shader_material_textures
            template_to_material(params, textures, template)

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

        if not (template := get_template(self.template_name, self.is_brand)):
            self.report({'ERROR'}, f"Template '{self.template_name}' not found.")
            return {'CANCELLED'}
        params = context.material.i3d_attributes.shader_material_params
        textures = context.material.i3d_attributes.shader_material_textures

        if self.single_param:  # Updating single param only, no need for parent inheritance
            template_to_material(params, textures, template, allowed_params={self.single_param}, allowed_textures=[])
            info_parts.append(f"Only set param: {self.single_param}")
        else:
            if (parent := getattr(template, 'parentTemplate', None)) is not None:
                template_to_material(params, textures, parent, allowed_params, allowed_textures)
                info_parts.append(f"Applied parent template: {parent.name}")
            template_to_material(params, textures, template, allowed_params, allowed_textures)

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


def _parse_template_common(tmpl) -> dict[str, float | tuple[float, float, float] | str]:
    result = {"name": tmpl.attrib["name"]}
    for key, value in tmpl.attrib.items():
        match key:
            case "colorScale":
                result[key] = tuple(map(float, value.split()))
            case "clearCoatIntensity" | "clearCoatSmoothness" | "smoothnessScale" | "metalnessScale" | "porosity":
                result[key] = float(value) if value is not None else None
    return result


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


def generate_template_previews():
    """Generate previews for all material templates."""
    if not (data_path := get_fs_data_path(as_path=True)):
        return
    pcoll = bpy.utils.previews.new()
    template_icons_dir = data_path / 'shared' / 'detailLibrary' / 'icons'
    for icon_path in sorted(template_icons_dir.glob("*.png")):
        pcoll.load(icon_path.stem, str(icon_path), 'IMAGE')
    preview_collections['material_templates'] = pcoll


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
    generate_template_previews()


def unregister():
    _unregister()
    bpy.app.handlers.load_post.remove(parse_templates)
    for pcoll in preview_collections.values():
        bpy.utils.previews.remove(pcoll)
    preview_collections.clear()
