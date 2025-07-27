import numpy as np
import bpy
import mathutils
from bpy_extras.io_utils import axis_conversion
from .utility import sort_blender_objects_by_outliner_ordering
from .debugging import addon_logger as logger


CONVERSION_MATRIX: mathutils.Matrix = axis_conversion(to_forward='-Z', to_up='Y').to_4x4()
CONVERSION_MATRIX_INVERSE = CONVERSION_MATRIX.inverted()


def is_hierarchical(obj: bpy.types.Object) -> bool:
    """Checks if the object has children that also have children."""
    return any(child.children for child in obj.children)


def get_item_data(obj_matrix: mathutils.Matrix, prev_quat: mathutils.Quaternion = None, is_cyclic: bool = False
                  ) -> tuple[list[float], list[float], list[float]]:
    """
    Extracts position, quaternion (DDS order), and scale from the matrix.
    For cyclic paths (normalized to [0, 2π) range).
    """
    matrix = CONVERSION_MATRIX @ obj_matrix @ CONVERSION_MATRIX_INVERSE

    if is_cyclic:
        # For cyclic curves or splines, matrix.to_euler() wraps angles to [-π, π],
        # which causes sudden flips if the rotation crosses ±180 degrees.
        # To ensure smooth, continuous rotation (0 to 2π) for export,
        # normalize the X Euler angle to the [0, 2π) range before converting to quaternion.
        euler = matrix.to_euler('XYZ')
        x_unwrapped = euler.x % (2 * np.pi)
        quat = mathutils.Euler((x_unwrapped, euler.y, euler.z), 'XYZ').to_quaternion()
    else:
        quat = matrix.to_quaternion()
        if prev_quat is not None:
            # Smooth quaternion transition from previous item
            quat.make_compatible(prev_quat)
    orient = [quat.x, quat.y, quat.z, quat.w]  # Giants/DDS order
    position = list(matrix.to_translation()) + [1.0]  # Last value (.w) used for visibility in shader
    scale = list(matrix.to_scale()) + [1.0]  # Last value (.w) is unused, but kept for consistency
    return position, orient, scale, quat


def gather_flat_array(obj: bpy.types.Object, props: bpy.types.PropertyGroup) -> np.ndarray:
    """
    Collects transforms for all children of obj in a flat array.
    Returns shape (count, 12): [pos(4), rot(4), scale(4)] per child.
    """
    children = sort_blender_objects_by_outliner_ordering(list(obj.children))
    children_count = len(children)
    arr = np.zeros((children_count, 12), dtype=np.float16)
    prev_quat = None
    for i, child in enumerate(children):
        position, orient, scale, prev_quat = get_item_data(child.matrix_local, child, prev_quat,
                                                           is_cyclic=props.is_cyclic)
        # Hide first/last object if enabled, by setting position.w (visibility) to 0
        if props.hide_first_and_last and (i == 0 or i == children_count - 1):
            position[3] = 0.0
        arr[i] = position + orient + scale
    return arr


def gather_hierarchical_array(obj: bpy.types.Object, props: bpy.types.PropertyGroup) -> np.ndarray:
    """
    Collects transforms in a 3D hierarchy:
      - Z: poses (direct children of obj)
      - Y: groups (children of pose)
      - X: items (children of group)
    Pads missing Y/X with last value for consistent array shape.
    Returns (z_count, max_y, max_x, 12)
    """
    parents = sort_blender_objects_by_outliner_ordering(list(obj.children))
    z_count = len(parents)
    max_y = 0
    max_x = 0

    # Find the maximum Y (rows) and X (columns) needed for padding
    for parent in parents:
        y_children = parent.children
        max_y = max(max_y, len(y_children))
        for y_child in y_children:
            x_children = y_child.children
            max_x = max(max_x, len(x_children))

    arr = np.zeros((z_count, max_y, max_x, 12), dtype=np.float16)

    # Collect and pad data
    for zi, parent in enumerate(parents):
        y_children = sort_blender_objects_by_outliner_ordering(list(parent.children))
        logger.debug(f"[{obj.name}] Processing parent '{parent.name}' with {len(y_children)} groups")
        for yi, y_child in enumerate(y_children):
            x_children = sort_blender_objects_by_outliner_ordering(list(y_child.children))
            logger.debug(f"[{obj.name}] Processing group '{y_child.name}' with {len(x_children)} items")
            prev_quat = None
            for xi, x_child in enumerate(x_children):
                position, orient, scale, prev_quat = get_item_data(x_child.matrix_local, prev_quat,
                                                                   is_cyclic=props.is_cyclic)
                logger.debug(f"[{obj.name}] Processing item '{x_child.name}', position: {position}, orient: {orient}")
                # Optionally hide first/last in this row
                if props.hide_first_and_last and (xi == 0 or xi == len(x_children) - 1):
                    position[3] = 0.0
                arr[zi, yi, xi] = position + orient + scale
            # Pad missing X with last value, or zero if row is empty
            for xi in range(len(x_children), max_x):
                if len(x_children) == 0:
                    arr[zi, yi, xi] = 0
                else:
                    arr[zi, yi, xi] = arr[zi, yi, len(x_children) - 1]
        # Pad missing Y with last row, or zero if no groups
        for yi in range(len(y_children), max_y):
            if len(y_children) == 0:
                arr[zi, yi] = 0
            else:
                arr[zi, yi, :] = arr[zi, len(y_children) - 1, :]
    return arr


def pack_motion_path_dds_array(arr: np.ndarray, props: bpy.types.PropertyGroup) -> np.ndarray:
    """
    Packs a motion path array for DDS export, supporting both flat and hierarchical modes.

    - For flat: (1, N, 12) → (num_channels, N, 1, 4)
    - For hierarchical: (Z, Y, X, 12) → (num_poses * num_channels, Y, X, 4)
    Channels (position, rotation, scale) are stored as separate arrays, per pose.
    """
    # Normalize to 4D: (Z, Y, X, 12)
    if arr.ndim == 3:
        arr = arr[np.newaxis, :, :]   # Flat array: (1, N, 12)

    channel_slices = []
    # Build a list of (start, end) slices for each enabled channel
    channel_indices = []
    if props.include_position:
        channel_indices.append((0, 4))
    if props.include_rotation:
        channel_indices.append((4, 8))
    if props.include_scale:
        channel_indices.append((8, 12))
    if not channel_indices:
        return None

    num_poses = arr.shape[0]
    for pose_idx in range(num_poses):
        for start, end in channel_indices:
            channel_slices.append(arr[pose_idx, :, :, start:end])

    return np.stack(channel_slices, axis=0)


def gather_motion_path_array_data(obj: bpy.types.Object) -> np.ndarray:
    """
    Entry point: gathers and packs array data (flat or hierarchical)
    into a (array_size, Z, Y, X, 4) shape ready for DDS export.
    """
    logger.info(f"[{obj.name}] Gathering motion path array data")
    props = obj.i3d_motion_path_array
    if is_hierarchical(obj):
        logger.debug(f"[{obj.name}] Using hierarchical mode for DDS array.")
        arr = gather_hierarchical_array(obj, props)  # (Z, Y, X, 12)
    else:
        logger.debug(f"[{obj.name}] Using flat mode for DDS array.")
        arr = gather_flat_array(obj, props)  # (N, 12)
        arr = arr[np.newaxis, :, :]  # (1, N, 12)
    if arr is None:
        logger.warning(f"[{obj.name}] No data found for DDS export.")
    else:
        logger.info(f"[{obj.name}] Motion path array shape: {arr.shape}")
    return pack_motion_path_dds_array(arr, props) if arr is not None else None
