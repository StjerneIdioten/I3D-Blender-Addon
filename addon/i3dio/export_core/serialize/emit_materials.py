from __future__ import annotations

from typing import TYPE_CHECKING

from ...xml_i3d import SubElementA
from .xml_attrs import write_attributes, write_child_elements

if TYPE_CHECKING:
    import xml.etree.ElementTree as ET

    from ..ctx import ExportContext


def emit_materials(ctx: ExportContext, materials_elem: ET.Element) -> None:
    for entry in ctx.materials.entries():
        mat_elem = SubElementA(materials_elem, "Material", {"name": entry.key.export_name, "materialId": entry.id})
        write_attributes(elem=mat_elem, attrs=entry.attrs.node)
        write_child_elements(parent_elem=mat_elem, emit_attrs=entry.attrs)

        for child_name, child_attrs in entry.extra_children:
            child_elem = SubElementA(mat_elem, child_name)
            write_attributes(child_elem, child_attrs)
