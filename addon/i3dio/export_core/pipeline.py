# i3dio/export_core/pipeline.py
from __future__ import annotations

from typing import TYPE_CHECKING

import bpy

from . import post_export, traverse
from .resolve.runner import resolve_all
from .serialize.emit_i3d_mappings import emit_i3d_mappings
from .serialize.write_i3d import write_i3d

if TYPE_CHECKING:
    from .ctx import ExportContext


def run_export(ctx: ExportContext, *, context: bpy.types.Context) -> None:
    """Run the export pipeline to export the Blender scene to an I3D file."""
    rep = ctx.reporter("pipeline")
    rep.debug("Traverse start")
    scope_objects = _build_ir(ctx, context=context)
    rep.debug("Traverse done (nodes=%d roots=%d)", len(ctx.ir.scene_nodes), sum(1 for _ in ctx.ir.iter_roots()))

    rep.debug("Resolve start")
    resolve_all(ctx)
    rep.debug("Resolve done")

    rep.debug("Serialization start")
    write_i3d(ctx)
    rep.debug("Serialization done")

    rep.debug("i3dMappings export start")
    emit_i3d_mappings(ctx)
    rep.debug("i3dMappings export done")

    post_export.run_post_export(ctx, scope_objects=scope_objects)


def _build_ir(ctx: ExportContext, *, context: bpy.types.Context) -> list[bpy.types.Object]:
    op = ctx.operator
    reporter = ctx.reporter("pipeline")

    # Determine the export scope objects BEFORE traversal.
    # This allows post-export steps (DDS sidecars etc) to run on authoring intent
    # even when objects are excluded from the I3D export.
    scope_objects: list[bpy.types.Object]
    source_collection = None
    if getattr(op, "collection", None):
        source_collection = bpy.data.collections.get(op.collection)
        if not source_collection:
            reporter.fail("Collection %r was not found", op.collection)

    if source_collection:
        reporter.info("Exporting from collection export %r", source_collection.name)
        scope_objects = list(source_collection.all_objects)
        traverse.add_collection(ctx, source_collection, parent_id=None, emit_self=False)
        return scope_objects

    match op.selection:
        case "ALL":
            reporter.info("Exporting entire scene")
            scope_objects = list(context.scene.collection.all_objects)
            traverse.add_collection(ctx, context.scene.collection, parent_id=None, emit_self=False)
            return scope_objects
        case "ACTIVE_COLLECTION":
            active_layer_collection = context.view_layer.active_layer_collection.collection
            reporter.info("Exporting active collection %r", active_layer_collection.name)
            scope_objects = list(active_layer_collection.all_objects)
            traverse.add_collection(ctx, active_layer_collection, parent_id=None, emit_self=False)
            return scope_objects
        case "ACTIVE_OBJECT":
            if context.active_object is None:
                reporter.fail("No active object for export")
            reporter.info("Exporting active object %r", context.active_object.name)
            # ACTIVE_OBJECT always exports the object and its children (see traverse.build_from_objects).
            scope_objects = _objects_with_children([context.active_object])
            traverse.build_from_objects(ctx, [context.active_object])
            return scope_objects
        case "SELECTED_OBJECTS":
            if not context.selected_objects:
                reporter.fail("No objects selected for export")
            reporter.info("Exporting %d selected objects", len(context.selected_objects))
            if ctx.setting("selection_traverse_children", False):
                scope_objects = _objects_with_children(list(context.selected_objects))
                traverse.build_from_objects(ctx, context.selected_objects)
                return scope_objects
            else:
                scope_objects = list(context.selected_objects)
                traverse.build_selected_only(ctx, context.selected_objects)
                return scope_objects
        case _:
            reporter.fail("Unknown selection mode: %r", op.selection)

    return []


def _objects_with_children(objs: list[bpy.types.Object]) -> list[bpy.types.Object]:
    """Return objs plus all recursive children, de-duped."""
    out: list[bpy.types.Object] = []
    seen: set[int] = set()

    def add(o: bpy.types.Object) -> None:
        ptr = int(o.as_pointer())
        if ptr in seen:
            return
        seen.add(ptr)
        out.append(o)

    stack: list[bpy.types.Object] = []
    for o in objs:
        if o is None:
            continue
        add(o)
        stack.append(o)

    while stack:
        cur = stack.pop()
        for child in getattr(cur, "children", ()):  # Blender Object children
            if child is None:
                continue
            ptr = int(child.as_pointer())
            if ptr in seen:
                continue
            add(child)
            stack.append(child)

    return out
