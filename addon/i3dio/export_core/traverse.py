from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Callable, Iterable

import bpy

from ..utility import sort_blender_objects_by_outliner_ordering

if TYPE_CHECKING:
    from .ctx import ExportContext

ChildIter = Callable[[bpy.types.Object], Iterable[bpy.types.Object]]


def add_object_node(ctx: ExportContext, obj: bpy.types.Object, parent_id: int | None) -> int | None:
    """Create the node for an object (no recursion). Returns node_id or None if skipped."""
    if obj.i3d_attributes.exclude_from_export:
        ctx.object_reporter(obj, "traverse").debug("Excluded from export (skip subtree)")
        return None
    return ctx.builder.add_object(obj=obj, parent_id=parent_id)


def _add_object_with_children(
    ctx: ExportContext,
    obj: bpy.types.Object,
    parent_id: int | None,
    *,
    child_iter: ChildIter,
    expand_instance_collections: bool,
) -> None:
    if (node_id := add_object_node(ctx, obj, parent_id)) is None:
        return  # excluded
    obj_type = obj.type
    rep = ctx.object_reporter(obj, "traverse")
    if obj_type == 'MESH' and ctx.has_feature('MERGE_CHILDREN') and obj.i3d_merge_children.enabled:
        ctx.ir.index.merge_children_roots.append(node_id)
        rep.debug("MergeChildren root: skipping child traversal")
        return  # skip children

    if expand_instance_collections and obj.instance_collection is not None:
        rep.debug("Expanding instance_collection %r", obj.instance_collection.name)
        add_collection(ctx, obj.instance_collection, node_id)

    if obj_type == 'MESH' and ctx.has_feature('MERGE_GROUPS') and (mg := obj.i3d_merge_group_index) >= 0:
        ctx.ir.index.merge_group_nodes_by_index.setdefault(mg, []).append(node_id)
        rep.debug("Added to MergeGroup %d", mg)

    for child in child_iter(obj):
        _add_object_with_children(
            ctx,
            child,
            node_id,
            child_iter=child_iter,
            expand_instance_collections=expand_instance_collections,
        )


def _default_child_iter(obj: bpy.types.Object) -> Iterable[bpy.types.Object]:
    """Default child iterator for standard object traversal."""
    return sort_blender_objects_by_outliner_ordering(obj.children)


def add_object(ctx: ExportContext, obj: bpy.types.Object, parent_id: int | None) -> None:
    """Add a single object and its children to the IR."""
    _add_object_with_children(ctx, obj, parent_id, child_iter=_default_child_iter, expand_instance_collections=True)


def add_collection(
    ctx: ExportContext, collection: bpy.types.Collection, parent_id: int | None, *, emit_self: bool = True
) -> None:
    """
    Add a collection and its contents.
    - Child collections first, then root objects (outliner-like).
    - Collection membership doesn't drive parenting: only root objects are added here;
      non-root objects are exported via their object-parent chain elsewhere.
    - If keep_collections_as_transformgroups and emit_self: emit a TG node for the collection,
      otherwise treat it as transparent.
    """
    keep = ctx.setting("keep_collections_as_transformgroups", False)

    # Decide where the collection's contents should attach
    contents_parent_id = parent_id
    if emit_self and keep:
        contents_parent_id = ctx.builder.add_collection(collection, parent_id=parent_id)

    # Child collections first
    for child_coll in collection.children.values():
        add_collection(ctx, child_coll, contents_parent_id)

    # Then root objects in this collection (non-root objects come via parent chain elsewhere)
    roots = [obj for obj in collection.objects if obj.parent is None]
    for obj in sort_blender_objects_by_outliner_ordering(roots):
        add_object(ctx, obj, contents_parent_id)


def build_from_objects(ctx: ExportContext, objects: Iterable[bpy.types.Object]) -> None:
    """Entry point for a set of root objects (e.g. active/selected)."""
    for obj in objects:
        add_object(ctx, obj, parent_id=None)


def build_selected_only(ctx: ExportContext, selected_objs: list[bpy.types.Object]) -> None:
    """Selected-only mode without traversing unselected children. Keeps nearest-selected-parent rule."""
    selection_set = set(selected_objs)

    # obj -> nearest parent within selection
    parent_map: dict[bpy.types.Object, bpy.types.Object] = {}
    roots: list[bpy.types.Object] = []

    for obj in selected_objs:
        parent = obj.parent
        while parent and parent not in selection_set:
            parent = parent.parent
        if parent:
            parent_map[obj] = parent
        else:
            roots.append(obj)

    # Build selected-children adjacency from parent_map
    children_map: dict[bpy.types.Object, list[bpy.types.Object]] = defaultdict(list)
    for child, parent in parent_map.items():
        children_map[parent].append(child)

    # Stable/outliner-like ordering
    roots_sorted = sort_blender_objects_by_outliner_ordering(roots)
    for p, kids in list(children_map.items()):
        children_map[p] = sort_blender_objects_by_outliner_ordering(kids)

    def selected_children(obj: bpy.types.Object) -> Iterable[bpy.types.Object]:
        return children_map.get(obj, ())

    for root in roots_sorted:
        _add_object_with_children(
            ctx,
            root,
            parent_id=None,
            child_iter=selected_children,
            expand_instance_collections=True,
        )
