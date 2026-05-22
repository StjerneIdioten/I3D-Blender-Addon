from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from math import tau

import bpy
import mathutils
import numpy as np
from bpy_extras.io_utils import axis_conversion

from ... import debugging
from ...utility import sort_blender_objects_by_outliner_ordering

# Convert matrix from Blender to Giants coordinate system
CONVERSION_MATRIX: mathutils.Matrix = axis_conversion(to_forward='-Z', to_up='Y').to_4x4()
CONVERSION_MATRIX_INVERSE = CONVERSION_MATRIX.inverted()

LogSink = logging.Logger | logging.LoggerAdapter


@dataclass(frozen=True, slots=True)
class MPAConfig:
    include_position: bool
    include_rotation: bool
    include_scale: bool
    use_geometry_nodes: bool
    is_cyclic: bool
    hide_first_and_last: bool


def collect_motion_path_array(
    obj: bpy.types.Object, depsgraph: bpy.types.Depsgraph, *, logger: LogSink | None = None
) -> np.ndarray | None:
    """Collect + pack Motion Path Array data for DDS writing.

    Returns:
        float16 numpy array ready for DDS writing, or None if no data / not configured.
    """
    if logger is None:
        logger = debugging.ContextAdapter(
            debugging.get_logger("export"), {"object_name": obj.name, "prefix": "motion_path_array"}
        )
    props = obj.i3d_motion_path_array
    cfg = MPAConfig(
        include_position=props.include_position,
        include_rotation=props.include_rotation,
        include_scale=props.include_scale,
        use_geometry_nodes=props.use_geometry_nodes,
        is_cyclic=props.is_cyclic,
        hide_first_and_last=(props.hide_first_and_last and props.include_position),
    )
    if not (cfg.include_position or cfg.include_rotation or cfg.include_scale):
        logger.warning("Skipped: no channels enabled (position/rotation/scale all disabled).")
        return None

    raw = _collect_raw(obj, depsgraph, cfg, logger)
    if raw is None or raw.size == 0:
        logger.warning("No data collected for Motion Path Array.")
        return None
    packed = _pack_channels(raw, cfg=cfg)
    if packed is None or packed.size == 0:
        logger.warning("No data after packing channels for Motion Path Array.")
        return None

    logger.info("Motion path array shape (packed): %s", packed.shape)
    return np.nan_to_num(packed, copy=False).astype(np.float16, copy=False)


def _collect_raw(
    obj: bpy.types.Object, depsgraph: bpy.types.Depsgraph, cfg: MPAConfig, logger: LogSink
) -> np.ndarray | None:
    """Returns raw float32 array of shape (Z, Y, X, 12) or None if no data found."""
    if obj.type == 'MESH' and cfg.use_geometry_nodes and any(mod.type == 'NODES' for mod in obj.modifiers):
        logger.debug("Using Geometry Nodes mode for DDS array.")
        evaluated_geometry = obj.evaluated_get(depsgraph).evaluated_geometry()
        pc = evaluated_geometry.instances_pointcloud()
        if not pc or not pc.points:
            logger.warning("Geo Nodes object has no instance points for DDS export.")
            return None

        # Allow GN attr override for cyclic mode
        if is_cyclic := pc.attributes.get("is_cyclic"):
            cfg = replace(cfg, is_cyclic=bool(is_cyclic.data[0].value))
        if pc.attributes.get("pose_idx"):
            return _collect_hierarchical_gn(pc, cfg, logger)
        return _collect_flat(pc, obj, cfg, logger)

    logger.debug("Using Classic Parenting mode for DDS array.")
    if any(child.children for child in obj.children):
        return _collect_hierarchical_classic(obj, cfg=cfg, logger=logger)
    return _collect_flat(None, obj, cfg, logger)


def _collect_flat(
    pc: bpy.types.PointCloud | None, obj: bpy.types.Object, cfg: MPAConfig, logger: LogSink
) -> np.ndarray | None:
    item_matrices: list[mathutils.Matrix]
    if pc is not None:
        item_count = len(pc.points)
        data = pc.attributes["instance_transform"].data
        item_matrices = [data[i].value for i in range(item_count)]
    else:
        children = sort_blender_objects_by_outliner_ordering(obj.children)
        item_count = len(children)
        item_matrices = [child.matrix_local for child in children]

    if item_count == 0:
        logger.warning("[%s] No items found for flat array.", obj.name)
        return None

    logger.debug("Gathered %d items for flat array.", item_count)

    arr = np.zeros((item_count, 12), dtype=np.float32)
    prev_quat: mathutils.Quaternion | None = None
    for i, matrix in enumerate(item_matrices):
        pos4, quat4, scl4, prev_quat = _matrix_to_channels(
            matrix,
            prev_quat=prev_quat,
            is_cyclic=cfg.is_cyclic,
        )
        arr[i] = np.array(pos4 + quat4 + scl4, dtype=np.float32)

    if cfg.hide_first_and_last:
        arr[0, 3] = 0.0
        if item_count > 1:
            arr[-1, 3] = 0.0

    # (Z, Y, X, 12)
    return arr[np.newaxis, np.newaxis, :, :]


def _collect_hierarchical_gn(pc: bpy.types.PointCloud, cfg: MPAConfig, logger: LogSink) -> np.ndarray | None:
    pose_attr = pc.attributes.get("pose_idx")
    group_attr = pc.attributes.get("group_idx")
    if not pose_attr or not group_attr:
        logger.warning("Missing pose_idx or group_idx on geo nodes instances.")
        return None

    n = len(pc.points)
    pose_indices = np.empty(n, dtype=np.int32)
    group_indices = np.empty(n, dtype=np.int32)
    pose_attr.data.foreach_get("value", pose_indices)
    group_attr.data.foreach_get("value", group_indices)

    z_count = int(np.max(pose_indices) + 1) if pose_indices.size > 0 else 0
    y_count = int(np.max(group_indices) + 1) if group_indices.size > 0 else 0
    if z_count == 0 or y_count == 0:
        logger.warning("No items found in Geometry Nodes data!")
        return None

    buckets: dict[tuple[int, int], list[int]] = {}
    for idx, (zi, yj) in enumerate(zip(pose_indices, group_indices, strict=False)):
        key = (int(zi), int(yj))
        buckets.setdefault(key, []).append(idx)

    max_x = max((len(v) for v in buckets.values()), default=0)
    if max_x == 0:
        logger.warning("No items found in Geometry Nodes buckets!")
        return None

    arr = np.zeros((z_count, y_count, max_x, 12), dtype=np.float32)
    inst_xform_attr = pc.attributes["instance_transform"]

    for zi in range(z_count):
        for yj in range(y_count):
            idxs = buckets.get((zi, yj))
            if not idxs:
                continue

            prev_quat: mathutils.Quaternion | None = None
            for xi, idx in enumerate(idxs):
                matrix = inst_xform_attr.data[idx].value
                pos4, quat4, scl4, prev_quat = _matrix_to_channels(
                    matrix,
                    prev_quat=prev_quat,
                    is_cyclic=cfg.is_cyclic,
                )
                arr[zi, yj, xi] = pos4 + quat4 + scl4

            num_items = len(idxs)
            if cfg.hide_first_and_last and num_items > 0:
                arr[zi, yj, 0, 3] = 0.0
                if num_items > 1:
                    arr[zi, yj, num_items - 1, 3] = 0.0

            # pad X with last item (stable sampling in shader)
            last_item = arr[zi, yj, num_items - 1]
            arr[zi, yj, num_items:max_x] = last_item

        # Fill empty Y-groups by carrying nearest valid group (your old behavior)
        row_nonempty = np.array([(zi, y) in buckets for y in range(y_count)], dtype=bool)
        if row_nonempty.any():
            first = int(np.argmax(row_nonempty))
            first_data = arr[zi, first].copy()

            last_data = first_data
            for y in range(first + 1, y_count):
                if not row_nonempty[y]:
                    arr[zi, y] = last_data
                else:
                    last_data = arr[zi, y]

            for y in range(0, first):
                arr[zi, y] = first_data

    return arr


def _collect_hierarchical_classic(
    obj: bpy.types.Object,
    *,
    cfg: MPAConfig,
    logger: LogSink,
) -> np.ndarray | None:
    parents = sort_blender_objects_by_outliner_ordering(obj.children)
    z_count = len(parents)
    if z_count == 0:
        logger.warning("[%s] No pose parents found for hierarchical classic array.", obj.name)
        return None

    max_y = 0
    max_x = 0
    for parent in parents:
        y_children = list(parent.children)
        max_y = max(max_y, len(y_children))
        for y_child in y_children:
            max_x = max(max_x, len(y_child.children))

    if max_y == 0 or max_x == 0:
        logger.warning("[%s] Hierarchical classic structure is missing depth (Y/X).", obj.name)
        return None

    arr = np.zeros((z_count, max_y, max_x, 12), dtype=np.float32)

    for zi, parent in enumerate(parents):
        y_children = sort_blender_objects_by_outliner_ordering(parent.children)

        for yi, y_child in enumerate(y_children):
            x_children = sort_blender_objects_by_outliner_ordering(y_child.children)

            prev_quat: mathutils.Quaternion | None = None
            for xi, x_child in enumerate(x_children):
                pos4, quat4, scl4, prev_quat = _matrix_to_channels(
                    x_child.matrix_local,
                    prev_quat=prev_quat,
                    is_cyclic=cfg.is_cyclic,
                )
                arr[zi, yi, xi] = pos4 + quat4 + scl4

            num_items = len(x_children)
            if num_items == 0:
                continue

            if cfg.hide_first_and_last:
                arr[zi, yi, 0, 3] = 0.0
                if num_items > 1:
                    arr[zi, yi, num_items - 1, 3] = 0.0

            # pad X
            last_item = arr[zi, yi, num_items - 1]
            arr[zi, yi, num_items:max_x] = last_item

        # pad Y groups with last group
        num_groups = len(y_children)
        if num_groups > 0:
            last_group = arr[zi, num_groups - 1, :]
            arr[zi, num_groups:max_y, :] = last_group

    return arr


def _pack_channels(raw: np.ndarray, *, cfg: MPAConfig) -> np.ndarray | None:
    """Pack raw (Z,Y,X,12) into (Z*channels, Y, X, 4) with your Y-reversal per pose."""
    channel_ranges: list[tuple[int, int]] = []
    if cfg.include_position:
        channel_ranges.append((0, 4))
    if cfg.include_rotation:
        channel_ranges.append((4, 8))
    if cfg.include_scale:
        channel_ranges.append((8, 12))
    if not channel_ranges:
        return None

    z_count = raw.shape[0]
    slices: list[np.ndarray] = []
    for zi in range(z_count):
        for start, end in channel_ranges:
            slices.append(raw[zi, ::-1, :, start:end])

    return np.stack(slices, axis=0).astype(np.float32, copy=False)


def _matrix_to_channels(
    matrix: mathutils.Matrix, *, prev_quat: mathutils.Quaternion | None, is_cyclic: bool
) -> tuple[list[float], list[float], list[float], mathutils.Quaternion]:
    conv_matrix = CONVERSION_MATRIX @ matrix @ CONVERSION_MATRIX_INVERSE
    loc, rot_q, scale = conv_matrix.decompose()

    if is_cyclic:
        euler = rot_q.to_euler("XYZ")
        x_unwrapped = euler.x % tau
        quat = mathutils.Euler((x_unwrapped, euler.y, euler.z), "XYZ").to_quaternion()
    else:
        quat = rot_q.normalized()
        if prev_quat is not None:
            quat.make_compatible(prev_quat)

    orient = [quat.x, quat.y, quat.z, quat.w]
    return [*loc, 1.0], orient, [*scale, 1.0], quat
