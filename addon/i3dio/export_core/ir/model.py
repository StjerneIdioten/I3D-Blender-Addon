# i3dio/export_core/ir/model.py
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import Enum, StrEnum, auto
from typing import Any, cast

import bpy
from mathutils import Matrix

from ..blender.bones import BoneRef
from .animation import AnimationIR

BlenderRef = bpy.types.Object | bpy.types.Collection | BoneRef


class NodeKind(StrEnum):
    TRANSFORM_GROUP = "TransformGroup"
    REFERENCE_NODE = "ReferenceNode"
    SHAPE = "Shape"
    LIGHT = "Light"
    CAMERA = "Camera"
    UNRESOLVED = "__UNRESOLVED__"  # placeholder kind used during traversal, should not appear in final IR


class SourceKind(Enum):
    OBJECT = auto()
    COLLECTION = auto()
    BONE_REF = auto()
    OTHER = auto()


@dataclass(slots=True)
class EmitAttrs:
    node: dict[str, Any] = field(default_factory=dict)  # attributes for the node itself (e.g. <IndexedTriangleSet>)
    children: dict[str, dict[str, Any]] = field(default_factory=dict)  # child_name -> attrs (e.g. <Vertices>)

    def child(self, tag: str) -> dict[str, Any]:
        return self.children.setdefault(tag, {})


@dataclass(slots=True)
class ShapeSceneExt:
    shape_id: int | None = None
    # For Shapes in the Scene graph, resolved global export material IDs in subset order.
    # Formatting into the I3D "materialIds" attribute is handled by the serializer.
    material_ids: list[int] | None = None
    # For merge groups / skinned meshes: node ids (not shape ids) that provide skin bind transforms.
    # Formatting into the I3D "skinBindNodeIds" attribute is handled by the serializer.
    skin_bind_node_ids: list[int] | None = None


@dataclass(slots=True)
class ReferenceNodeExt:
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
    """A node in the export scene graph IR."""

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
    # Optional override for export decisions (e.g. CURVE exported as mesh)
    source_object_type_override: str | None = None
    blender_ref: BlenderRef | None = None

    _shape: ShapeSceneExt | None = None
    _ref: ReferenceNodeExt | None = None

    def _require(self, attr: str, expected_kind: NodeKind | None = None, expected_source: SourceKind | None = None):
        if expected_kind and self.kind is not expected_kind:
            raise RuntimeError(f"Node {self.id} (kind={self.kind}) is not a {expected_kind.name}")
        if expected_source and self.source_kind is not expected_source:
            raise RuntimeError(f"Node {self.id} is not a {expected_source.name} node")
        val = getattr(self, attr)
        if val is None:
            raise RuntimeError(f"Node {self.id}: {attr} is None (not initialized)")
        return val

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
    def bone_ref(self) -> BoneRef:
        return cast(BoneRef, self._require("blender_ref", expected_source=SourceKind.BONE_REF))

    @property
    def effective_source_object_type(self) -> str | None:
        """Object type used for export decisions (honors override when present)."""
        return self.source_object_type_override or self.source_object_type


@dataclass(slots=True)
class IRIndex:
    """
    Internal lookup tables built during traversal/resolve.
    Not user-facing XML attrs; keep them stable and deterministic.
    """

    node_id_by_blender_ptr: dict[int, list[int]] = field(default_factory=dict)  # blender_ref ptr -> node_id
    merge_children_roots: list[int] = field(default_factory=list)  # node ids
    merge_group_nodes_by_index: dict[int, list[int]] = field(default_factory=dict)  # mg_index -> [node ids]
    # Armature object ptr -> {bone_name: bone_node_id} (built in resolve_armatures)
    bone_nodes_by_armature_ptr: dict[int, dict[str, int]] = field(default_factory=dict)
    mapping_id_by_node_id: dict[int, str] = field(default_factory=dict)  # node_id -> i3dMapping id
    user_attributes_by_node_id: dict[int, list[UserAttributeEntry]] = field(default_factory=dict)


@dataclass(slots=True)
class ExportIR:
    """Intermediate representation of the export scene graph.

    Built during traversal, consumed by resolve and serialization.

    Notes:
    - parent_id is the single source of truth for hierarchy.
    - Hierarchy caches are built lazily and invalidated on mutations.
    - node_order preserves deterministic traversal/output ordering.
    """

    scene_nodes: dict[int, SceneNode] = field(default_factory=dict)
    node_order: list[int] = field(default_factory=list)  # node ids in creation order (stable)
    index: IRIndex = field(default_factory=IRIndex)

    animations: AnimationIR = field(default_factory=AnimationIR)

    # Caches for fast hierarchy queries (built-on-demand)
    _children_cache: dict[int | None, list[int]] | None = None  # parent_id -> [child_ids]
    _roots_cache: list[int] | None = None  # cached root node ids (parent_id=None)

    # Cache management
    def _invalidate_caches(self) -> None:
        self._roots_cache = None
        self._children_cache = None

    def _ensure_hierarchy(self) -> None:
        """Build hierarchy caches from current parent_id relationships."""
        if self._roots_cache is not None and self._children_cache is not None:
            return

        children: dict[int | None, list[int]] = {None: []}
        roots: list[int] = []

        # Make deterministic: build using node_order (not dict iteration)
        for nid in self.node_order:
            children[nid] = []

        for nid in self.node_order:
            node = self.scene_nodes[nid]
            pid = node.parent_id

            # Safeguard policy:
            # - pid is None -> root
            # - pid missing -> treat as root (best-effort)
            # - pid == nid -> treat as root (self-parent)
            if pid is None or pid == nid or pid not in self.scene_nodes:
                roots.append(nid)
                children[None].append(nid)
            else:
                children[pid].append(nid)

        self._roots_cache = roots
        self._children_cache = children

    # Mutations
    def _index_node_blender_ref(self, node: SceneNode) -> None:
        """Index node by its Blender reference pointer (if any)."""
        if (ptr := node.source_ptr) is not None:
            self.index.node_id_by_blender_ptr.setdefault(ptr, []).append(node.id)

    def add_node(self, node: SceneNode, *, parent_id: int | None = None) -> None:
        """Add a pre-created SceneNode into the IR."""
        if node.id in self.scene_nodes:
            raise RuntimeError(f"Node ID {node.id} already exists in IR")
        if parent_id is not None:
            node.parent_id = parent_id
        self.scene_nodes[node.id] = node
        self.node_order.append(node.id)
        self._index_node_blender_ref(node)
        self._invalidate_caches()

    def attach(self, node_id: int, parent_id: int | None) -> None:
        """Change a node's parent (reparent operation). No-op if the parent is unchanged or would create a cycle."""
        if node_id not in self.scene_nodes:
            raise KeyError(f"Node ID {node_id} not found in IR")

        if parent_id == node_id:
            return

        # Cycle check (walk up ancestors starting at proposed parent)
        pid = parent_id
        while pid is not None:
            if pid == node_id:
                return  # cycle detected
            p = self.scene_nodes.get(pid)
            if p is None:
                break  # missing parent in chain (best-effort)
            pid = p.parent_id

        n = self.scene_nodes[node_id]
        if n.parent_id == parent_id:
            return
        n.parent_id = parent_id
        self._invalidate_caches()

    # Queries
    def iter_roots(self) -> Iterator[SceneNode]:
        """Iterate over root nodes (parent_id=None)."""
        self._ensure_hierarchy()
        return (self.scene_nodes[rid] for rid in self._roots_cache)

    def iter_nodes(
        self,
        *,
        kind: NodeKind | None = None,
        source_kind: SourceKind | None = None,
        source_object_type: str | None = None,
        emitted_only: bool = False,
    ) -> Iterator[SceneNode]:
        """Iterate nodes in deterministic creation order."""
        for node_id in self.node_order:
            n = self.scene_nodes[node_id]
            if kind is not None and n.kind is not kind:
                continue
            if source_kind is not None and n.source_kind is not source_kind:
                continue
            if source_object_type is not None and n.effective_source_object_type != source_object_type:
                continue
            if emitted_only and not n.emit:
                continue
            yield n

    def children_ids(self, parent_id: int) -> tuple[int, ...]:
        """Get direct child node IDs (no emit filtering)."""
        self._ensure_hierarchy()
        return tuple(self._children_cache.get(parent_id, ()))

    def emitted_child_ids(self, node_id: int | None) -> list[int]:
        """Get child IDs to emit, flattening emit=False nodes recursively.

        - node_id=None returns emitted root ids (flattening non-emitted roots).
        - preserves deterministic sibling order.
        """
        self._ensure_hierarchy()
        result: list[int] = []
        for cid in self._children_cache.get(node_id, []):
            if self.scene_nodes[cid].emit:
                result.append(cid)
            else:
                result.extend(self.emitted_child_ids(cid))
        return result
