import logging
from math import tau
import numpy as np
import bpy
import mathutils
from bpy_extras.io_utils import axis_conversion
from .utility import sort_blender_objects_by_outliner_ordering
from . import debugging

# Convert matrix from Blender to Giants coordinate system
CONVERSION_MATRIX: mathutils.Matrix = axis_conversion(to_forward='-Z', to_up='Y').to_4x4()
CONVERSION_MATRIX_INVERSE = CONVERSION_MATRIX.inverted()


class MotionPathArray:
    """
    Collects and structures transform data for VAT-style shaders, supporting both
    classic parenting and geometry nodes instancing.

    Output Array Shape (Z, Y, X, 12):
        - Z (pose): "motion variants" or animation states, used for blending in the shader.
            Each pose represents a different possible shape or motion for the same path/effect.
            For example, one pose might be a "default" track, and another a "lifted" variant for special ground effects.
        - Y (group): subgroups or splines within a pose.
        - X (item): sample/instance within a group, e.g. point along a curve.
        - 12: [position(4), quaternion(4), scale(4)]

    The shader can blend between poses using scrollPos.y/z/w parameters, enabling
    dynamic, responsive effects (like changing snow spray shape or making tracks lift at certain ground types).

    All arrays output by this class are ready for packing into 16-bit float DDS textures.
    """
    def __init__(self, obj: bpy.types.Object, depsgraph: bpy.types.Depsgraph = None):
        self.obj = obj
        self.props = obj.i3d_motion_path_array
        self.depsgraph = depsgraph or bpy.context.view_layer.depsgraph
        self.logger = debugging.ObjectNameAdapter(logging.getLogger(f"{__name__}.{type(self).__name__}"),
                                                  {'object_name': obj.name})

        self.is_cyclic = self.props.is_cyclic
        self.hide_first_and_last = (self.props.hide_first_and_last and self.props.include_position)
        self.prev_quat = None  # For smooth quaternion transitions
        self.array = None

    def _is_geo_nodes(self) -> bool:
        """Checks if the object is a mesh with geometry nodes modifier."""
        return (
            self.obj.type == 'MESH'
            and self.props.use_geometry_nodes
            and any(mod.type == 'NODES' for mod in self.obj.modifiers)
        )

    def gather_data(self) -> np.ndarray:
        if self._is_geo_nodes():
            self.logger.debug("Using Geometry Nodes mode for DDS array.")
            evaluated_geometry = self.obj.evaluated_get(self.depsgraph).evaluated_geometry()
            pc = evaluated_geometry.instances_pointcloud()
            if not pc or not pc.points:
                self.logger.warning("Geo Nodes object has no instance points for DDS export.")
                return None
            if is_cyclic := pc.attributes.get("is_cyclic"):
                self.is_cyclic = is_cyclic.data[0].value
            if pc.attributes.get("pose_idx"):
                arr = self._gather_hierarchical_gn(pc)
            else:
                arr = self._gather_flat(pc)

        else:
            self.logger.debug("Using Classic Parenting mode for DDS array.")
            if any(child.children for child in self.obj.children):
                arr = self._gather_hierarchical_classic()
            else:
                arr = self._gather_flat()

        if arr is None or arr.size == 0:
            self.logger.warning("No data found for DDS export.")
            self.array = None
            return None
        self.logger.info(f"Motion path array shape: {arr.shape}")
        self.array = arr
        return np.nan_to_num(self._pack_array()).astype(np.float16, copy=False)

    def _gather_flat(self, pc: bpy.types.PointCloud = None) -> np.ndarray:
        """
        Collects transforms into a flat array of shape (1, 1, N, 12).

        This is used when data has no hierarchical 'pose' or 'group' structure.
        The 'N' items are laid out along the texture's width.
        """
        item_matrices = []
        item_count = 0
        if pc is not None:
            # Gather transforms from the point cloud instances
            item_count = len(pc.points)
            data = pc.attributes["instance_transform"].data
            item_matrices = [data[i].value for i in range(item_count)]
        else:
            children = sort_blender_objects_by_outliner_ordering(self.obj.children)
            item_count = len(children)
            item_matrices = [child.matrix_local for child in children]

        if item_count == 0:
            self.logger.warning(f"[{self.obj.name}] No items found for flat array.")
            return None

        self.logger.debug(f"Gathered {item_count} items for flat array.")
        arr = np.zeros((item_count, 12), dtype=np.float32)
        for i, matrix in enumerate(item_matrices):
            position, orient, scale = self._get_item_data(matrix)
            arr[i] = np.array(position + orient + scale, dtype=np.float32)

        if self.hide_first_and_last:
            arr[0, 3] = 0.0  # Hide first item's position.w
            if item_count > 1:
                arr[-1, 3] = 0.0  # Hide last item's position.w

        return arr[np.newaxis, np.newaxis, :, :]  # Shape: (Z=1, Y=1, X=N, channels=12)

    def _gather_hierarchical_gn(self, pc: bpy.types.PointCloud) -> np.ndarray:
        """
        Collects transforms for Geometry Nodes instances into a 3D hierarchy.

        This function relies on a data contract for the instance attributes:
        - 'pose_idx' and 'group_idx' must be zero-based and contiguous
        (e.g., 0, 1, 2...).
        - It iterates through all possible (pose, group) pairs to build the
        final array, ensuring correct quaternion smoothing and padding.
        """
        pose_attr = pc.attributes.get("pose_idx")
        group_attr = pc.attributes.get("group_idx")
        if not pose_attr or not group_attr:
            self.logger.warning(f"[{self.obj.name}] Missing pose_idx or group_idx on geo nodes instances.")
            return None

        n = len(pc.points)
        pose_indices = np.empty(n, dtype=np.int32)
        group_indices = np.empty(n, dtype=np.int32)
        pose_attr.data.foreach_get("value", pose_indices)
        group_attr.data.foreach_get("value", group_indices)

        z_count = np.max(pose_indices) + 1 if pose_indices.size > 0 else 0  # Number of poses
        y_count = np.max(group_indices) + 1 if group_indices.size > 0 else 0  # Max number of groups per pose

        # Calculate max_x by finding the largest group
        unique_pairs, counts = np.unique(np.stack((pose_indices, group_indices), axis=-1), axis=0, return_counts=True)
        max_x = np.max(counts) if counts.size > 0 else 0

        if max_x == 0:
            self.logger.warning("No items found in Geometry Nodes data!")
            return None

        arr = np.zeros((z_count, y_count, max_x, 12), dtype=np.float32)
        inst_xform_attr = pc.attributes["instance_transform"]
        for zi in range(z_count):
            for yj in range(y_count):
                mask = (pose_indices == zi) & (group_indices == yj)
                idxs = np.nonzero(mask)[0]
                num_items = len(idxs)
                if num_items == 0:
                    continue
                # Reset quaternion smoothing for each group
                self.prev_quat = None
                for xi, idx in enumerate(idxs):
                    matrix = inst_xform_attr.data[idx].value
                    position, orient, scale = self._get_item_data(matrix)
                    arr[zi, yj, xi] = position + orient + scale

                # If hiding first and last items, set their position.w to 0
                if self.hide_first_and_last and num_items > 0:
                    arr[zi, yj, 0, 3] = 0.0
                    if num_items > 1:
                        arr[zi, yj, num_items - 1, 3] = 0.0

                # Pad with last value if fewer items than max_x
                if num_items > 0:
                    last_item_data = arr[zi, yj, num_items - 1]
                    arr[zi, yj, num_items:max_x] = last_item_data

            # If there are valid groups, fill any empty Y rows (leading, middle, trailing)
            row_nonempty = np.array([np.any(arr[zi, y]) for y in range(y_count)])
            if row_nonempty.any():
                first = int(np.argmax(row_nonempty))  # first non-empty row
                first_data = arr[zi, first].copy()

                # Forward-propagate last seen data to fill middle/trailing holes
                last_data = first_data
                for y in range(first + 1, y_count):
                    if not row_nonempty[y]:
                        arr[zi, y] = last_data
                    else:
                        last_data = arr[zi, y]

                # Prefill leading empties with the first non-empty row
                for y in range(0, first):
                    arr[zi, y] = first_data

        return arr

    def _gather_hierarchical_classic(self) -> np.ndarray:
        """
        Collects transforms from a classic parent->group->item hierarchy.

        - The direct children of the main object are considered 'poses' (Z-axis).
        - The children of each pose object are 'groups' (Y-axis).
        - The children of each group object are 'items' (X-axis).
        """
        parents = sort_blender_objects_by_outliner_ordering(self.obj.children)
        z_count = len(parents)
        max_y = 0
        max_x = 0

        # Find max Y and X for padding
        for parent in parents:
            y_children = parent.children
            max_y = max(max_y, len(y_children))
            for y_child in y_children:
                x_children = y_child.children
                max_x = max(max_x, len(x_children))

        # Collect and pad data
        arr = np.zeros((z_count, max_y, max_x, 12), dtype=np.float32)
        for zi, parent in enumerate(parents):
            # y_children are the 'groups' (Y axis)
            y_children = sort_blender_objects_by_outliner_ordering(parent.children)
            for yi, y_child in enumerate(y_children):
                # x_children are the 'items' (X axis)
                x_children = sort_blender_objects_by_outliner_ordering(y_child.children)
                # Reset prev_quat for each new group
                self.prev_quat = None
                for xi, x_child in enumerate(x_children):
                    position, orient, scale = self._get_item_data(x_child.matrix_local)
                    arr[zi, yi, xi] = position + orient + scale

                num_items = len(x_children)
                if self.hide_first_and_last and num_items > 0:
                    arr[zi, yi, 0, 3] = 0.0  # Hide first item's position.w
                    if num_items > 1:
                        arr[zi, yi, num_items - 1, 3] = 0.0  # Hide last item's position.w

                # Pad missing X with last value, or zero if row is empty
                if num_items > 0:
                    # Get the last valid item's data
                    last_item_data = arr[zi, yi, num_items - 1]
                    # Fill remaining X with last item data
                    arr[zi, yi, num_items:max_x] = last_item_data
                else:
                    pass  # Already initialized to zero
            # Pad missing Y with last row, or zero if no groups
            num_groups = len(y_children)
            if num_groups > 0:
                last_group_data = arr[zi, num_groups - 1, :]
                arr[zi, num_groups:max_y, :] = last_group_data

        return arr

    def _pack_array(self) -> np.ndarray:
        """
        Packs the array for DDS export, stacking channels and poses into the first axis for easy shader sampling.

        Input:
            self.array: (Z, Y, X, 12), see class docstring for axis meaning.
        Output:
            np.ndarray (num_poses * num_channels, Y, X, 4) for hierarchical arrays,
            or (num_channels, 1, N, 4) for flat arrays.

        Note:
            Each "layer" in the DDS texture corresponds to a unique (pose, channel) combination,
            which matches the way the shader blends or selects different motion paths.
        """
        channel_slices = []
        # Build a list of (start, end) slices for each enabled channel
        channel_indices = []
        if self.props.include_position:
            channel_indices.append((0, 4))
        if self.props.include_rotation:
            channel_indices.append((4, 8))
        if self.props.include_scale:
            channel_indices.append((8, 12))
        if not channel_indices:
            return None

        num_poses = self.array.shape[0]
        for pose_idx in range(num_poses):
            for start, end in channel_indices:
                # Reverse Y so row 0 is at the top (matches Giants way of doing it in their tools)
                reversed_slice = self.array[pose_idx, ::-1, :, start:end]
                channel_slices.append(reversed_slice)

        return np.stack(channel_slices, axis=0)

    def _get_item_data(self, matrix: mathutils.Matrix) -> tuple[list[float], list[float], list[float]]:
        """
        Extract position, orientation (quaternion in DDS XYZW order), and scale.

        Cyclic (track) mode:
        - Treat rotation as a continuous twist about X.
        - Unwrap X by modulo into [0, 2π); keep Y/Z as authored in [-π, π].
        - Build the quaternion from (x_unwrapped, y, z). DO NOT use make_compatible here
            (avoid quaternion shortest-arc choices that can fight X continuity).

        Non-cyclic mode:
        - Use the full orientation from the matrix.
        - Apply make_compatible with the previous quaternion for per-row continuity.

        Notes:
        - position.w is used by some shaders as a visibility mask.
        - scale.w is unused but kept for consistent 4-component packing.
        """
        conv_matrix = CONVERSION_MATRIX @ matrix @ CONVERSION_MATRIX_INVERSE
        loc, rot_q, scale = conv_matrix.decompose()

        if self.is_cyclic:
            euler = rot_q.to_euler('XYZ')  # euler angles in [-π, π]
            x_unwrapped = euler.x % tau  # Normalize to [0, 2π)
            quat = mathutils.Euler((x_unwrapped, euler.y, euler.z), 'XYZ').to_quaternion()
        else:
            quat = rot_q.normalized()
            if self.prev_quat is not None:
                quat.make_compatible(self.prev_quat)
            self.prev_quat = quat

        orient = [quat.x, quat.y, quat.z, quat.w]  # DDS order
        return [*loc, 1.0], orient, [*scale, 1.0]
