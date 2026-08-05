from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .node import NodeKind, SceneNode, SourceKind

if TYPE_CHECKING:
    import bpy


@dataclass(slots=True)
class ExportIR:
    """Intermediate representation of the export scene graph."""

    scene_nodes: dict[int, SceneNode] = field(default_factory=dict)
    node_order: list[int] = field(default_factory=list)

    _node_ids_by_blender_ptr: dict[int, list[int]] = field(default_factory=dict, init=False, repr=False)
    _children_by_parent_cache: dict[int | None, list[int]] | None = field(default=None, init=False, repr=False)

    def _invalidate_children_cache(self) -> None:
        self._children_by_parent_cache = None

    def _index_node_blender_ptr(self, node: SceneNode) -> None:
        """Index the node by its Blender data-block pointer for quick lookup during resolve."""
        if node.source.blender_ptr is not None:
            self._node_ids_by_blender_ptr.setdefault(node.source.blender_ptr, []).append(node.id)

    def _children_by_parent(self) -> dict[int | None, list[int]]:
        """Return cached parent-child relationships, keyed by parent node ID."""
        if self._children_by_parent_cache is not None:
            return self._children_by_parent_cache

        children: dict[int | None, list[int]] = {None: []}

        for node_id in self.node_order:
            children[node_id] = []

        for node_id in self.node_order:
            node = self.scene_nodes[node_id]
            parent_id = node.parent_id

            if parent_id is None or parent_id == node_id or parent_id not in self.scene_nodes:
                children[None].append(node_id)
            else:
                children[parent_id].append(node_id)

        self._children_by_parent_cache = children
        return children

    def node_ids_for(self, datablock: bpy.types.ID) -> tuple[int, ...]:
        """Return all scene nodes that reference the given Blender data-block."""
        return tuple(self._node_ids_by_blender_ptr.get(datablock.as_pointer(), ()))

    def nodes_for(self, datablock: bpy.types.ID) -> tuple[SceneNode, ...]:
        """Return all scene nodes referencing the given Blender data-block."""
        return tuple(self.scene_nodes[node_id] for node_id in self.node_ids_for(datablock))

    def add_node(self, node: SceneNode) -> None:
        """Add a node to the IR."""
        if node.id in self.scene_nodes:
            raise RuntimeError(f"Node ID {node.id} already exists in IR")

        if node.parent_id == node.id:
            raise ValueError(f"Node {node.id} cannot parent itself")

        if node.parent_id is not None and node.parent_id not in self.scene_nodes:
            raise KeyError(f"Parent node ID {node.parent_id} not found in IR")

        self.scene_nodes[node.id] = node
        self.node_order.append(node.id)
        self._index_node_blender_ptr(node)
        self._invalidate_children_cache()

    def attach(self, node_id: int, parent_id: int | None) -> None:
        """Reparent a node, rejecting missing nodes and invalid relationships."""
        if node_id not in self.scene_nodes:
            raise KeyError(f"Node ID {node_id} not found in IR")

        if parent_id == node_id:
            raise ValueError(f"Node {node_id} cannot parent itself")

        if parent_id is not None and parent_id not in self.scene_nodes:
            raise KeyError(f"Parent node ID {parent_id} not found in IR")

        current_parent_id = parent_id
        while current_parent_id is not None:
            if current_parent_id == node_id:
                raise ValueError(f"Attaching node {node_id} to {parent_id} would create a cycle")
            current_parent_id = self.scene_nodes[current_parent_id].parent_id

        node = self.scene_nodes[node_id]
        if node.parent_id == parent_id:
            return

        node.parent_id = parent_id
        self._invalidate_children_cache()

    def iter_roots(self) -> Iterator[SceneNode]:
        """Iterate root nodes (nodes with no parent)."""
        return (self.scene_nodes[node_id] for node_id in self._children_by_parent()[None])

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
            if source_kind is not None and node.source.kind is not source_kind:
                continue
            object_type = node.source_object_type_override or node.source.object_type
            if source_object_type is not None and object_type != source_object_type:
                continue
            if emitted_only and not node.emit:
                continue

            yield node

    def children_ids(self, parent_id: int) -> tuple[int, ...]:
        """Return the IDs of the children of the given parent node."""
        return tuple(self._children_by_parent().get(parent_id, ()))

    def emitted_child_ids(self, node_id: int | None) -> list[int]:
        """Return emitted children, flattening non-emitted grouping nodes."""
        result: list[int] = []
        for child_id in self._children_by_parent().get(node_id, ()):
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
                raise KeyError(f"Parent node {node.parent_id} does not exist")

            if node.parent_id == node.id:
                raise ValueError(f"Node {node.id} cannot parent itself")

            if require_resolved and node.kind is NodeKind.UNRESOLVED:
                raise RuntimeError(f"Node {node.id} is still unresolved")
