import logging
import math
import bpy
from bpy_extras import anim_utils
import mathutils

from .node import SceneGraphNode
from .. import xml_i3d, debugging
from ..i3d import I3D

# https://developer.blender.org/docs/release_notes/4.4/python_api/#slotted-actions


class Animation:
    def __init__(self, id_: int, i3d: I3D, animated_object: bpy.types.Object, parent: SceneGraphNode | None = None):
        self.id = id_
        self.i3d = i3d
        self.animated_object = animated_object
        self.parent = parent
        self.name = animated_object.name
        self.fps = i3d.depsgraph.scene.render.fps

        self.logger = debugging.ObjectNameAdapter(logging.getLogger(f"{__name__}.{type(self).__name__}"),
                                                  {'object_name': self.name})

        self.logger.debug("Initialized animation")

        action = self.animated_object.animation_data.action
        action_slot = self.animated_object.animation_data.action_slot
        channelbag = anim_utils.action_get_channelbag_for_slot(action, action_slot)

        if not channelbag:
            self.logger.warning(f"No action found for '{self.animated_object.name}', skipping keyframes.")
            return

        self.animation_root = i3d.xml_elements['Animation']
        self.animation_sets = i3d.xml_elements.get('AnimationSets')

        if self.animation_sets is None:
            self.animation_sets = xml_i3d.SubElement(self.animation_root, "AnimationSets")
            i3d.xml_elements['AnimationSets'] = self.animation_sets

        self.animation_set = next((anim_set for anim_set in self.animation_sets.findall('AnimationSet')
                                   if anim_set.get('name') == self.name), None)
        if self.animation_set is None:
            self.animation_set = xml_i3d.SubElement(self.animation_sets, 'AnimationSet', {"name": self.name})

        fcurves = channelbag.fcurves
        # Compute animation duration (last frame converted to milliseconds)
        duration = max((kp.co.x for fcurve in fcurves for kp in fcurve.keyframe_points), default=0)
        duration = (duration / self.fps) * 1000  # i3d expects time in milliseconds

        # Create Clip element inside AnimationSet
        self.clip = xml_i3d.SubElement(self.animation_set, "Clip", {"name": action_slot.name_display,
                                                                    "duration": f"{duration:.6f}"})
        keyframes_element = xml_i3d.SubElement(self.clip, "Keyframes", {"nodeId": str(self.id)})

        self._extract_keyframes(fcurves, keyframes_element)

    def _extract_keyframes(self,
                           fcurves: bpy.types.ActionChannelbagFCurves,
                           keyframes_element: xml_i3d.Element) -> None:
        """Extracts keyframes"""

        keyframes = {keyframe.co.x for fcurve in fcurves for keyframe in fcurve.keyframe_points}
        if not keyframes:
            return

        keyframe_data = {}

        # No need to write keyframes if they are empty
        export_translation = any("location" in fcurve.data_path for fcurve in fcurves)
        export_rotation = any("rotation_euler" in fcurve.data_path for fcurve in fcurves)
        export_scale = any("scale" in fcurve.data_path for fcurve in fcurves)
        export_visibility = any("hide_viewport" in fcurve.data_path for fcurve in fcurves)

        parent_matrix = (self.parent.blender_object.matrix_world.inverted()
                         if self.parent else mathutils.Matrix.Identity(4))

        for frame in sorted(list(keyframes)):
            time_ms = (frame / self.fps) * 1000  # i3d expects time in milliseconds

            translation = [0, 0, 0]
            rotation = [0, 0, 0] if export_rotation else None
            scale = [1, 1, 1]
            visibility = True

            for fcurve in fcurves:
                value = fcurve.evaluate(frame)
                path = fcurve.data_path
                if "location" in path:
                    translation[fcurve.array_index] = value
                elif "rotation_euler" in path:
                    rotation[fcurve.array_index] = value
                elif "scale" in path:
                    scale[fcurve.array_index] = value
                elif "hide_viewport" in path:
                    # `hide_viewport` has invert_checkbox enabled in Blender's UI.
                    # API/fcurve stores 0.0 when visible and 1.0 when hidden.
                    visibility = fcurve.evaluate(frame) == 0.0

            translation_vec = mathutils.Vector(translation)
            rotation_euler = mathutils.Euler(rotation, 'XYZ') if rotation else None
            scale_vec = mathutils.Vector(scale)

            translation_matrix = mathutils.Matrix.Translation(translation_vec)
            scale_matrix = mathutils.Matrix.Diagonal(scale_vec).to_4x4()

            if export_rotation:
                rotation_euler = mathutils.Euler(rotation, 'XYZ')
                rotation_matrix = rotation_euler.to_matrix().to_4x4()
            else:
                rotation_matrix = mathutils.Matrix.Identity(4)

            # Relative to parent
            transform_matrix = parent_matrix @ translation_matrix @ rotation_matrix @ scale_matrix
            conversion_matrix = self.i3d.conversion_matrix @ transform_matrix @ self.i3d.conversion_matrix.inverted()

            final_translation, final_rotation, final_scale = conversion_matrix.decompose()
            if export_rotation:
                final_rotation = final_rotation.to_euler('XYZ')

            keyframe_attribs = {"time": str(time_ms)}
            if export_translation:
                keyframe_attribs["translation"] = "{0:.6g} {1:.6g} {2:.6g}".format(*final_translation)
            if export_rotation:
                keyframe_attribs["rotation"] = "{0:.6g} {1:.6g} {2:.6g}".format(*[math.degrees(angle)
                                                                                  for angle in final_rotation])
            if export_scale:
                keyframe_attribs["scale"] = "{0:.6g} {1:.6g} {2:.6g}".format(*final_scale)

            if export_visibility:
                keyframe_attribs["visibility"] = str(visibility).lower()

            xml_i3d.SubElement(keyframes_element, "Keyframe", keyframe_attribs)

        self.logger.debug(f"Extracted {len(keyframe_data)} keyframes for '{self.animated_object.name}'")
