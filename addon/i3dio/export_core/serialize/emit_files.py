from __future__ import annotations

from typing import TYPE_CHECKING

from ... import xml_i3d

if TYPE_CHECKING:
    from ..ctx import ExportContext


def emit_files(ctx: "ExportContext", files_elem) -> None:
    """
    Write <Files> entries from ctx.files.
    Expects resolve_files() to have run so each entry has resolved_path.
    """
    for e in ctx.files.entries():
        if e.resolved_path is None:
            continue
        # filename is the resolved (export) path
        xml_i3d.SubElementA(files_elem, "File", {"fileId": e.id, "filename": e.resolved_path.as_posix()})
