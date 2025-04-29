import logging
import math
import bpy
from bpy_extras import anim_utils
from dataclasses import dataclass

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


class BaseAnimationNode(BaseAnimationExport):
    def __init__(self, i3d: I3D, fps: float, node: SceneGraphNode | SkinnedMeshBoneNode):
        super().__init__(i3d, fps)
        self.node = node
        self.is_bone = isinstance(node, SkinnedMeshBoneNode)
        self.parent_is_bone = isinstance(node.parent, SkinnedMeshBoneNode)
        self.fcurves: list[bpy.types.FCurve] = []
        self.should_bake: bool = False

    def _filter_fcurves(self, channelbag: bpy.types.ActionChannelbag) -> list[bpy.types.FCurve]:
        if self.is_bone:
            bone_name = self.node.blender_object.name
            return [fc for fc in channelbag.fcurves if f'pose.bones["{bone_name}"]' in fc.data_path]
        return channelbag.fcurves


@dataclass
class KeyframeContext:
    node: SceneGraphNode | SkinnedMeshBoneNode
    is_bone: bool
    frame: float
    time_ms: float
    export_translation: bool
    export_rotation: bool
    export_scale: bool
    should_bake: bool = False


class Keyframe(BaseAnimationExport):
    def __init__(self, i3d: I3D, context: KeyframeContext):
        super().__init__(i3d, i3d.depsgraph.scene.render.fps)
        self.ctx = context
        self._generate_keyframe()

    def _generate_keyframe(self):
        """Generates and returns the XML representation of the keyframe at a specific frame."""
        """ if self.should_bake:
            # If baking is needed, we need to sample the keyframe at the current frame
            self.time_ms = ((self.frame - self.i3d.start_frame) / self.i3d.fps) * 1000 """

        self.i3d.depsgraph.scene.frame_set(int(self.ctx.frame))

        node = self.ctx.node

        if self.ctx.is_bone:
            if pose_bone := node.root_node.blender_object.pose.bones.get(node.blender_object.name):
                local_matrix = pose_bone.matrix.copy()
        else:
            local_matrix = node.blender_object.matrix_local.copy()

        if self.ctx.is_bone:
            if isinstance(node.parent, SkinnedMeshBoneNode):
                # Bone with bone parent — use raw matrix
                if parent_pose_bone := node.root_node.blender_object.pose.bones.get(node.parent.blender_object.name):
                    local_matrix = parent_pose_bone.matrix.inverted_safe() @ local_matrix
                conv_matrix = local_matrix
            else:
                conv_matrix = self.i3d.conversion_matrix @ local_matrix
        else:
            conv_matrix = self.i3d.conversion_matrix @ local_matrix @ self.i3d.conversion_matrix.inverted_safe()

        final_translation, final_rotation, final_scale = conv_matrix.decompose()
        final_rotation = final_rotation.to_euler('XYZ')
        self.xml_element = xml_i3d.Element("Keyframe", {"time": f"{self.ctx.time_ms:.6g}"})
        if self.ctx.export_translation:
            self.xml_element.set("translation", "{0:.6g} {1:.6g} {2:.6g}".format(*final_translation))
        if self.ctx.export_rotation:
            self.xml_element.set("rotation", " ".join(f"{math.degrees(a):.6g}" for a in final_rotation))
        if self.ctx.export_scale:
            self.xml_element.set("scale", "{0:.6g} {1:.6g} {2:.6g}".format(*final_scale))


class Keyframes(BaseAnimationNode):
    def __init__(self,
                 i3d: I3D,
                 fps: float,
                 node: SceneGraphNode | SkinnedMeshBoneNode,
                 channelbag: bpy.types.ActionChannelbag,
                 start_frame: int):
        super().__init__(i3d, fps, node)
        self.channelbag = channelbag
        self.start_frame = start_frame
        self.fcurves = self._filter_fcurves(channelbag)
        self.has_translation = any(fc.data_path.endswith("location") for fc in self.fcurves)
        self.has_rotation = any(fc.data_path.endswith("rotation_euler") for fc in self.fcurves)
        self.has_scale = any(fc.data_path.endswith("scale") for fc in self.fcurves)
        self.should_bake = self.needs_baking(self.fcurves)

        self.xml_element = self._generate_keyframes()

    @staticmethod
    def needs_baking(fcurves: list[bpy.types.FCurve]) -> bool:
        """Check if any fcurve requires baking. E.g. if it has animated constraints etc."""
        return any(not fc.data_path.endswith((
            "location", "rotation_euler", "rotation_quaternion", "scale")) for fc in fcurves
        )

    @property
    def is_empty(self) -> bool:
        return not self.xml_element

    def _generate_keyframes(self) -> xml_i3d.Element:
        xml_element = xml_i3d.Element("Keyframes", {"nodeId": str(self.node.id)})
        keyframe_list = sorted({kp.co.x for fc in self.fcurves for kp in fc.keyframe_points})

        if not keyframe_list:
            return xml_element

        for frame in keyframe_list:
            # Convert frame to time in milliseconds and ensure time always starts with 0ms
            time_ms = ((frame - self.start_frame) / self.fps) * 1000
            context = KeyframeContext(
                node=self.node,
                is_bone=self.is_bone,
                frame=frame,
                time_ms=time_ms,
                export_translation=self.has_translation,
                export_rotation=self.has_rotation,
                export_scale=self.has_scale,
                should_bake=self.should_bake,
            )
            keyframe = Keyframe(self.i3d, context)
            xml_element.append(keyframe.xml_element)
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
                        keyframes = Keyframes(self.i3d, self.fps, bone_node, channelbag, start_frame)
                        if not keyframes.is_empty:
                            self.xml_element.append(keyframes.xml_element)
                continue  # skip processing the armature object itself

            self.i3d.logger.debug(f"[{node.name}] Processing completed")

            keyframes = Keyframes(self.i3d, self.fps, node, channelbag, start_frame)
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
