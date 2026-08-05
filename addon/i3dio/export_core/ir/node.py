from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, StrEnum, auto
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    import bpy
    from mathutils import Matrix


class NodeKind(StrEnum):
    TRANSFORM_GROUP = "TransformGroup"
    REFERENCE_NODE = "ReferenceNode"
    SHAPE = "Shape"
    LIGHT = "Light"
    CAMERA = "Camera"

    # Temporary kind used after traversal, before resolve/kinds has classified the node.
    UNRESOLVED = "__UNRESOLVED__"


class SourceKind(Enum):
    OBJECT = auto()
    COLLECTION = auto()
    BONE = auto()
    OTHER = auto()


@dataclass(frozen=True, slots=True)
class BoneRef:
    """Reference to a bone inside an armature object."""

    armature_obj: bpy.types.Object
    bone_name: str

    @property
    def name(self) -> str:
        return self.bone_name


if TYPE_CHECKING:
    BlenderRef = bpy.types.Object | bpy.types.Collection | BoneRef
else:
    BlenderRef = Any


@dataclass(frozen=True, slots=True)
class ObjectSource:
    kind: ClassVar[SourceKind] = SourceKind.OBJECT

    blender_ref: bpy.types.Object
    blender_ptr: int | None = None
    object_type: str | None = None

    @classmethod
    def from_object(cls, obj: bpy.types.Object) -> ObjectSource:
        return cls(blender_ref=obj, blender_ptr=obj.as_pointer(), object_type=obj.type)


@dataclass(frozen=True, slots=True)
class CollectionSource:
    kind: ClassVar[SourceKind] = SourceKind.COLLECTION

    blender_ref: bpy.types.Collection
    blender_ptr: int | None = None
    object_type: None = None

    @classmethod
    def from_collection(cls, collection: bpy.types.Collection) -> CollectionSource:
        return cls(blender_ref=collection, blender_ptr=collection.as_pointer())


@dataclass(frozen=True, slots=True)
class BoneSource:
    kind: ClassVar[SourceKind] = SourceKind.BONE

    blender_ref: BoneRef
    blender_ptr: ClassVar[None] = None
    object_type: ClassVar[None] = None


@dataclass(frozen=True, slots=True)
class SyntheticSource:
    kind: ClassVar[SourceKind] = SourceKind.OTHER

    blender_ref: BlenderRef | None = None
    blender_ptr: int | None = None
    object_type: ClassVar[None] = None

    @classmethod
    def from_object(cls, obj: bpy.types.Object) -> SyntheticSource:
        return cls(blender_ref=obj, blender_ptr=obj.as_pointer())


NodeSource = ObjectSource | CollectionSource | BoneSource | SyntheticSource


@dataclass(frozen=True, slots=True)
class UnresolvedPayload:
    kind: ClassVar[NodeKind] = NodeKind.UNRESOLVED


@dataclass(frozen=True, slots=True)
class TransformGroupPayload:
    kind: ClassVar[NodeKind] = NodeKind.TRANSFORM_GROUP


@dataclass(slots=True)
class ShapePayload:
    kind: ClassVar[NodeKind] = NodeKind.SHAPE

    shape_id: int | None = None
    material_ids: list[int] | None = None
    skin_bind_node_ids: list[int] | None = None


@dataclass(slots=True)
class ReferencePayload:
    kind: ClassVar[NodeKind] = NodeKind.REFERENCE_NODE

    reference_id: int | None = None
    runtime_loaded: bool = False
    child_path: str | None = None


@dataclass(frozen=True, slots=True)
class LightPayload:
    kind: ClassVar[NodeKind] = NodeKind.LIGHT


@dataclass(frozen=True, slots=True)
class CameraPayload:
    kind: ClassVar[NodeKind] = NodeKind.CAMERA


NodePayload = UnresolvedPayload | TransformGroupPayload | ShapePayload | ReferencePayload | LightPayload | CameraPayload


@dataclass(slots=True)
class XmlAttrs:
    """Attributes intended for final I3D/XML emission."""

    node: dict[str, Any] = field(default_factory=dict)
    children: dict[str, dict[str, Any]] = field(default_factory=dict)

    def child(self, tag: str) -> dict[str, Any]:
        return self.children.setdefault(tag, {})


@dataclass(slots=True)
class SceneNode:
    """A node in the export scene graph IR.

    The IR stores export intent, not XML directly. Traversal creates mostly unresolved nodes,
    resolve passes classify/fill them, and serializers later consume the finalized state.
    """

    id: int
    name: str
    source: NodeSource
    payload: NodePayload
    parent_id: int | None = None

    matrix_local_export: Matrix | None = None
    emit: bool = True
    attrs: XmlAttrs = field(default_factory=XmlAttrs)
    source_object_type_override: str | None = None

    @property
    def kind(self) -> NodeKind:
        return self.payload.kind
