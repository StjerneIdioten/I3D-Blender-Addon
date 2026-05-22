from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from ..ids import IdKind
from .base import IdEntryTable

if TYPE_CHECKING:
    from ..ctx import ExportContext


FileKind = Literal["image", "shader", "reference", "generic"]


_MODHUB_FOLDER: dict[FileKind, str] = {
    "image": "textures",
    "shader": "shaders",
    "reference": "assets",
    "generic": "",
}


@dataclass(slots=True)
class FileEntry:
    id: int
    kind: FileKind
    blender_path: str  # as stored in Blender (relative, //, or absolute)
    resolved_path: Path | None = None  # export-side path ($data..., relative to i3d folder, or absolute)


@dataclass(slots=True)
class FileTable(IdEntryTable[FileEntry, tuple[FileKind, str]]):
    """
    Responsibilities:
      - de-duplicate file registrations and provide stable file IDs
      - finalize() resolves each file path for export and optionally copies it
    """

    ctx: ExportContext
    _by_key: dict[tuple[FileKind, str], int] = field(default_factory=dict)
    _entries: dict[int, FileEntry] = field(default_factory=dict)

    def _alloc_entry(self, *, key: tuple[FileKind, str], kind: FileKind, blender_path: str) -> FileEntry:
        fid = self.ctx.ids.alloc(IdKind.FILE)
        entry = FileEntry(id=fid, kind=kind, blender_path=blender_path)
        self.register(key=key, entry_id=fid, entry=entry)
        return entry

    def add(self, *, kind: FileKind, blender_path: str) -> int:
        key = (kind, blender_path)
        if (fid := self.get_id(key)) is not None:
            return fid
        return self._alloc_entry(key=key, kind=kind, blender_path=blender_path).id

    def add_reference(self, blender_path: str) -> int:
        return self.add(kind="reference", blender_path=blender_path)

    def add_image(self, blender_path: str) -> int:
        return self.add(kind="image", blender_path=blender_path)

    def add_shader(self, blender_path: str) -> int:
        return self.add(kind="shader", blender_path=blender_path)
