from __future__ import annotations

from typing import TYPE_CHECKING

import bpy

from ...ir import NodeKind
from ...resources.shapes import ShapeContributor, ShapeMode

if TYPE_CHECKING:
    from ...ctx import ExportContext


MAX_BIND_NODES = 256  # total bind nodes (including root)


def resolve_merge_groups(ctx: ExportContext) -> None:
    rep = ctx.reporter("merge_group")

    groups = ctx.ir.index.merge_group_nodes_by_index
    if not groups:
        rep.debug("No MergeGroups to process")
        return

    scene_groups = ctx.scene.i3dio_merge_groups
    for mg_index, node_ids in groups.items():
        if not (0 <= mg_index < len(scene_groups)):
            rep.warning(
                "MergeGroup index %d out of range (have %d groups). This group will not be exported.",
                mg_index,
                len(scene_groups),
                code="merge_group_index_out_of_range",
            )
            continue

        mg = scene_groups[mg_index]
        mg_label = mg.name or f"MergeGroup_{mg_index}"
        root_obj: bpy.types.Object | None = mg.root
        if not root_obj:
            rep.warning("MergeGroup %d has no root object; skipping", mg_index)
            continue

        obj_rep = ctx.object_reporter(root_obj, "merge_group")
        if root_obj.type != 'MESH':
            obj_rep.warning(
                "MergeGroup %r root %r must be a Mesh object (got %s); it will not be exported.",
                mg_label,
                root_obj.name,
                root_obj.type,
                code="merge_group_root_not_mesh",
            )
            continue

        ids = ctx.ir.index.node_id_by_blender_ptr.get(root_obj.as_pointer(), [])
        root_node_id = next((nid for nid in ids if nid in node_ids), ids[0] if ids else None)
        if root_node_id is None:
            obj_rep.warning(
                "MergeGroup %r root %r is not part of the export; it will not be exported. "
                "Ensure the root is included in export scope.",
                mg_label,
                root_obj.name,
                code="merge_group_root_not_exported",
            )
            continue
        if len(ids) > 1:
            obj_rep.warning(
                "MergeGroup root %r appears multiple times in export graph; using nodeId=%d",
                root_obj.name,
                root_node_id,
            )

        root_node = ctx.ir.scene_nodes[root_node_id]

        # bind order: root first, then the rest in traversal order (dedup just in case)
        ordered = list(dict.fromkeys([root_node_id, *node_ids]))

        if len(ordered) == 1:
            obj_rep.warning(
                "MergeGroup %r only contains the root (no member bind nodes). Remove the MergeGroup or add members.",
                mg_label,
                code="merge_group_single_bind_node",
            )
        elif len(ordered) > MAX_BIND_NODES:
            obj_rep.warning(
                "MergeGroup %r has %d bind nodes. Recommended maximum is %d; split into multiple MergeGroups.",
                mg_label,
                len(ordered),
                MAX_BIND_NODES,
                code="merge_group_bind_node_limit",
            )

        # Create the merged ShapeEntry
        entry = ctx.shapes.add_merge_shape(
            root_obj=root_obj,
            name=mg_label,
            mode=ShapeMode.MERGE_GROUP,
            merge_group_index=mg_index,
        )
        entry.enable_bind_index()
        root_frame = root_obj.matrix_world.copy()

        # Contributors + bind list (bind index == position in ordered list)
        for bind_index, nid in enumerate(ordered):
            ref = ctx.ir.scene_nodes[nid].blender_ref
            if isinstance(ref, bpy.types.Object) and ref.type == "MESH":
                entry.contributors.append(ShapeContributor(obj=ref, reference_frame=root_frame, bind_index=bind_index))

        # Mutate IR nodes (root_node is already SHAPE kind from traversal, _shape exists)
        root_node.shape.shape_id = entry.id
        root_node.shape.skin_bind_node_ids = ordered

        for nid in ordered[1:]:  # Member nodes become TransformGroups
            ctx.ir.scene_nodes[nid].kind = NodeKind.TRANSFORM_GROUP

        rep.debug(
            "[%s] MergeGroup %d shapeId=%d binds=%d contrib_meshes=%d",
            root_obj.name,
            mg_index,
            entry.id,
            len(ordered),
            len(entry.contributors),
        )
