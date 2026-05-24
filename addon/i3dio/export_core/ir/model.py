from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import Enum, StrEnum, auto
from typing import Any, cast

import bpy
from mathutils import Matrix

BlenderRef = bpy.types.Object | bpy.types.Collection


class NodeKind(StrEnum):
    TRANSFORM_GROUP = "TransformGroup"
    REFERENCE_NODE = "ReferenceNode"
    SHAPE = "Shape"
    LIGHT = "Light"
    CAMERA = "Camera"

    # Temporary kind used after traversal, before resolve/kinds has classified the node
    UNRESOLVED = "__UNRESOLVED__"


class SourceKind(Enum):
    OBJECT = auto()
    COLLECTION = auto()
    OTHER = auto()


@dataclass(slots=True)
class EmitAttrs:
    """Attributes intended for final I3D/XML emission."""

    node: dict[str, Any] = field(default_factory=dict)
    children: dict[str, dict[str, Any]] = field(default_factory=dict)

    def child(self, tag: str) -> dict[str, Any]:
        return self.children.setdefault(tag, {})


@dataclass(slots=True)
class ShapeSceneExt:
    """Shape-specific scene data, attached to shape nodes."""

    shape_id: int | None = None
    material_ids: list[int] | None = None
    skin_bind_node_ids: list[int] | None = None


@dataclass(slots=True)
class ReferenceNodeExt:
    """Reference node-specific scene data, attached to reference nodes."""

    reference_id: int | None = None
    runtime_loaded: bool = False
    child_path: str | None = None


@dataclass(slots=True)
class UserAttributeEntry:
    name: str
    type: str
    value: Any


@dataclass(slots=True)
class SceneNode:
    """A node in the export scene graph IR.

    The IR stores export intent, not XML directly. Traversal creates mostly
    unresolved nodes, resolve passes classify/fill them, and serializers later
    consume the finalized state.
    """

    id: int
    name: str
    kind: NodeKind
    source_kind: SourceKind
    parent_id: int | None = None

    matrix_local_export: Matrix | None = None
    emit: bool = True
    attrs: EmitAttrs = field(default_factory=EmitAttrs)

    source_ptr: int | None = None
    source_object_type: str | None = None
    source_object_type_override: str | None = None
    blender_ref: BlenderRef | None = None

    _shape: ShapeSceneExt | None = None
    _ref: ReferenceNodeExt | None = None

    def set_kind(self, kind: NodeKind) -> None:
        """Set the node kind and keep kind-specific extensions valid."""
        self.kind = kind

        if kind is NodeKind.SHAPE and self._shape is None:
            self._shape = ShapeSceneExt()
        elif kind is NodeKind.REFERENCE_NODE and self._ref is None:
            self._ref = ReferenceNodeExt()

    def make_shape(self, *, shape_id: int | None = None) -> ShapeSceneExt:
        self.set_kind(NodeKind.SHAPE)
        shape = self.shape
        if shape_id is not None:
            shape.shape_id = shape_id
        return shape

    def make_reference(
        self, *, reference_id: int | None = None, runtime_loaded: bool | None = None, child_path: str | None = None
    ) -> ReferenceNodeExt:
        self.set_kind(NodeKind.REFERENCE_NODE)
        ref = self.ref

        if reference_id is not None:
            ref.reference_id = reference_id
        if runtime_loaded is not None:
            ref.runtime_loaded = runtime_loaded
        if child_path is not None:
            ref.child_path = child_path

        return ref

    def _require(
        self,
        attr: str,
        *,
        expected_kind: NodeKind | None = None,
        expected_source: SourceKind | None = None,
    ) -> Any:
        if expected_kind and self.kind is not expected_kind:
            raise RuntimeError(f"Node {self.id} ({self.kind}) is not a {expected_kind}")

        if expected_source and self.source_kind is not expected_source:
            raise RuntimeError(f"Node {self.id} is not a {expected_source.name} node")

        value = getattr(self, attr)
        if value is None:
            raise RuntimeError(f"Node {self.id}: {attr} is not initialized")

        return value

    @property
    def shape(self) -> ShapeSceneExt:
        return self._require("_shape", expected_kind=NodeKind.SHAPE)

    @property
    def ref(self) -> ReferenceNodeExt:
        return self._require("_ref", expected_kind=NodeKind.REFERENCE_NODE)

    @property
    def obj(self) -> bpy.types.Object:
        return cast(bpy.types.Object, self._require("blender_ref", expected_source=SourceKind.OBJECT))

    @property
    def collection(self) -> bpy.types.Collection:
        return cast(bpy.types.Collection, self._require("blender_ref", expected_source=SourceKind.COLLECTION))

    @property
    def effective_source_object_type(self) -> str | None:
        """Object type used for export decisions (honors override when present)."""
        return self.source_object_type_override or self.source_object_type


@dataclass(slots=True)
class IRIndex:
    """Lookup tables built during traversal/resolve.
    These are internal pipeline indexes, not values intended for direct XML emission.
    """

    node_ids_by_blender_ptr: dict[int, list[int]] = field(default_factory=dict)
    mapping_id_by_node_id: dict[int, str] = field(default_factory=dict)
    user_attributes_by_node_id: dict[int, list[UserAttributeEntry]] = field(default_factory=dict)


@dataclass(slots=True)
class ExportIR:
    """Intermediate representation of the export scene graph."""

    scene_nodes: dict[int, SceneNode] = field(default_factory=dict)
    node_order: list[int] = field(default_factory=list)
    index: IRIndex = field(default_factory=IRIndex)

    _children_cache: dict[int | None, list[int]] | None = None
    _roots_cache: list[int] | None = None

    def _invalidate_caches(self) -> None:
        self._children_cache = None
        self._roots_cache = None

    def _index_node_blender_ref(self, node: SceneNode) -> None:
        """Index the node by its Blender reference pointer for quick lookup during resolve."""
        if node.source_ptr is not None:
            self.index.node_ids_by_blender_ptr.setdefault(node.source_ptr, []).append(node.id)

    def _ensure_hierarchy(self) -> None:
        """Build caches for parent-child relationships if not already built."""
        if self._children_cache is not None and self._roots_cache is not None:
            return

        children: dict[int | None, list[int]] = {None: []}
        roots: list[int] = []

        for node_id in self.node_order:
            children[node_id] = []

        for node_id in self.node_order:
            node = self.scene_nodes[node_id]
            parent_id = node.parent_id

            if parent_id is None or parent_id == node_id or parent_id not in self.scene_nodes:
                roots.append(node_id)
                children[None].append(node_id)
            else:
                children[parent_id].append(node_id)

        self._children_cache = children
        self._roots_cache = roots

    def add_node(self, node: SceneNode, *, parent_id: int | None = None) -> None:
        """Add a node to the IR."""
        if node.id in self.scene_nodes:
            raise RuntimeError(f"Node ID {node.id} already exists in IR")

        if parent_id is not None:
            node.parent_id = parent_id

        self.scene_nodes[node.id] = node
        self.node_order.append(node.id)
        self._index_node_blender_ref(node)
        self._invalidate_caches()

    def attach(self, node_id: int, parent_id: int | None) -> None:
        """Reparent a node. Invalid or cyclic reparenting is ignored instead of corrupting the IR."""
        if node_id not in self.scene_nodes:
            raise KeyError(f"Node ID {node_id} not found in IR")

        if parent_id == node_id:
            return

        current_parent_id = parent_id
        while current_parent_id is not None:
            if current_parent_id == node_id:
                return
            if (parent := self.scene_nodes.get(current_parent_id)) is None:
                break

            current_parent_id = parent.parent_id

        node = self.scene_nodes[node_id]
        if node.parent_id == parent_id:
            return

        node.parent_id = parent_id
        self._invalidate_caches()

    def iter_roots(self) -> Iterator[SceneNode]:
        """Iterate root nodes (nodes with no parent)."""
        self._ensure_hierarchy()
        return (self.scene_nodes[node_id] for node_id in self._roots_cache or ())

    def iter_nodes(
        self,
        *,
        kind: NodeKind | None = None,
        source_kind: SourceKind | None = None,
        source_object_type: str | None = None,
        emitted_only: bool = False,
    ) -> Iterator[SceneNode]:
        """Iterate nodes in node_order order, optionally filtering by kind/source and/or emitted status."""
        for node_id in self.node_order:
            node = self.scene_nodes[node_id]
            if kind is not None and node.kind is not kind:
                continue
            if source_kind is not None and node.source_kind is not source_kind:
                continue
            if source_object_type is not None and node.effective_source_object_type != source_object_type:
                continue
            if emitted_only and not node.emit:
                continue

            yield node

    def children_ids(self, parent_id: int) -> tuple[int, ...]:
        """Return the IDs of the children of the given parent node."""
        self._ensure_hierarchy()
        return tuple((self._children_cache or {}).get(parent_id, ()))

    def emitted_child_ids(self, node_id: int | None) -> list[int]:
        """Return emitted children, flattening non-emitted grouping nodes."""
        self._ensure_hierarchy()

        result: list[int] = []
        for child_id in (self._children_cache or {}).get(node_id, ()):
            child = self.scene_nodes[child_id]
            if child.emit:
                result.append(child_id)
            else:
                result.extend(self.emitted_child_ids(child_id))

        return result

    def validate_basic(self, *, require_resolved: bool = False) -> None:
        """Validate cheap IR invariants. This is not a full consistency check, but can catch common mistakes early."""
        seen: set[int] = set()

        for node_id in self.node_order:
            if node_id in seen:
                raise RuntimeError(f"Node ID {node_id} appears multiple times in node_order")
            seen.add(node_id)

            if node_id not in self.scene_nodes:
                raise RuntimeError(f"Node ID {node_id} exists in node_order but not scene_nodes")

        missing_from_order = set(self.scene_nodes) - seen
        if missing_from_order:
            raise RuntimeError(f"Nodes missing from node_order: {sorted(missing_from_order)}")

        for node in self.scene_nodes.values():
            if node.parent_id is not None and node.parent_id not in self.scene_nodes:
                raise RuntimeError(f"Node {node.id} has missing parent {node.parent_id}")

            if node.parent_id == node.id:
                raise RuntimeError(f"Node {node.id} cannot be its own parent")

            if node.kind is NodeKind.SHAPE and node._shape is None:
                raise RuntimeError(f"Shape node {node.id} has no shape extension")

            if node.kind is NodeKind.REFERENCE_NODE and node._ref is None:
                raise RuntimeError(f"Reference node {node.id} has no reference extension")

            if require_resolved and node.kind is NodeKind.UNRESOLVED:
                raise RuntimeError(f"Node {node.id} is still unresolved")
