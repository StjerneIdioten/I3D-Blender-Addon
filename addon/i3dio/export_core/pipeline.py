from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from . import traverse
from .resolve.runner import resolve_all
from .scope import CollectionScope, ObjectScope

if TYPE_CHECKING:
    import logging

    import bpy

    from .ctx import ExportContext
    from .scope import ExportScope


def run_export(ctx: ExportContext, scope: ExportScope) -> None:
    """Run the export pipeline."""
    _PipelineRun(ctx, scope).run()


@dataclass(slots=True)
class _PipelineRun:
    ctx: ExportContext
    scope: ExportScope
    logger: logging.LoggerAdapter = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.logger = self.ctx.ctx_logger(prefix="pipeline")

    def run(self) -> None:
        self.logger.debug("Traversal start")
        self._build_ir()
        self.logger.debug(
            "Traversal done: nodes=%d roots=%d", len(self.ctx.ir.scene_nodes), sum(1 for _ in self.ctx.ir.iter_roots())
        )

        self.logger.debug("Resolve start")
        resolve_all(self.ctx)
        self.logger.debug("Resolve done")

    def _build_ir(self) -> None:
        """Build the IR for the given export scope."""
        match self.scope:
            case CollectionScope(collection):
                self._build_collection_scope(collection)
            case ObjectScope(objects, include_children):
                self._build_object_scope(objects, include_children=include_children)
            case _:
                raise TypeError(f"Unsupported export scope: {type(self.scope).__name__}")

    def _build_collection_scope(self, collection: bpy.types.Collection) -> None:
        self.logger.info("Exporting collection %r", collection.name)
        traverse.add_collection_tree(self.ctx, collection, parent_id=None, emit_self=False)

    def _build_object_scope(self, objects: tuple[bpy.types.Object, ...], *, include_children: bool) -> None:
        self.logger.info("Exporting %d objects", len(objects))
        if include_children:
            traverse.build_object_roots(self.ctx, objects)
        else:
            traverse.build_selected_roots(self.ctx, objects)
