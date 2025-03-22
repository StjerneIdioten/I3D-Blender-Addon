import logging
import math
import bpy
from bpy_extras import anim_utils
import mathutils

from .node import SceneGraphNode
from .. import xml_i3d, debugging
from ..i3d import I3D

# https://developer.blender.org/docs/release_notes/4.4/python_api/#slotted-actions


class Keyframe:
    def __init__(self, i3d: I3D, node: SceneGraphNode, parent_matrix: mathutils.Matrix,
                 fcurves, frame: float, time_ms: float):
        self.i3d = i3d
        self.node = node
        self.parent_matrix = parent_matrix
        self.fcurves = fcurves
        self.frame = frame
        self.time_ms = time_ms
        paths = [fcurve.data_path for fcurve in self.fcurves]
        self.export_translation = any("location" in path for path in paths)
        self.export_rotation = any("rotation_euler" in path for path in paths)
        self.export_scale = any("scale" in path for path in paths)
        self.export_visibility = any("hide_viewport" in path for path in paths)
        self._generate_keyframe()

    def _generate_keyframe(self):
        # Evaluate fcurves and bake transform
        self.xml_element = xml_i3d.Element("Keyframe", {"time": f"{self.time_ms:.6g}"})
        translation = [0, 0, 0]
        rotation = [0, 0, 0] if self.export_rotation else None
        scale = [1, 1, 1]
        visibility = True

        for fcurve in self.fcurves:
            value = fcurve.evaluate(self.frame)
            path = fcurve.data_path
            if "location" in path:
                translation[fcurve.array_index] = value
            elif "rotation_euler" in path:
                rotation[fcurve.array_index] = value
            elif "scale" in path:
                scale[fcurve.array_index] = value
            elif "hide_viewport" in path:
                visibility = value == 0.0

        translation_vec = mathutils.Vector(translation)
        rotation_euler = mathutils.Euler(rotation, 'XYZ') if rotation else None
        scale_vec = mathutils.Vector(scale)

        translation_matrix = mathutils.Matrix.Translation(translation_vec)
        scale_matrix = mathutils.Matrix.Diagonal(scale_vec).to_4x4()
        rotation_matrix = rotation_euler.to_matrix().to_4x4() if rotation_euler else mathutils.Matrix.Identity(4)

        transform_matrix = self.parent_matrix @ translation_matrix @ rotation_matrix @ scale_matrix
        conversion_matrix = self.i3d.conversion_matrix @ transform_matrix @ self.i3d.conversion_matrix.inverted()

        final_translation, final_rotation, final_scale = conversion_matrix.decompose()
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
    def __init__(self, i3d: I3D, fps: float, node: SceneGraphNode, channelbag: bpy.types.ActionChannelbag):
        self.i3d = i3d
        self.fps = fps
        self.node = node
        self.channelbag = channelbag

        self.max_frame = 0
        self.has_data = False
        self.xml_element = xml_i3d.Element("Keyframes", {"nodeId": str(node.id)})

        self._generate_keyframes()

    def _generate_keyframes(self):
        keyframe_list = sorted({kp.co.x for fc in self.channelbag.fcurves for kp in fc.keyframe_points})
        if not keyframe_list:
            return

        self.has_data = True
        self.max_frame = keyframe_list[-1]
        first_frame = keyframe_list[0]

        parent = self.node.parent
        parent_matrix = parent.blender_object.matrix_world.inverted() if parent else mathutils.Matrix.Identity(4)

        for frame in keyframe_list:
            time_ms = ((frame - first_frame) / self.fps) * 1000
            keyframe = Keyframe(self.i3d, self.node, parent_matrix, self.channelbag.fcurves, frame, time_ms)
            self.xml_element.append(keyframe.xml_element)


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
        max_frame = 0
        keyframes_written = 0

        for node, slot in self.node_slot_pairs:
            if not (channelbag := anim_utils.action_get_channelbag_for_slot(self.action, slot)):
                continue

            keyframes = Keyframes(self.i3d, self.fps, node, channelbag)
            if keyframes.has_data:
                self.xml_element.append(keyframes.xml_element)
                max_frame = max(max_frame, keyframes.max_frame)
                keyframes_written += 1

        duration_ms = (max_frame / self.fps) * 1000
        self.xml_element.set("duration", f"{duration_ms:.6g}")
        self.xml_element.set("count", str(keyframes_written))


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
