from __future__ import annotations

from typing import TYPE_CHECKING
from xml.sax.saxutils import quoteattr

from ... import xml_i3d

if TYPE_CHECKING:
    from ..geometry.mesh.its import BuiltITS

CHUNK_LINES = 30_000  # number of lines to buffer before writing to file, more or less a random guess


def write_its_stream(f, built: BuiltITS, indent: str = "    ") -> None:
    positions = built.positions
    normals = built.normals
    uvs = built.uvs
    color = built.color
    g = built.g
    bi = built.bi
    bw = built.bw
    bi4 = built.bi4
    indices = built.indices

    vcount = int(positions.shape[0])
    tri_count = int(indices.size // 3)

    # Localize lookups (can be a bit faster)
    write_open = xml_i3d.write_open_tag
    write_close = xml_i3d.write_close_tag

    write = f.write

    ind_tag = indent
    ind_child = indent + "  "  # 2 spaces deeper (matches your open-tag usage)
    ind_line = indent + "    "  # lines under Vertices/Triangles

    # <IndexedTriangleSet ...>
    its_attrs: dict[str, object] = {"name": built.name, "shapeId": built.shape_id, **built.attrs.node}
    write_open(f, "IndexedTriangleSet", its_attrs, indent=ind_tag)

    # <Vertices ...>
    v_attrs: dict[str, object] = {"count": vcount, "normal": True}
    for li in range(len(uvs)):
        v_attrs[f"uv{li}"] = True
    if color is not None:
        v_attrs["color"] = True
    v_attrs.update(built.attrs.children.get("Vertices", {}))
    write_open(f, "Vertices", v_attrs, indent=ind_child)

    # vertices: chunked writing
    chunk: list[str] = []
    append = chunk.append
    uv_layers = uvs  # local alias
    uv_count = len(uv_layers)

    # Noticably faster than using for loop range over uv_count on a dense mesh
    uv0 = uv_layers[0] if uv_count > 0 else None
    uv1 = uv_layers[1] if uv_count > 1 else None
    uv2 = uv_layers[2] if uv_count > 2 else None
    uv3 = uv_layers[3] if uv_count > 3 else None

    for i in range(vcount):
        p = positions[i]
        n = normals[i]

        # Build with in-line formatting, faster than calling any external function
        line = f'{ind_line}<v p="{p[0]:.6g} {p[1]:.6g} {p[2]:.6g}" n="{n[0]:.6g} {n[1]:.6g} {n[2]:.6g}"'
        if uv0 is not None:
            uv = uv0[i]
            line += f' t0="{uv[0]:.6g} {uv[1]:.6g}"'
        if uv1 is not None:
            uv = uv1[i]
            line += f' t1="{uv[0]:.6g} {uv[1]:.6g}"'
        if uv2 is not None:
            uv = uv2[i]
            line += f' t2="{uv[0]:.6g} {uv[1]:.6g}"'
        if uv3 is not None:
            uv = uv3[i]
            line += f' t3="{uv[0]:.6g} {uv[1]:.6g}"'
        if color is not None:
            col = color[i]
            line += f' c="{col[0]:.6g} {col[1]:.6g} {col[2]:.6g} {col[3]:.6g}"'
        # generic have priority over merge group and skinning
        if g is not None:
            line += f' g="{g[i]:.9g}"'
        # merge group have priority over skinning
        elif bi is not None:
            line += f' bi="{bi[i]:d}"'
        elif bw is not None and bi4 is not None:
            w = bw[i]
            ii = bi4[i]
            line += (
                f' bw="{w[0]:.9g} {w[1]:.9g} {w[2]:.9g} {w[3]:.9g}"'
                f' bi="{int(ii[0])} {int(ii[1])} {int(ii[2])} {int(ii[3])}"'
            )

        line += " />\n"
        append(line)

        if len(chunk) >= CHUNK_LINES:
            write("".join(chunk))
            chunk.clear()

    if chunk:
        write("".join(chunk))
        chunk.clear()

    write_close(f, "Vertices", indent=ind_child)

    # <Triangles ...>
    write_open(f, "Triangles", {"count": tri_count}, indent=ind_child)

    # Avoid reshape + row iteration + int() calls
    flat = indices.ravel()
    for j in range(0, flat.size, 3):
        a = flat[j]
        b = flat[j + 1]
        c = flat[j + 2]
        append(f'{ind_line}<t vi="{a} {b} {c}" />\n')
        if len(chunk) >= CHUNK_LINES:
            write("".join(chunk))
            chunk.clear()

    if chunk:
        write("".join(chunk))
        chunk.clear()
    write_close(f, "Triangles", indent=ind_child)

    # <Subsets ...>
    write_open(f, "Subsets", {"count": len(built.subsets)}, indent=ind_child)
    for s in built.subsets:
        slot_attr = f" materialSlotName={quoteattr(s.material_slot_name)}" if s.material_slot_name else ""
        write(
            f'{ind_line}<Subset firstIndex="{s.first_index:d}" '
            f'numVertices="{s.num_vertices:d}" firstVertex="{s.first_vertex:d}" '
            f'numIndices="{s.num_indices:d}"{slot_attr} />\n'
        )
    write_close(f, "Subsets", indent=ind_child)

    write_close(f, "IndexedTriangleSet", indent=ind_tag)
