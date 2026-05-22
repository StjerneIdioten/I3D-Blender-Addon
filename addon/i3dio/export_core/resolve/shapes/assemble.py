from __future__ import annotations

from collections import defaultdict
from contextlib import nullcontext
from typing import TYPE_CHECKING

from ...blender.evaluated_mesh import temporary_disable_armature_modifiers
from ...geometry.built import ShapeKind
from ...geometry.mesh.its import MaterialKeyKind
from ...geometry.mesh.material_resolve import resolve_slots
from ...ir import NodeKind, SceneNode, to_transform_group
from ...resources.shapes import ShapeMode

if TYPE_CHECKING:
    from ...ctx import ExportContext


def resolve_shape_links(ctx: ExportContext) -> None:
    """Link Shape nodes to their ShapeEntry by calling ShapeTable.link_node."""
    for node in ctx.ir.iter_nodes(kind=NodeKind.SHAPE, emitted_only=True):
        ctx.shapes.link_node(node)


def _index_emitted_shape_nodes_by_id(ctx: "ExportContext") -> dict[int, list[SceneNode]]:
    shape_nodes_by_id: dict[int, list[SceneNode]] = defaultdict(list)
    for node in ctx.ir.iter_nodes(kind=NodeKind.SHAPE, emitted_only=True):
        sid = node.shape.shape_id
        if sid is not None:
            shape_nodes_by_id[sid].append(node)
    return shape_nodes_by_id


def resolve_shapes_build(ctx: "ExportContext") -> dict[int, list[SceneNode]]:
    """Build/validate geometry for referenced shapes.

    Temporarily disables armature modifiers for skinned meshes to ensure
    correct deformation during evaluation.

    Returns:
        shape_nodes_by_id for shapes that built successfully.

    Side-effects:
        - Invalid shapes are converted to TransformGroup (nodes mutated).
        - Built geometry is cached in ctx.shapes.built_by_id via ctx.shapes.get_built().
    """
    rep = ctx.reporter("shapes")

    # Map shapeId -> [node]
    shape_nodes_by_id = _index_emitted_shape_nodes_by_id(ctx)
    if not shape_nodes_by_id:
        rep.debug("No shape nodes with shapeId; skipping build")
        return {}

    # Detect skinned mesh objects to temporarily disable armature modifiers during build
    skinned_objs = set()
    for n in ctx.ir.iter_nodes(kind=NodeKind.SHAPE, source_object_type='MESH'):
        entry = ctx.shapes.get_entry(n.shape.shape_id)
        if entry is not None and entry.mode is ShapeMode.SKINNED_MESH:
            skinned_objs.add(n.obj)

    # Build shapes with armature modifiers temporarily disabled for skinned meshes
    with temporary_disable_armature_modifiers(ctx, skinned_objs) if skinned_objs else nullcontext():
        rep.debug("Building %d referenced shapes", len(shape_nodes_by_id))

        valid: dict[int, list[SceneNode]] = {}
        for shape_id, nodes in shape_nodes_by_id.items():
            built = ctx.shapes.get_built(shape_id)
            if built is None:
                entry = ctx.shapes.get_entry(shape_id)
                rep.warning("Shape %r produced no valid geometry; exporting as TransformGroup", entry.name)
                for n in nodes:
                    to_transform_group(n)
                continue

            # Log debug info based on shape type
            if built.kind is ShapeKind.INDEXED_TRIANGLE_SET:
                rep.debug(
                    "Shape id=%d built ITS: vertices=%d triangles=%d materials=%d",
                    shape_id,
                    built.vertex_count,
                    built.triangle_count,
                    len(built.material_ids),
                )
            elif built.kind is ShapeKind.NURBS_CURVE:
                rep.debug(
                    "Shape id=%d built NurbsCurve: points=%d type=%s cyclic=%s",
                    shape_id,
                    built.point_count,
                    built.curve_type,
                    built.is_cyclic,
                )
            valid[shape_id] = nodes

        return valid


def finalize_shape_material_ids(ctx: "ExportContext", shape_nodes_by_id: dict[int, list[SceneNode]]) -> None:
    """Finalize materialIds for Scene nodes.

    Expects:
        shape_nodes_by_id contains only shapes that built successfully.
    """
    rep = ctx.reporter("shapes")

    if not shape_nodes_by_id:
        rep.debug("No valid shape nodes; skipping materialIds finalize")
        return

    default_id = ctx.materials.get_default_id()
    wrote_nodes = 0
    for shape_id, nodes in shape_nodes_by_id.items():
        built = ctx.shapes.get_built(shape_id)
        if built is None:
            for n in nodes:
                n.shape.material_ids = None
            continue

        # Only IndexedTriangleSet has materials; NurbsCurve doesn't
        if built.kind is not ShapeKind.INDEXED_TRIANGLE_SET:
            continue

        if not built.material_ids:
            for n in nodes:
                n.shape.material_ids = None
            continue

        if built.material_kind == MaterialKeyKind.MATERIAL_ID:
            # Merge shapes: subsets already keyed by resolved global material IDs.
            for n in nodes:
                n.shape.material_ids = built.material_ids
                wrote_nodes += 1
            continue

        # NORMAL shapes: built.material_ids stores material slot indices in subset order.
        for n in nodes:
            obj = n.obj
            slot_materials = (
                [s.material for s in obj.material_slots] if obj.material_slots else list(obj.data.materials)
            )
            res = resolve_slots(ctx, slot_materials=slot_materials)
            fallback_id = res.fallback_id if res.fallback_id is not None else default_id

            n.shape.material_ids = [
                int(res.slot_ids[slot_idx]) if 0 <= slot_idx < len(slot_materials) else int(fallback_id)
                for slot_idx in built.material_ids
            ]
            wrote_nodes += 1

    rep.debug("Finalized materialIds for %d nodes", wrote_nodes)
