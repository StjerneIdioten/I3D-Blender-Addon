from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal

from ..ids import IdKind
from .base import IdEntryTable

if TYPE_CHECKING:
    from ..ctx import ExportContext


FileKind = Literal["image", "shader", "reference", "generic"]
FileKey = tuple[FileKind, str]


MODHUB_FOLDER: Final[Mapping[FileKind, str]] = {
    "image": "textures",
    "shader": "shaders",
    "reference": "assets",
    "generic": "",
}


@dataclass(slots=True)
class FileEntry:
    id: int
    kind: FileKind
    # Path/reference as stored in Blender, e.g. "//textures/foo.dds", absolute path, or "$data/..."
    blender_path: str
    # Real disk path used for validation/copying. None if it cannot be resolved.
    source_path: Path | None = None
    # Final reference written to the I3D XML, e.g. "textures/foo.dds" or "$data/shared/foo.dds".
    export_path: str | None = None


@dataclass(slots=True)
class FileTable(IdEntryTable[FileKey, FileEntry]):
    """Deduplicates file references and provides stable file IDs."""

    ctx: ExportContext

    def _make_entry(self, *, kind: FileKind, blender_path: str) -> tuple[int, FileEntry]:
        file_id = self.ctx.ids.alloc(IdKind.FILE)
        return file_id, FileEntry(id=file_id, kind=kind, blender_path=blender_path)

    def add(self, *, kind: FileKind, blender_path: str) -> int:
        key = (kind, blender_path)
        file_id, _, _ = self.get_or_create(key, lambda: self._make_entry(kind=kind, blender_path=blender_path))
        return file_id

    def add_image(self, blender_path: str) -> int:
        return self.add(kind="image", blender_path=blender_path)

    def add_shader(self, blender_path: str) -> int:
        return self.add(kind="shader", blender_path=blender_path)

    def add_reference(self, blender_path: str) -> int:
        return self.add(kind="reference", blender_path=blender_path)

    def add_generic(self, blender_path: str) -> int:
        return self.add(kind="generic", blender_path=blender_path)
