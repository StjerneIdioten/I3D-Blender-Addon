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


@dataclass(frozen=True, slots=True)
class MaterialKey:
    material_ptr: int  # 0 for None/export-side default material
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
        return "Normalmap" in self.attrs.children or any("tangent" in attr.name.lower() for attr in req_attrs)

    def requires_vcol(self) -> bool:
        """Return True if this material requires vertex colors."""
        if (mat := self.blender_material) is None:
            return False
        return any("color" in attr.name.lower() for attr in mat.i3d_attributes.required_vertex_attributes)

    def get_slot_name(self) -> str | None:
        """Return the optional materialSlotName, or None if disabled."""
        if (mat := self.blender_material) is None:
            return None
        i3d_attrs = mat.i3d_attributes
        if not i3d_attrs.use_material_slot_name:
            return None
        return i3d_attrs.material_slot_name or mat.name


@dataclass(slots=True)
class MaterialTable(IdEntryTable[MaterialKey, MaterialEntry]):
    """Deduplicates materials and provides stable material IDs."""

    ctx: ExportContext
    _default_id: int | None = field(default=None, init=False, repr=False)

    def _make_entry(
        self, *, key: MaterialKey, blender_material: bpy.types.Material | None
    ) -> tuple[int, MaterialEntry]:
        mid = self.ctx.ids.alloc(IdKind.MATERIAL)
        return mid, MaterialEntry(id=mid, key=key, blender_material=blender_material)

    def _make_key(self, mat: bpy.types.Material | None, export_name: str | None) -> MaterialKey:
        if mat is None:
            return MaterialKey(0, export_name or DEFAULT_MATERIAL_NAME)
        return MaterialKey(mat.as_pointer(), export_name or mat.name)

    @property
    def default_id(self) -> int:
        if self._default_id is None:
            self._default_id = self.get_or_add(None, export_name=DEFAULT_MATERIAL_NAME)
        return self._default_id

    def get_or_add(self, mat: bpy.types.Material | None, *, export_name: str | None = None) -> int:
        key = self._make_key(mat, export_name)
        mat_id, _, _ = self.get_or_create(key, lambda: self._make_entry(key=key, blender_material=mat))

        if mat is None and key.export_name == DEFAULT_MATERIAL_NAME:
            self._default_id = mat_id
        return mat_id
