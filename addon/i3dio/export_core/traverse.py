from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence
from typing import TYPE_CHECKING

from ..utility import sort_blender_objects_by_outliner_ordering

if TYPE_CHECKING:
    import bpy

    from .ctx import ExportContext


def build_object_roots(ctx: ExportContext, objects: Iterable[bpy.types.Object]) -> None:
    """Build IR from the given objects, filtering to root objects only.

    Objects whose parents are not in the provided object set are treated as roots
    and traversed with their full child hierarchies.
    """
    object_set = set(objects)
    roots = (obj for obj in object_set if object_set.isdisjoint(_iter_parents(obj)))

    for obj in _sorted_objects(roots):
        add_object_tree(ctx, obj, parent_id=None)


def _iter_parents(obj: bpy.types.Object) -> Iterable[bpy.types.Object]:
    parent = obj.parent
    while parent is not None:
        yield parent
        parent = parent.parent


def build_selected_roots(ctx: ExportContext, selected_objects: Sequence[bpy.types.Object]) -> None:
    """Build IR from selected objects, preserving nearest selected parent relationships."""
    roots, children_by_parent = _selected_tree(selected_objects)

    def selected_children(obj: bpy.types.Object) -> Iterable[bpy.types.Object]:
        return children_by_parent.get(obj, ())

    for root in _sorted_objects(roots):
        _walk_object_tree(ctx, root, parent_id=None, get_children=selected_children)


def add_collection_tree(
    ctx: ExportContext,
    collection: bpy.types.Collection,
    parent_id: int | None,
    *,
    emit_self: bool = True,
) -> None:
    """Add a collection and its contents to the IR."""
    contents_parent_id = parent_id
    if emit_self and ctx.setting("keep_collections_as_transformgroups", False):
        contents_parent_id = ctx.builder.add_collection(collection, parent_id=parent_id)

    for child_collection in collection.children.values():
        add_collection_tree(ctx, child_collection, contents_parent_id)

    root_objects = [obj for obj in collection.objects if obj.parent is None]
    for obj in _sorted_objects(root_objects):
        add_object_tree(ctx, obj, contents_parent_id)


def add_object_tree(ctx: ExportContext, obj: bpy.types.Object, parent_id: int | None) -> None:
    """Add an object and its child hierarchy to the IR."""
    _walk_object_tree(ctx, obj, parent_id, get_children=_object_children)


def _selected_tree(
    selected_objects: Sequence[bpy.types.Object],
) -> tuple[list[bpy.types.Object], dict[bpy.types.Object, list[bpy.types.Object]]]:
    """Build a selected-only hierarchy using the nearest selected parent for each object."""
    selected_set = set(selected_objects)
    children_by_parent: defaultdict[bpy.types.Object, list[bpy.types.Object]] = defaultdict(list)
    roots: list[bpy.types.Object] = []

    for obj in selected_objects:
        parent = obj.parent
        while parent is not None and parent not in selected_set:
            parent = parent.parent

        if parent is None:
            roots.append(obj)
        else:
            children_by_parent[parent].append(obj)

    return roots, {parent: _sorted_objects(children) for parent, children in children_by_parent.items()}


def _walk_object_tree(
    ctx: ExportContext,
    obj: bpy.types.Object,
    parent_id: int | None,
    *,
    get_children: Callable[[bpy.types.Object], Iterable[bpy.types.Object]],
) -> None:
    """Walk an object hierarchy, expanding instance collections and using the given child lookup."""
    node_id = _add_object_node(ctx, obj, parent_id)
    if node_id is None:
        return

    if obj.instance_collection is not None:
        add_collection_tree(ctx, obj.instance_collection, node_id, emit_self=False)

    for child in get_children(obj):
        _walk_object_tree(ctx, child, node_id, get_children=get_children)


def _add_object_node(ctx: ExportContext, obj: bpy.types.Object, parent_id: int | None) -> int | None:
    """Create the IR node for one object, or return None when the object subtree should be skipped."""
    if obj.i3d_attributes.exclude_from_export:
        ctx.ctx_logger(name="export", object_name=obj.name, prefix="traverse").debug("Excluded from export")
        return None

    return ctx.builder.add_object(obj, parent_id=parent_id)


def _object_children(obj: bpy.types.Object) -> list[bpy.types.Object]:
    return _sorted_objects(obj.children)


def _sorted_objects(objects: Iterable[bpy.types.Object]) -> list[bpy.types.Object]:
    return sort_blender_objects_by_outliner_ordering(list(objects))
