from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import bpy

from ..ids import IdKind
from ..ir import EmitAttrs
from .base import IdEntryTable

if TYPE_CHECKING:
    from ..ctx import ExportContext

DEFAULT_MATERIAL_NAME = "i3d_default_material"


# ──────────────────────────────────────────────────────────────────────────────
# Material model types
# ──────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class MaterialKey:
    material_ptr: int  # 0 for None/export side only
    export_name: str  # final Material@name (slot override or datablock name)


@dataclass(slots=True)
class MaterialEntry:
    id: int
    key: MaterialKey
    blender_material: bpy.types.Material | None
    attrs: EmitAttrs = field(default_factory=EmitAttrs)
    extra_children: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    def requires_tangents(self) -> bool:
        """Return True if tangent export is required for this material."""
        if (mat := self.blender_material) is None:
            return False
        req_attrs = mat.i3d_attributes.required_vertex_attributes
        return "Normalmap" in self.attrs.children or any(req.name == "tangent" for req in req_attrs)

    def requires_vcol(self) -> bool:
        """Return True if this material requires vertex colors."""
        if (mat := self.blender_material) is None:
            return False
        return any("color" in attr.name.lower() for attr in mat.i3d_attributes.required_vertex_attributes)

    def get_slot_name(self) -> str | None:
        """Return the optional materialSlotName (or None if disabled)."""
        if (mat := self.blender_material) is None:
            return None
        if mat.i3d_attributes.use_material_slot_name:
            return mat.i3d_attributes.material_slot_name or mat.name
        return None


# ──────────────────────────────────────────────────────────────────────────────
# Material table (registry)
# ──────────────────────────────────────────────────────────────────────────────


@dataclass(slots=True)
class MaterialTable(IdEntryTable[MaterialEntry, MaterialKey]):
    ctx: "ExportContext"
    _by_key: dict[MaterialKey, int] = field(default_factory=dict)
    _entries: dict[int, MaterialEntry] = field(default_factory=dict)
    _default_id: int | None = None

    def _alloc_entry(self, *, key: MaterialKey, blender_material: bpy.types.Material | None) -> MaterialEntry:
        mid = self.ctx.ids.alloc(IdKind.MATERIAL)
        entry = MaterialEntry(id=mid, key=key, blender_material=blender_material)
        self.register(key=key, entry_id=mid, entry=entry)
        return entry

    def get_default_id(self) -> int:
        if self._default_id is None:
            self._default_id = self.get_or_add(None, export_name=DEFAULT_MATERIAL_NAME)
        return self._default_id

    def get_or_add(self, mat: bpy.types.Material | None, *, export_name: str | None = None) -> int:
        """
        Get or add a material entry by Blender material and optional export name override.
        If mat is None, a default material entry is used/created.
        """
        if mat is None:
            name = export_name or DEFAULT_MATERIAL_NAME
            key = MaterialKey(0, name)

            if (mid := self.get_id(key)) is not None:
                if name == DEFAULT_MATERIAL_NAME:
                    self._default_id = mid
                return mid
            entry = self._alloc_entry(key=key, blender_material=None)
            if name == DEFAULT_MATERIAL_NAME:
                self._default_id = entry.id
            return entry.id

        name = export_name or mat.name
        key = MaterialKey(mat.as_pointer(), name)
        if (mid := self.get_id(key)) is not None:
            return mid

        return self._alloc_entry(key=key, blender_material=mat).id
