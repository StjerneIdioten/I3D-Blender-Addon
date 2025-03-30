import logging
import math
import bpy
from bpy_extras import anim_utils
import mathutils

from .node import SceneGraphNode
from .skinned_mesh import SkinnedMeshBoneNode
from .. import xml_i3d, debugging
from ..i3d import I3D

# https://developer.blender.org/docs/release_notes/4.4/python_api/#slotted-actions


class Keyframe:
    def __init__(self,
                 i3d: I3D,
                 node: SceneGraphNode | SkinnedMeshBoneNode,
                 is_bone: bool,
                 parent_matrix: mathutils.Matrix,
                 parent_is_bone: bool,
                 fcurves: list[bpy.types.FCurve],
                 frame: float,
                 time_ms: float):
        self.i3d = i3d
        self.node = node
        self.is_bone = is_bone
        self.parent_matrix = parent_matrix
        self.parent_is_bone = parent_is_bone
        self.fcurves = fcurves
        self.frame = frame
        self.time_ms = time_ms
        paths = [fcurve.data_path for fcurve in self.fcurves]

        # Determine which properties to export based on the fcurve paths
        self.export_translation = any("location" in path for path in paths)
        self.export_rotation = any("rotation_euler" in path or "rotation_quaternion" in path for path in paths)
        self.export_scale = any("scale" in path for path in paths)
        self.export_visibility = any("hide_viewport" in path for path in paths)
        self._generate_keyframe()

    def _generate_keyframe(self):
        """Generates and returns the XML representation of the keyframe at a specific frame."""
        self.xml_element = xml_i3d.Element("Keyframe", {"time": f"{self.time_ms:.6g}"})
        translation = [0, 0, 0]
        rotation = None
        used_quaternion = False
        scale = [1, 1, 1]
        visibility = True

        for fcurve in self.fcurves:
            value = fcurve.evaluate(self.frame)
            path = fcurve.data_path
            if "location" in path:
                translation[fcurve.array_index] = value
            elif "rotation_euler" in path:
                if rotation is None:
                    rotation = [0, 0, 0]
                rotation[fcurve.array_index] = value
            elif "rotation_quaternion" in path:
                if rotation is None:
                    rotation = [0, 0, 0, 0]
                rotation[fcurve.array_index] = value
                used_quaternion = True
            elif "scale" in path:
                scale[fcurve.array_index] = value
            elif "hide_viewport" in path:
                visibility = value == 0.0  # Visibility property is inverted in UI

        if rotation:
            rotation = mathutils.Quaternion(rotation).to_euler('XYZ') if used_quaternion else rotation[:3]

        translation_vec = mathutils.Vector(translation)
        rotation_euler = mathutils.Euler(rotation, 'XYZ') if rotation else None
        scale_vec = mathutils.Vector(scale)

        translation_matrix = mathutils.Matrix.Translation(translation_vec)
        scale_matrix = mathutils.Matrix.Diagonal(scale_vec).to_4x4()
        rotation_matrix = rotation_euler.to_matrix().to_4x4() if rotation_euler else mathutils.Matrix.Identity(4)

        transform_matrix = self.parent_matrix @ translation_matrix @ rotation_matrix @ scale_matrix
        if self.is_bone:
            if self.parent_is_bone:
                conv_matrix = transform_matrix
            else:
                bone_matrix = self.i3d.conversion_matrix @ self.node.blender_object.matrix_local
                conv_matrix = bone_matrix @ transform_matrix
        else:
            conv_matrix = self.i3d.conversion_matrix @ transform_matrix @ self.i3d.conversion_matrix.inverted_safe()

        final_translation, final_rotation, final_scale = conv_matrix.decompose()
        final_rotation = final_rotation.to_euler('XYZ')
        if self.export_translation:
            self.xml_element.set("translation", "{0:.6g} {1:.6g} {2:.6g}".format(*final_translation))
        if self.export_rotation:
            self.xml_element.set("rotation", "{0:.6g} {1:.6g} {2:.6g}".format(*[math.degrees(angle)
                                                                                for angle in final_rotation]))
        if self.export_scale:
            self.xml_element.set("scale", "{0:.6g} {1:.6g} {2:.6g}".format(*final_scale))
        if self.export_visibility:
            self.xml_element.set("visibility", str(visibility).lower())


class Keyframes:
    def __init__(self,
                 i3d: I3D,
                 fps: float,
                 node: SceneGraphNode | SkinnedMeshBoneNode,
                 channelbag: bpy.types.ActionChannelbag,
                 start_frame: int):
        self.i3d = i3d
        self.fps = fps
        self.node = node
        self.channelbag = channelbag
        self.start_frame = start_frame
        self.is_bone = isinstance(node, SkinnedMeshBoneNode)
        self.parent_is_bone = isinstance(node.parent, SkinnedMeshBoneNode)
        self.fcurves = self._filter_fcurves()

        self.xml_element = self._generate_keyframes()

    def _filter_fcurves(self) -> list[bpy.types.FCurve]:
        """Filter fcurves based on the node type."""
        if self.is_bone:
            bone_name = self.node.blender_object.name
            return [fc for fc in self.channelbag.fcurves if f'pose.bones["{bone_name}"]' in fc.data_path]
        return self.channelbag.fcurves

    def _get_parent_matrix(self) -> mathutils.Matrix:
        """Get the matrix of the node's parent, accounting for bones and collapsed armatures."""
        parent = self.node.parent
        parent_matrix = parent.blender_object.matrix_local.inverted_safe() if parent else mathutils.Matrix.Identity(4)
        if self.is_bone:
            if self.parent_is_bone:
                # For child bones, the transform is relative to the parent's local space
                return parent_matrix @ self.node.blender_object.matrix_local
            matrix = parent_matrix
            if self.node.root_node.is_collapsed:
                # Include armature's transform if the armature object is collapsed
                armature_inv_matrix = self.node.root_node.blender_object.matrix_local.inverted()
                matrix = armature_inv_matrix @ matrix
            return matrix
        return parent_matrix  # Non-bone nodes use inverted parent matrix directly

    @property
    def is_empty(self) -> bool:
        return not self.xml_element

    def _generate_keyframes(self) -> xml_i3d.Element:
        xml_element = xml_i3d.Element("Keyframes", {"nodeId": str(self.node.id)})
        keyframe_list = sorted({kp.co.x for fc in self.fcurves for kp in fc.keyframe_points})

        if not keyframe_list:
            return xml_element

        parent_matrix = self._get_parent_matrix()

        for frame in keyframe_list:
            time_ms = ((frame - self.start_frame) / self.fps) * 1000
            keyframe = Keyframe(
                self.i3d, self.node, self.is_bone, parent_matrix, self.parent_is_bone, self.fcurves, frame, time_ms
            )
            xml_element.append(keyframe.xml_element)
        return xml_element


class Clip:
    def __init__(self,
                 i3d: I3D,
                 fps: float,
                 layer: bpy.types.ActionLayer,
                 node_slot_pairs: list[tuple[SceneGraphNode, bpy.types.ActionSlot]],
                 action: bpy.types.Action):
        self.i3d = i3d
        self.fps = fps
        self.layer = layer
        self.action = action
        self.node_slot_pairs = node_slot_pairs
        self.xml_element = xml_i3d.Element("Clip", {"name": layer.name})

        self._generate_keyframes()

    def _generate_keyframes(self):
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


class AnimationSet:
    def __init__(self,
                 i3d: I3D,
                 fps: float,
                 action: bpy.types.Action,
                 node_slot_pairs: list[tuple[SceneGraphNode, bpy.types.ActionSlot]]):
        self.i3d = i3d
        self.fps = fps
        self.action = action
        self.node_slot_pairs = node_slot_pairs

        self.xml_element = xml_i3d.Element("AnimationSet", {"name": action.name})
        self.clips: list[Clip] = []
        self._generate_clips()

    def _generate_clips(self):
        # NOTE: Blender 4.4 action can only have one layer
        layer = self.action.layers[0]
        clip = Clip(self.i3d, self.fps, layer, self.node_slot_pairs, self.action)
        self.clips.append(clip)
        self.xml_element.append(clip.xml_element)
        self.xml_element.set("clipCount", str(len(self.clips)))


class Animation:
    def __init__(self, i3d: I3D):
        self.i3d = i3d
        self.fps = i3d.depsgraph.scene.render.fps
        self.logger = debugging.ObjectNameAdapter(logging.getLogger(f"{__name__}.{type(self).__name__}"),
                                                  {'object_name': 'AnimationExport'})
        self.logger.debug("Initialized animation export")
        self.animation_sets_element = xml_i3d.SubElement(self.i3d.xml_elements['Animation'], "AnimationSets")
        self._export()

    def _export(self):
        for action, node_slot_pairs in self.i3d.anim_links.items():
            anim_set = AnimationSet(self.i3d, self.fps, action, node_slot_pairs)
            self.animation_sets_element.append(anim_set.xml_element)
        self.animation_sets_element.set("count", str(len(self.i3d.anim_links)))
