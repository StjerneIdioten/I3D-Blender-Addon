import logging
import math
import bpy
from bpy_extras import anim_utils

from .node import SceneGraphNode
from .skinned_mesh import SkinnedMeshBoneNode
from .. import xml_i3d, debugging
from ..i3d import I3D

# https://developer.blender.org/docs/release_notes/4.4/python_api/#slotted-actions


class BaseAnimationExport:
    def __init__(self, i3d: I3D, fps: float):
        self.i3d = i3d
        self.fps = fps
        self.logger = debugging.ObjectNameAdapter(logging.getLogger(f"{__name__}.{type(self).__name__}"),
                                                  {'object_name': type(self).__name__})


class Keyframe:
    @staticmethod
    def generate_keyframe(i3d: I3D,
                          node: SceneGraphNode | SkinnedMeshBoneNode,
                          is_bone: bool,
                          frame: int,
                          time_ms: float,
                          export_translation: bool,
                          export_rotation: bool,
                          export_scale: bool) -> xml_i3d.Element:

        i3d.depsgraph.scene.frame_set(frame)

        local_matrix = node.blender_object.matrix_local.copy()
        if is_bone:
            if pose_bone := node.root_node.blender_object.pose.bones.get(node.blender_object.name):
                local_matrix = pose_bone.matrix.copy()
            if isinstance(node.parent, SkinnedMeshBoneNode):
                # Bone with bone parent — use raw matrix
                if parent_pose_bone := node.root_node.blender_object.pose.bones.get(node.parent.blender_object.name):
                    local_matrix = parent_pose_bone.matrix.inverted_safe() @ local_matrix
                conv_matrix = local_matrix
            else:
                conv_matrix = i3d.conversion_matrix @ local_matrix
        else:
            conv_matrix = i3d.conversion_matrix @ local_matrix @ i3d.conversion_matrix.inverted_safe()

        translation, rotation, scale = conv_matrix.decompose()
        rotation = rotation.to_euler('XYZ')
        keyframe_element = xml_i3d.Element("Keyframe", {"time": f"{time_ms:.6g}"})
        if export_translation:
            keyframe_element.set("translation", "{0:.6g} {1:.6g} {2:.6g}".format(*translation))
        if export_rotation:
            keyframe_element.set("rotation", " ".join(f"{math.degrees(a):.6g}" for a in rotation))
        if export_scale:
            keyframe_element.set("scale", "{0:.6g} {1:.6g} {2:.6g}".format(*scale))

        return keyframe_element


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
        self.has_translation = any(fc.data_path.endswith("location") for fc in self.fcurves)
        self.has_rotation = any(fc.data_path.endswith("rotation_euler") for fc in self.fcurves)
        self.has_scale = any(fc.data_path.endswith("scale") for fc in self.fcurves)

        self.xml_element = self._generate_keyframes()

    def _filter_fcurves(self, channelbag: bpy.types.ActionChannelbag) -> list[bpy.types.FCurve]:
        if self.is_bone:
            bone_name = self.node.blender_object.name
            return [fc for fc in channelbag.fcurves if f'pose.bones["{bone_name}"]' in fc.data_path]
        return channelbag.fcurves

    @staticmethod
    def _needs_baking(fcurves: list[bpy.types.FCurve]) -> bool:
        """Returns True if *any* FCurve animates a non-transform property."""
        valid_paths = ("location", "rotation_euler", "rotation_quaternion", "scale")
        return any(not fc.data_path.endswith(path) for fc in fcurves for path in valid_paths if fc.data_path)

    @property
    def is_empty(self) -> bool:
        return not self.xml_element

    def _generate_keyframes(self) -> xml_i3d.Element:
        xml_element = xml_i3d.Element("Keyframes", {"nodeId": str(self.node.id)})

        if self._needs_baking(self.fcurves):
            # When baking, we need to use the start and end frame of the action
            # and we will get object transforms for each frame between them.
            keyframe_list = list(range(self.start_frame, self.end_frame + 1))
            self.i3d.logger.debug(f"[{self.node.name}] Baking keyframes from {self.start_frame} to {self.end_frame}")
            self.has_translation = True
            self.has_rotation = True
            self.has_scale = True
        else:
            keyframe_list = sorted({kp.co.x for fc in self.fcurves for kp in fc.keyframe_points})

        if not keyframe_list:
            self.i3d.logger.debug(f"[{self.node.name}] No keyframes found")
            return xml_element

        for frame in keyframe_list:
            # Convert frame to time in milliseconds and ensure time always starts with 0ms
            time_ms = ((frame - self.start_frame) / self.fps) * 1000
            keyframe_element = Keyframe.generate_keyframe(
                self.i3d,
                self.node,
                self.is_bone,
                frame,
                time_ms,
                export_translation=self.has_translation,
                export_rotation=self.has_rotation,
                export_scale=self.has_scale
            )
            xml_element.append(keyframe_element)
        return xml_element


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

        # Add check to see if anything in related hiearchy have animated constraints etc.

        self._generate_clip()

    def _generate_clip(self):
        start_frame, end_frame = map(int, self.action.frame_range)
        duration_ms = ((end_frame - start_frame) / self.fps) * 1000

        for node, slot in self.node_slot_pairs:
            if not (channelbag := anim_utils.action_get_channelbag_for_slot(self.action, slot)):
                continue

            self.i3d.logger.debug(f"[{node.name}] Processing started")

            if node.blender_object.type == 'ARMATURE':
                for bone in node.blender_object.data.bones:
                    if (bone_node := self.i3d.processed_objects.get(bone)):
                        keyframes = Keyframes(self.i3d, self.fps, bone_node, channelbag, start_frame, end_frame)
                        if not keyframes.is_empty:
                            self.xml_element.append(keyframes.xml_element)
                continue  # skip processing the armature object itself

            self.i3d.logger.debug(f"[{node.name}] Processing completed")

            keyframes = Keyframes(self.i3d, self.fps, node, channelbag, start_frame, end_frame)
            if not keyframes.is_empty:
                self.i3d.logger.debug(f"[{node.name}] Keyframes found")
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
        # NOTE: Blender 4.4 action can only have one layer
        layer = self.action.layers[0]
        clip = Clip(self.i3d, self.fps, layer, self.node_slot_pairs, self.action)
        self.clips.append(clip)
        self.xml_element.append(clip.xml_element)
        self.xml_element.set("clipCount", str(len(self.clips)))


class Animation(BaseAnimationExport):
    def __init__(self, i3d: I3D):
        super().__init__(i3d, i3d.depsgraph.scene.render.fps)
        self.animation_sets_element = xml_i3d.SubElement(self.i3d.xml_elements['Animation'], "AnimationSets")
        self.logger.debug("Initialized animation export")
        self._export()

    def _export(self):
        for action, node_slot_pairs in self.i3d.anim_links.items():
            anim_set = AnimationSet(self.i3d, self.fps, action, node_slot_pairs)
            self.animation_sets_element.append(anim_set.xml_element)
        self.animation_sets_element.set("count", str(len(self.i3d.anim_links)))
