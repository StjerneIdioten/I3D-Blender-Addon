# i3dio/export_core/geometry/mesh/subsets.py
from __future__ import annotations

import numpy as np

from .its import BuiltSubset


def build_indices_and_subsets(
    tri_loops: np.ndarray,  # (T,3) int32
    tri_mat_id: np.ndarray,  # (T,) int32 (material keys)
    total_vertices: int,
) -> tuple[np.ndarray, list[BuiltSubset]]:
    """
    Group triangles by material key in first-seen order (stable), producing:
      - flat indices array
      - subsets (each subset has material_id)
    """
    if tri_loops.size == 0:
        return np.empty((0,), dtype=np.int32), []

    # Unique materials, and for each triangle: which unique-index it maps to
    mats, first_idx, inv = np.unique(tri_mat_id, return_index=True, return_inverse=True)

    # Order unique mats by first appearance
    order_u = np.argsort(first_idx)

    # Map unique-index -> "first-seen rank" (0..M-1)
    rank_of_u = np.empty_like(order_u)
    rank_of_u[order_u] = np.arange(order_u.size, dtype=rank_of_u.dtype)

    # Rank for each triangle, then stable-sort triangles by rank
    tri_rank = rank_of_u[inv]  # (T,)
    tri_sort = np.argsort(tri_rank, kind="stable")  # (T,)

    tri_sorted = tri_loops[tri_sort]  # (T,3)
    indices = tri_sorted.reshape(-1)  # (3*T,)

    # Counts per rank (triangles)
    tri_counts = np.bincount(tri_rank, minlength=order_u.size)  # (M,)

    subsets: list[BuiltSubset] = []
    write = 0
    for r, tcount in enumerate(tri_counts):
        if tcount == 0:
            continue
        n = int(tcount) * 3  # indices

        # All subsets share the global vertex buffer (firstVertex=0, numVertices=total).
        # Deduplication is global, not per-subset, maximizing vertex reuse across materials.
        # i3dConverter.exe will optimize the binary .i3d.shapes format as needed.
        subsets.append(
            BuiltSubset(
                first_index=write,
                num_indices=n,
                first_vertex=0,
                num_vertices=total_vertices,
                material_id=int(mats[order_u[r]]),
            )
        )
        write += n

    return indices, subsets
