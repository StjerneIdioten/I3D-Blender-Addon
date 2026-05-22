from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from xml.sax.saxutils import quoteattr

import bpy

from ... import xml_i3d

if TYPE_CHECKING:
    from ..ctx import ExportContext


OPEN_TAG = "<i3dMappings>"
CLOSE_TAG = "</i3dMappings>"
INDENT_STEP = " " * 4


def _detect_newline(lines: list[str]) -> str:
    return "\r\n" if any(line.endswith("\r\n") for line in lines) else "\n"


def _leading_ws(line: str, default: str = INDENT_STEP) -> str:
    stripped = line.lstrip(" \t")
    return line[: len(line) - len(stripped)] or default


def _find_or_insert_i3d_mappings_block(ctx: ExportContext, lines: list[str]) -> tuple[int, int, str] | None:
    """
    Ensure `<i3dMappings> ... </i3dMappings>` exists and return (open_idx, close_idx, base_indent).
    Inserts the block just before the last closing XML tag if missing.
    """
    rep = ctx.reporter("i3dMappings")

    def _is_closing_tag(line: str) -> bool:
        s = line.strip()
        return s.startswith("</") and s.endswith(">")

    open_i = next((i for i, line in enumerate(lines) if line.strip().startswith(OPEN_TAG)), None)

    # Missing block -> insert before last closing tag
    if open_i is None:
        last_close_i = next((i for i in range(len(lines) - 1, -1, -1) if _is_closing_tag(lines[i])), None)
        if last_close_i is None:
            rep.warning("Could not locate a root closing tag; aborting.")
            return None

        nl = _detect_newline(lines)
        base_indent = _leading_ws(lines[last_close_i])

        open_i = last_close_i
        lines.insert(open_i, f"{base_indent}{OPEN_TAG}{nl}")
        lines.insert(open_i + 1, f"{base_indent}{CLOSE_TAG}{nl}")
        return open_i, open_i + 1, base_indent

    base_indent = _leading_ws(lines[open_i])

    close_i = next((i for i in range(open_i + 1, len(lines)) if lines[i].strip().startswith(CLOSE_TAG)), None)
    if close_i is None:
        rep.warning("%s found but no closing tag; aborting.", OPEN_TAG)
        return None

    return open_i, close_i, base_indent


def _iter_mapped_entries_preorder(ctx: "ExportContext"):
    """
    Yield (mapping_id, i3d_index_path) in root-first preorder.

    i3d_index_path format:
      root: "0>"
      child: "0>2"
      grandchild: "0>2|1"
    """
    stack: list[tuple[int, str]] = [(root.id, f"{i}>") for i, root in reversed(list(enumerate(ctx.ir.iter_roots())))]
    mapped = ctx.ir.index.mapping_id_by_node_id

    while stack:
        nid, path = stack.pop()
        if (mapping_id := mapped.get(nid)) is not None:
            yield mapping_id, path

        child_ids = ctx.ir.emitted_child_ids(nid)
        sep = "" if path.endswith(">") else "|"
        for child_i, child_id in reversed(list(enumerate(child_ids))):
            stack.append((child_id, f"{path}{sep}{child_i}"))


def emit_i3d_mappings(ctx: "ExportContext") -> None:
    rep = ctx.reporter("i3dMappings")

    if not (file_path_raw := ctx.setting("i3d_mapping_file_path", "")):
        return

    file_path = Path(bpy.path.abspath(file_path_raw))
    if not file_path.exists():
        rep.warning("file not found: %r", str(file_path))
        return

    if not (mapped := list(_iter_mapped_entries_preorder(ctx))):
        rep.debug("No nodes with i3d_mapping attribute; skipping.")
        return

    with file_path.open("r", encoding="utf-8") as f:
        text = f.read()

    try:  # Only used to validate XML, don't write with ET (formatting changes)
        xml_i3d.ET.fromstring(text)
    except xml_i3d.ET.ParseError as e:
        rep.warning("Can't update %r: the file isn't valid XML, i3dMappings was not written. (%s)", file_path.name, e)
        return

    lines = text.splitlines(keepends=True)
    if (block := _find_or_insert_i3d_mappings_block(ctx, lines)) is None:
        return
    open_i, close_i, base_indent = block

    entry_indent = base_indent + INDENT_STEP
    nl = _detect_newline(lines)
    new_entries = [f'{entry_indent}<i3dMapping id={quoteattr(mid)} node="{path}" />{nl}' for mid, path in mapped]

    lines[open_i + 1 : close_i] = new_entries
    file_path.write_text("".join(lines), encoding="utf-8")
    rep.debug("Wrote %d entries to %r", len(new_entries), str(file_path))
