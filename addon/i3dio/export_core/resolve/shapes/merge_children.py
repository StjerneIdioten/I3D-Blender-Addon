from __future__ import annotations

from typing import TYPE_CHECKING

import bpy
import mathutils

from ....utility import sort_blender_objects_by_outliner_ordering
from ...ir import NodeKind, set_kind
from ...resources.shapes import ShapeContributor, ShapeMode

if TYPE_CHECKING:
    from ...ctx import ExportContext

# Maximum index value for `mergeChildren` objects, used to normalize
# generic values (generic_value01) for shaders. This constant is critical for:
# - Calculating normalized indices for motion paths or animations (e.g., vertex animation textures).
# - Controlling visibility of elements via the `hideByIndex` shader parameter.
# NOTE: The value must match the expected range in the shaders (e.g., [0..32767]).
GENERIC_VALUE01_MAX_INDEX = 32767
# Difference between Merge Group and Merge Children:
# Merge Group collect multiple meshes which are all referenced (and keeps its location) in the scene graph
# Merge Children collects the children meshes of the "root" and "root" mesh is not included in the IndexedTriangleSet.
# Merge Children is used to merge all children meshes of a single object, which are not referenced in the scene graph.


def resolve_merge_children(ctx: "ExportContext") -> None:
    """
    Resolve MergeChildren roots collected during traversal.

    MergeChildren merges *descendant meshes* into one ShapeEntry:
    - The root becomes a Scene Shape (gets shapeId), but its own mesh is excluded.
    - Children are not emitted as IR nodes; only geometry is produced.
    - Each top-level child subtree gets a normalized generic_value01 bucket (0..1).
    - reference_frame is root-world if apply_transforms else top-child world.
    """
    rep = ctx.reporter("merge_children")

    for root_id in ctx.ir.index.merge_children_roots:
        node = ctx.ir.scene_nodes[root_id]
        obj = node.obj
        mc_pg = obj.i3d_merge_children
        # Collect contributors
        contributors = _collect_contributors(obj, mc_pg.apply_transforms, mc_pg.interpolation_steps)

        if not contributors:
            rep.warning("[%s] MergeChildren enabled but no child meshes found; exporting as regular Shape", obj.name)
            # Let normal shape logic handle it later (do not create ShapeEntry here).
            continue

        # Create synthetic merged shape entry
        entry = ctx.shapes.add_merge_shape(root_obj=obj, name=obj.name, mode=ShapeMode.MERGE_CHILDREN)
        entry.enable_generic_value01()
        for mesh_obj, ref_frame, g in contributors:
            entry.contributors.append(ShapeContributor(mesh_obj, ref_frame, generic_value01=g))

        # Root becomes a Shape in Scene and points at shapeId
        set_kind(node, NodeKind.SHAPE)
        # set_kind ensures _shape exists, so safe to use property
        node.shape.shape_id = entry.id

        rep.debug("[%s] MergeChildren shapeId=%d contributors=%d", obj.name, entry.id, len(entry.contributors))


def _collect_contributors(
    root_obj: bpy.types.Object, apply_transforms: bool, steps: int
) -> list[tuple[bpy.types.Object, mathutils.Matrix, float]]:
    """Returns list of (mesh_obj, reference_frame, generic_value01). Root mesh is excluded."""
    root_world = root_obj.matrix_world.copy()
    out: list[tuple[bpy.types.Object, mathutils.Matrix, float]] = []

    child_objects = sort_blender_objects_by_outliner_ordering(root_obj.children)
    if root_obj.i3d_merge_children.reverse_order:
        child_objects.reverse()

    for idx, top_child in enumerate(child_objects):
        g = min(idx * steps, GENERIC_VALUE01_MAX_INDEX) / GENERIC_VALUE01_MAX_INDEX
        ref_frame = root_world if apply_transforms else top_child.matrix_world.copy()

        stack = [top_child]
        while stack:
            obj = stack.pop()
            if obj.type == 'MESH':
                out.append((obj, ref_frame, g))
            stack.extend(obj.children)

    return out
