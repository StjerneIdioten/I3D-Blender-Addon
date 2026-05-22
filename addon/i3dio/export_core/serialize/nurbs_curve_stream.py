from __future__ import annotations

from typing import TYPE_CHECKING

from ... import xml_i3d

if TYPE_CHECKING:
    from ..geometry.mesh.its import BuiltNurbsCurve


def write_nurbs_curve_stream(f, built: BuiltNurbsCurve, indent: str = "    ") -> None:
    """Write a NurbsCurve element to the I3D file."""
    write_open = xml_i3d.write_open_tag
    write_close = xml_i3d.write_close_tag
    write = f.write

    ind_tag = indent
    ind_cv = indent + "  "

    # Build NurbsCurve attributes
    nc_attrs: dict[str, object] = {
        "name": built.name,
        "shapeId": built.shape_id,
        "type": built.curve_type,
        "degree": built.degree,
        "form": "closed" if built.is_cyclic else "open",
    }
    # Merge any additional attrs from the shape entry
    nc_attrs.update(built.attrs.node)

    write_open(f, "NurbsCurve", nc_attrs, indent=ind_tag)

    # Write control vertices
    for i in range(built.point_count):
        p = built.control_positions[i]
        write(f'{ind_cv}<cv c="{p[0]:.6g} {p[1]:.6g} {p[2]:.6g}"/>\n')

    write_close(f, "NurbsCurve", indent=ind_tag)
