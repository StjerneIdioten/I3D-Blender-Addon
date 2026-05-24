from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import bpy

from ..ids import IdKind
from .model import BlenderRef, NodeKind, SceneNode, SourceKind

if TYPE_CHECKING:
    from ..ctx import ExportContext


def _blender_ptr(value: object) -> int | None:
    """Get a stable integer pointer for a Blender data-block, or None if not possible."""
    if (as_pointer := getattr(value, "as_pointer", None)) is None:
        return None
    try:
        return int(as_pointer())
    except Exception:
        return None


@dataclass(slots=True)
class SceneBuilder:
    ctx: ExportContext

    def _add_node(
        self,
        *,
        kind: NodeKind,
        name: str,
        blender_ref: BlenderRef | None,
        source_kind: SourceKind,
        source_ptr: int | None,
        source_object_type: str | None,
        parent_id: int | None,
    ) -> int:
        """Add a new node to the IR with the given properties and return its ID."""
        node_id = self.ctx.ids.alloc(IdKind.NODE)

        node = SceneNode(
            id=node_id,
            name=name,
            kind=kind,
            parent_id=parent_id,
            source_kind=source_kind,
            source_ptr=source_ptr,
            source_object_type=source_object_type,
            blender_ref=blender_ref,
        )

        self.ctx.ir.add_node(node)
        return node_id

    def add_object(self, obj: bpy.types.Object, *, parent_id: int | None) -> int:
        """Add an object node to the IR."""
        return self._add_node(
            kind=NodeKind.UNRESOLVED,
            name=obj.name,
            blender_ref=obj,
            source_kind=SourceKind.OBJECT,
            source_ptr=_blender_ptr(obj),
            source_object_type=obj.type,
            parent_id=parent_id,
        )

    def add_collection(self, collection: bpy.types.Collection, *, parent_id: int | None) -> int:
        """Add a collection node to the IR."""
        return self._add_node(
            kind=NodeKind.TRANSFORM_GROUP,
            name=collection.name,
            blender_ref=collection,
            source_kind=SourceKind.COLLECTION,
            source_ptr=_blender_ptr(collection),
            source_object_type=None,
            parent_id=parent_id,
        )

    def add_derived_shape(
        self,
        *,
        name: str,
        parent_id: int,
        shape_id: int,
        source_obj: bpy.types.Object | None = None,
    ) -> int:
        """Add a shape node derived from the given source object, attached to the given parent, and return its ID."""
        node_id = self.ctx.ids.alloc(IdKind.NODE)

        node = SceneNode(
            id=node_id,
            name=name,
            kind=NodeKind.UNRESOLVED,
            parent_id=parent_id,
            source_kind=SourceKind.OTHER,
            source_ptr=None,
            source_object_type=None,
            blender_ref=source_obj,
        )
        node.make_shape(shape_id=shape_id)

        self.ctx.ir.add_node(node)
        return node_id
