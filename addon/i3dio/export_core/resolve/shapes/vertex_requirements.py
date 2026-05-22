from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from ...geometry.built import ShapeKind

if TYPE_CHECKING:
    from ...ctx import ExportContext
    from ...geometry.mesh.build_its import ShapeEntry
    from ...ir.model import SceneNode


def resolve_shape_vertex_requirements(ctx: ExportContext, shape_nodes_by_id: dict[int, list[SceneNode]]) -> None:
    """
    For each shape, determine whether tangents and/or vertex colors are needed based on the materials used by its nodes.

    Only applies to IndexedTriangleSet shapes - NurbsCurve shapes don't have materials or vertex colors.
    """
    for shape_id, nodes in shape_nodes_by_id.items():
        built = ctx.shapes.get_built(shape_id)
        if built is None or built.kind is not ShapeKind.INDEXED_TRIANGLE_SET:
            continue  # Skip non-mesh shapes (e.g., NurbsCurve) - they don't have materials or vertex attributes
        entry = ctx.shapes.get_entry(shape_id)

        mats = [ctx.materials.get_entry(mid) for node in nodes for mid in node.shape.material_ids]
        needs_tangent = any(m.requires_tangents() for m in mats)
        vcol_mats = {m.key.export_name for m in mats if m.requires_vcol()}
        needs_vcol = bool(vcol_mats)

        if needs_tangent:
            entry.enable_tangent()

        mode = _shape_effective_vcol_mode(ctx, entry)  # AUTO / IF_PRESENT
        if mode == "IF_PRESENT":
            continue  # keep whatever was extracted
        else:  # AUTO
            if needs_vcol:
                if built.color is None:
                    built.color = np.zeros((built.vertex_count, 4), dtype=np.float32)
                    ctx.reporter("shapes").warning(
                        "Shape %r needs vertex colors (materials: %s) but has no vertex color layer; padded zeros",
                        entry.name,
                        ", ".join(sorted(vcol_mats)),
                    )
            else:
                built.color = None  # discard extracted colors


def _shape_effective_vcol_mode(ctx: ExportContext, entry: ShapeEntry) -> str:
    override = ctx.setting("vertex_color_override", "USE_MESH")
    if override == "FORCE_AUTO":
        return "AUTO"
    if override == "FORCE_IF_PRESENT":
        return "IF_PRESENT"
    # USE_MESH - check all contributors; if any wants IF_PRESENT, preserve colors
    for contributor in entry.contributors:
        obj = contributor.obj
        # Only mesh data has color_export attribute
        if obj is not None and obj.type == 'MESH' and hasattr(obj.data, 'i3d_attributes'):
            if obj.data.i3d_attributes.color_export == "IF_PRESENT":
                return "IF_PRESENT"
    return "AUTO"
