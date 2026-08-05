from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..ids import IdKind
from .node import (
    BoneRef,
    BoneSource,
    CollectionSource,
    NodePayload,
    NodeSource,
    ObjectSource,
    SceneNode,
    ShapePayload,
    SyntheticSource,
    TransformGroupPayload,
    UnresolvedPayload,
)

if TYPE_CHECKING:
    import bpy

    from ..ctx import ExportContext


@dataclass(slots=True)
class SceneBuilder:
    ctx: ExportContext

    def _create_node(self, *, name: str, source: NodeSource, payload: NodePayload, parent_id: int | None) -> SceneNode:
        """Create a new node, add it to the IR, and return the node for final specialization."""
        node = SceneNode(
            id=self.ctx.ids.alloc(IdKind.NODE),
            name=name,
            source=source,
            payload=payload,
            parent_id=parent_id,
        )

        self.ctx.ir.add_node(node)
        return node

    def add_object(self, obj: bpy.types.Object, *, parent_id: int | None) -> int:
        """Add an object node to the IR."""
        node = self._create_node(
            name=obj.name,
            source=ObjectSource.from_object(obj),
            payload=UnresolvedPayload(),
            parent_id=parent_id,
        )
        return node.id

    def add_collection(self, collection: bpy.types.Collection, *, parent_id: int | None) -> int:
        """Add a collection node to the IR."""
        node = self._create_node(
            name=collection.name,
            source=CollectionSource.from_collection(collection),
            payload=TransformGroupPayload(),
            parent_id=parent_id,
        )
        return node.id

    def add_bone(self, bone_ref: BoneRef, *, parent_id: int) -> int:
        """Add a bone transform-group node to the IR."""
        node = self._create_node(
            name=bone_ref.name,
            source=BoneSource(blender_ref=bone_ref),
            payload=TransformGroupPayload(),
            parent_id=parent_id,
        )
        return node.id

    def add_derived_shape(
        self,
        *,
        name: str,
        parent_id: int,
        shape_id: int,
        source_obj: bpy.types.Object | None = None,
    ) -> int:
        """Add a shape node derived from the given source object, attached to the given parent, and return its ID."""
        node = self._create_node(
            name=name,
            source=SyntheticSource.from_object(source_obj) if source_obj is not None else SyntheticSource(),
            payload=ShapePayload(shape_id=shape_id),
            parent_id=parent_id,
        )
        return node.id
