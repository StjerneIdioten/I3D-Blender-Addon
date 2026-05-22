from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from ... import xml_i3d

if TYPE_CHECKING:
    import xml.etree.ElementTree as ET

    from ..ir import EmitAttrs, SceneNode


def write_attributes(elem: ET.Element, attrs: Mapping[str, object]) -> None:
    """Write a mapping of attributes using xml_i3d's canonical value formatting."""
    for k, v in attrs.items():
        xml_i3d.write_attribute(elem, k, v)


def write_node_attributes(elem: ET.Element, node: SceneNode) -> None:
    """Write all node attributes including shapeId, materialIds, skinBindNodeIds, and reference data."""
    write_attributes(elem=elem, attrs=node.attrs.node)

    # Shape attributes
    if (shape := node._shape) is not None:
        xml_i3d.write_attribute(elem, "shapeId", shape.shape_id)

        if shape.material_ids:
            xml_i3d.write_attribute(elem, "materialIds", ",".join(str(mid) for mid in shape.material_ids))

        if shape.skin_bind_node_ids:
            xml_i3d.write_attribute(
                elem,
                "skinBindNodeIds",
                " ".join(str(nid) for nid in shape.skin_bind_node_ids),
            )

    # Reference attributes
    if (ref := node._ref) is not None:
        xml_i3d.write_attribute(elem, "referenceId", ref.reference_id)

        if ref.child_path:
            xml_i3d.write_attribute(elem, "referenceChildPath", ref.child_path)

        if ref.runtime_loaded is False:
            xml_i3d.write_attribute(elem, "referenceRuntimeLoaded", False)


def write_child_elements(parent_elem: ET.Element, emit_attrs: EmitAttrs) -> None:
    """Create child elements from EmitAttrs.children and write their attributes."""
    for child_name, child_attrs in emit_attrs.children.items():
        child_elem = xml_i3d.SubElementA(parent_elem, child_name)
        write_attributes(elem=child_elem, attrs=child_attrs)
