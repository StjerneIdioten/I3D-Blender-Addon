# i3dio/export_core/ir/builder.py
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import bpy

from ..blender.bones import BoneRef
from ..ids import IdKind
from .model import NodeKind, SceneNode, ShapeSceneExt, SourceKind

if TYPE_CHECKING:
    from ..ctx import ExportContext
    from .model import BlenderRef


def _blender_ptr(x: object) -> int | None:
    """Return the Blender pointer integer for x, or None if not available."""
    ap = getattr(x, "as_pointer", None)
    if ap is None:
        return None
    try:
        return int(ap())
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
        blender_ref: BlenderRef,
        source_kind: SourceKind,
        source_ptr: int | None,
        source_object_type: str | None,
        parent_id: int | None,
    ) -> int:
        """Low-level node creation. Keeps identity deterministic."""
        node_id = self.ctx.ids.alloc(IdKind.NODE)

        self.ctx.ir.add_node(
            SceneNode(
                id=node_id,
                name=name,
                kind=kind,
                parent_id=parent_id,
                # identity (stable through export)
                source_kind=source_kind,
                source_ptr=source_ptr,
                source_object_type=source_object_type,
                blender_ref=blender_ref,
            )
        )
        return node_id

    def add_object(self, obj: bpy.types.Object, *, parent_id: int | None) -> int:
        """Add an object node"""
        return self._add_node(
            kind=NodeKind.UNRESOLVED,
            name=obj.name,
            blender_ref=obj,
            source_kind=SourceKind.OBJECT,
            source_ptr=_blender_ptr(obj),
            source_object_type=obj.type,
            parent_id=parent_id,
        )

    def add_collection(self, col: bpy.types.Collection, *, parent_id: int | None) -> int:
        """Add a collection node"""
        return self._add_node(
            kind=NodeKind.TRANSFORM_GROUP,
            name=col.name,
            blender_ref=col,
            source_kind=SourceKind.COLLECTION,
            source_ptr=_blender_ptr(col),
            source_object_type=None,
            parent_id=parent_id,
        )

    def add_bone(self, bone_ref: BoneRef, *, parent_id: int) -> int:
        """Add a bone node (stored as BoneRef in blender_ref)"""
        # NOTE: We do not index BoneRef by pointer in node_id_by_blender_ptr. BoneRef isn't a Blender ID datablock
        # with a stable as_pointer(), and mixing armature pointers into the same lookup can be confusing.
        return self._add_node(
            kind=NodeKind.TRANSFORM_GROUP,
            name=bone_ref.name,
            blender_ref=bone_ref,
            source_kind=SourceKind.BONE_REF,
            source_ptr=None,
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
        """Add a derived Shape node not directly tied to a Blender object.

        Used for programmatically generated shapes like individual splines from
        a curve object (where one Blender object produces multiple i3D Shape nodes).

        Args:
            name: Name for the new Shape node.
            parent_id: Parent node ID (typically the original object's node).
            shape_id: Pre-allocated shape ID from ShapeTable.
            source_obj: Optional source object for reference (not indexed).

        Returns:
            The new node ID.
        """
        node_id = self.ctx.ids.alloc(IdKind.NODE)

        node = SceneNode(
            id=node_id,
            name=name,
            kind=NodeKind.SHAPE,
            parent_id=parent_id,
            source_kind=SourceKind.OTHER,
            source_ptr=None,
            source_object_type=None,
            blender_ref=source_obj,
        )
        # Initialize the shape extension with the pre-assigned shape_id
        node._shape = ShapeSceneExt(shape_id=shape_id)

        self.ctx.ir.add_node(node)
        return node_id
