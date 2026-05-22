from __future__ import annotations

from typing import TYPE_CHECKING

from ...ir import SourceKind

if TYPE_CHECKING:
    from ...ctx import ExportContext


def _read_mapping(pg) -> tuple[bool, str]:
    """Read mapping properties from a property group"""
    return bool(getattr(pg, "is_mapped", False)), (getattr(pg, "mapping_name", "") or "").strip()


def collect_i3d_mappings(ctx: ExportContext) -> None:
    """
    Collect i3dMapping entries from Blender properties and store them in IRIndex.
    Keeps SceneNode clean: mapping is an export sidecar feature.
    """
    out = ctx.ir.index.mapping_id_by_node_id
    out.clear()
    for node in ctx.ir.iter_nodes(emitted_only=True):
        if node.source_kind is SourceKind.OBJECT:
            obj = node.obj
            is_mapped, mapping_name = _read_mapping(obj.i3d_mapping)
        elif node.source_kind is SourceKind.BONE_REF:
            if (bone := node.bone_ref.data_bone()) is None:
                continue
            is_mapped, mapping_name = _read_mapping(bone.i3d_mapping)
        else:
            continue
        if not is_mapped:
            continue
        mapping_id = mapping_name or node.name
        if mapping_id in out.values():
            mapping_id = f"{mapping_id}_{node.id}"
            ctx.node_reporter(node, "mappings").warning(
                "Duplicate i3dMapping id; renamed to %r", mapping_id, code="duplicate_i3d_mapping_id"
            )
        out[node.id] = mapping_id
