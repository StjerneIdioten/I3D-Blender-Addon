from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import bpy


@dataclass(frozen=True, slots=True)
class ObjectScope:
    objects: tuple[bpy.types.Object, ...]
    include_children: bool = False


@dataclass(frozen=True, slots=True)
class CollectionScope:
    collection: bpy.types.Collection


ExportScope = ObjectScope | CollectionScope
