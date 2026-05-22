from __future__ import annotations

from typing import TYPE_CHECKING

from ...ir import NodeKind

if TYPE_CHECKING:
    from ...ctx import ExportContext


def resolve_skinned_meshes(ctx: ExportContext) -> None:
    rep = ctx.reporter("skinned_mesh")

    # Find bone nodes produced by resolve_armatures.
    bones_by_arm_ptr = ctx.ir.index.bone_nodes_by_armature_ptr

    processed = 0
    # Only mesh objects can be skinned meshes (have modifiers and vertex groups)
    for node in ctx.ir.iter_nodes(kind=NodeKind.SHAPE, source_object_type='MESH'):
        obj = node.obj
        obj_rep = ctx.object_reporter(obj, "skinned_mesh")
        # Find armature modifiers with valid armature object.
        if not (arm_mods := [m for m in obj.modifiers if m.type == 'ARMATURE' and m.object]):
            continue

        # Only treat as skinned mesh if there are vertex groups (skinning data).
        if not obj.vertex_groups:
            obj_rep.warning(
                "Object has armature modifier(s) but no vertex groups; it will be exported as a normal mesh.",
                code="skinned_mesh_no_vertex_groups",
            )
            continue

        bind_node_ids: list[int] = []
        vgroup_to_bind: dict[int, int] = {}

        vgroups = list(obj.vertex_groups)
        bind_idx = 0

        # Deterministic bind order: armature modifiers in order, then vgroup order
        for mod in arm_mods:
            arm_obj = mod.object
            if arm_obj is None or arm_obj.type != 'ARMATURE':
                continue

            if not (bone_map := bones_by_arm_ptr.get(arm_obj.as_pointer())):
                continue

            for vg in vgroups:
                if vg.index in vgroup_to_bind:
                    continue
                if (bone_node_id := bone_map.get(vg.name)) is None:
                    continue
                vgroup_to_bind[int(vg.index)] = bind_idx
                bind_node_ids.append(int(bone_node_id))
                bind_idx += 1

        if not bind_node_ids:
            # Mesh has armature modifiers but no matching exported bones.
            obj_rep.warning(
                "Mesh has armature modifier(s) but no matching exported bones were found via vertex group names; "
                "it will be exported as a normal mesh.",
                code="skinned_mesh_no_matching_bones",
            )
            continue

        # Create distinct skinned mesh shape entry and link to node.
        entry = ctx.shapes.add_skinned_mesh_shape(obj, name=obj.data.name)

        # Inject contributor mapping
        if entry.contributors:
            entry.contributors[0].skin_vgroup_to_bind_index = vgroup_to_bind

        # Node is already SHAPE kind (from resolve_kinds), so _shape exists
        node.shape.shape_id = entry.id
        node.shape.skin_bind_node_ids = bind_node_ids

        processed += 1
        obj_rep.debug("shapeId=%d binds=%d", entry.id, len(bind_node_ids))

    if not processed:
        rep.debug("No skinned meshes detected")
