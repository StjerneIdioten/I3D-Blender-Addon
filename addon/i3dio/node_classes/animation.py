import logging
import math
import bpy
from bpy_extras import anim_utils
import contextlib

from .node import SceneGraphNode
from .skinned_mesh import SkinnedMeshBoneNode
from .. import xml_i3d, debugging
from ..i3d import I3D


class BaseAnimationExport:
    def __init__(self, i3d: I3D, fps: float):
        self.i3d = i3d
        self.fps = fps
        self.logger = debugging.ObjectNameAdapter(logging.getLogger(f"{__name__}.{type(self).__name__}"),
                                                  {'object_name': type(self).__name__})


class Keyframes(BaseAnimationExport):
    def __init__(self,
                 i3d: I3D,
                 fps: float,
                 node: SceneGraphNode | SkinnedMeshBoneNode,
                 channelbag: bpy.types.ActionChannelbag,
                 start_frame: int,
                 end_frame: int):
        super().__init__(i3d, fps)
        self.node = node
        self.is_bone = isinstance(node, SkinnedMeshBoneNode)
        self.channelbag = channelbag
        self.start_frame = start_frame
        self.end_frame = end_frame
        self.fcurves = self._filter_fcurves(channelbag)
        self.needs_baking = self._needs_baking(self.fcurves)
        self.has_translation = any(fc.data_path.endswith("location") for fc in self.fcurves) or self.needs_baking
        self.has_rotation = any(fc.data_path.endswith(("rotation_euler", "rotation_quaternion"))
                                for fc in self.fcurves) or self.needs_baking
        self.has_scale = any(fc.data_path.endswith("scale") for fc in self.fcurves) or self.needs_baking

        self.xml_element = self._generate_keyframes()

    def _filter_fcurves(self, channelbag: bpy.types.ActionChannelbag) -> list[bpy.types.FCurve]:
        if self.is_bone:
            bone_name = self.node.blender_object.name
            return [fc for fc in channelbag.fcurves if f'pose.bones["{bone_name}"]' in fc.data_path]
        return channelbag.fcurves

    @staticmethod
    def _needs_baking(fcurves: list[bpy.types.FCurve]) -> bool:
        """Returns True if any FCurve is not a basic transform path (location, rotation, scale)."""
        valid_paths = ("location", "rotation_euler", "rotation_quaternion", "scale")
        return any(not any(fc.data_path.endswith(valid) for valid in valid_paths) for fc in fcurves if fc.data_path)

    @property
    def is_empty(self) -> bool:
        return not self.xml_element

    def _generate_keyframes(self) -> xml_i3d.Element:
        xml_element = xml_i3d.Element("Keyframes", {"nodeId": str(self.node.id)})

        if self.needs_baking:
            # When baking, we need to use the start and end frame of the action
            # and we will get object transforms for each frame between them.
            keyframe_list = list(range(self.start_frame, self.end_frame + 1))
            self.logger.debug(f"[{self.node.name}] Baking keyframes from {self.start_frame} to {self.end_frame}")
        else:
            keyframe_list = sorted({kp.co.x for fc in self.fcurves for kp in fc.keyframe_points})
            self.logger.debug(f"[{self.node.name}] Found {len(keyframe_list)} keyframes")

        if not keyframe_list:
            self.logger.warning(f"[{self.node.name}] No keyframes found")
            return xml_element

        for frame in keyframe_list:
            # Convert frame to time in milliseconds and ensure time always starts with 0ms
            time_ms = ((frame - self.start_frame) / self.fps) * 1000
            keyframe_element = self._generate_keyframe(int(frame), time_ms)
            xml_element.append(keyframe_element)
        return xml_element

    def _generate_keyframe(self, frame: int, time_ms: float) -> xml_i3d.Element:

        self.i3d.depsgraph.scene.frame_set(frame)

        local_matrix = self.node.blender_object.matrix_local.copy()
        if self.is_bone:
            if pose_bone := self.node.root_node.blender_object.pose.bones.get(self.node.blender_object.name):
                local_matrix = pose_bone.matrix.copy()
            if isinstance(self.node.parent, SkinnedMeshBoneNode):  # Bone is parented to another bone
                if parent := self.node.root_node.blender_object.pose.bones.get(self.node.parent.blender_object.name):
                    local_matrix = parent.matrix.inverted_safe() @ local_matrix
                conv_matrix = local_matrix
            else:
                conv_matrix = self.i3d.conversion_matrix @ local_matrix
        else:
            conv_matrix = self.i3d.conversion_matrix @ local_matrix @ self.i3d.conversion_matrix_inv

        translation, rotation, scale = conv_matrix.decompose()
        rotation = rotation.to_euler('XYZ')
        keyframe_element = xml_i3d.Element("Keyframe", {"time": f"{time_ms:.6g}"})
        if self.has_translation:
            keyframe_element.set("translation", "{0:.6g} {1:.6g} {2:.6g}".format(*translation))
        if self.has_rotation:
            keyframe_element.set("rotation", " ".join(f"{math.degrees(a):.6g}" for a in rotation))
        if self.has_scale:
            keyframe_element.set("scale", "{0:.6g} {1:.6g} {2:.6g}".format(*scale))

        return keyframe_element


class Clip(BaseAnimationExport):
    def __init__(self,
                 i3d: I3D,
                 fps: float,
                 layer: bpy.types.ActionLayer,
                 node_slot_pairs: list[tuple[SceneGraphNode, bpy.types.ActionSlot]],
                 action: bpy.types.Action):
        super().__init__(i3d, fps)
        self.layer = layer
        self.action = action
        self.node_slot_pairs = node_slot_pairs
        self.xml_element = xml_i3d.Element("Clip", {"name": layer.name})

        self._generate_clip()

    def _generate_clip(self):
        start_frame, end_frame = map(int, self.action.frame_range)
        duration_ms = ((end_frame - start_frame) / self.fps) * 1000

        for node, slot in self.node_slot_pairs:
            if not (channelbag := anim_utils.action_get_channelbag_for_slot(self.action, slot)):
                self.logger.debug(f"[{node.name}] Skipped — no channelbag found for slot")
                continue

            if node.blender_object.type == 'ARMATURE':
                for bone in node.blender_object.data.bones:
                    if (bone_node := self.i3d.processed_objects.get(bone)):
                        keyframes = Keyframes(self.i3d, self.fps, bone_node, channelbag, start_frame, end_frame)
                        if not keyframes.is_empty:
                            self.xml_element.append(keyframes.xml_element)
                continue  # skip processing the armature object itself

            keyframes = Keyframes(self.i3d, self.fps, node, channelbag, start_frame, end_frame)
            if not keyframes.is_empty:
                self.xml_element.append(keyframes.xml_element)

        self.xml_element.set("duration", f"{duration_ms:.6g}")
        self.xml_element.set("count", str(len(self.xml_element)))


class AnimationSet(BaseAnimationExport):
    def __init__(self,
                 i3d: I3D,
                 fps: float,
                 action: bpy.types.Action,
                 node_slot_pairs: list[tuple[SceneGraphNode, bpy.types.ActionSlot]]):
        super().__init__(i3d, fps)
        self.action = action
        self.node_slot_pairs = node_slot_pairs
        self.clips: list[Clip] = []

        self.xml_element = xml_i3d.Element("AnimationSet", {"name": action.name})
        self._generate_clips()

    def _generate_clips(self):
        layer = self.action.layers[0]  # NOTE: Blender 4.4 action can only have one layer
        clip = Clip(self.i3d, self.fps, layer, self.node_slot_pairs, self.action)
        self.clips.append(clip)
        self.xml_element.append(clip.xml_element)
        self.xml_element.set("clipCount", str(len(self.clips)))


class Animation(BaseAnimationExport):
    def __init__(self, i3d: I3D):
        super().__init__(i3d, i3d.depsgraph.scene.render.fps)
        self.animation_sets_element = xml_i3d.SubElement(self.i3d.xml_elements['Animation'], "AnimationSets")
        self.logger.debug("Initialized animation export")

        with self._temporary_unhide_objects():
            self._export()

    @contextlib.contextmanager
    def _temporary_unhide_objects(self):
        # Temporarily unhides all animated objects during export.
        # Objects hidden in the viewport won't update transforms when the frame changes, which can break baking.
        affected_objects = {
            node.blender_object for node_slot_pairs in self.i3d.anim_links.values()
            for node, _ in node_slot_pairs if isinstance(node.blender_object, bpy.types.Object)
        }

        original_hide_state = {obj: obj.hide_viewport for obj in affected_objects}

        for obj in affected_objects:
            obj.hide_viewport = False
        try:
            yield
        finally:
            for obj, state in original_hide_state.items():
                obj.hide_viewport = state

    def _export(self):
        for action, node_slot_pairs in self.i3d.anim_links.items():
            anim_set = AnimationSet(self.i3d, self.fps, action, node_slot_pairs)
            self.animation_sets_element.append(anim_set.xml_element)
        self.animation_sets_element.set("count", str(len(self.i3d.anim_links)))
        self.logger.info(f"Exported {len(self.i3d.anim_links)} animation sets")
