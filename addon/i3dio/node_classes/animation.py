import logging
import math
import bpy
import mathutils
from .. import xml_i3d, debugging
from ..i3d import I3D


class Animation:
    def __init__(self, id_: int, i3d: I3D, animated_object: bpy.types.Object):
        self.id = id_
        self.i3d = i3d
        self.animated_object = animated_object
        self.name = animated_object.name
        self.fps = i3d.depsgraph.scene.render.fps

        self.logger = debugging.ObjectNameAdapter(logging.getLogger(f"{__name__}.{type(self).__name__}"),
                                                  {'object_name': self.name})

        self.logger.debug("Initialized animation")

        self.animation_root = i3d.xml_elements['Animation']
        self.animation_sets = i3d.xml_elements.get('AnimationSets')

        if self.animation_sets is None:
            self.animation_sets = xml_i3d.SubElement(self.animation_root, "AnimationSets")
            i3d.xml_elements['AnimationSets'] = self.animation_sets

        self.animation_set = next((anim_set for anim_set in self.animation_sets.findall('AnimationSet')
                                   if anim_set.get('name') == self.name), None)
        if self.animation_set is None:
            self.animation_set = xml_i3d.SubElement(self.animation_sets, 'AnimationSet', {"name": self.name})

        self._extract_animation_clips()

    def _extract_animation_clips(self) -> None:
        """Extracts animation keyframes and structures them inside a Clip."""
        anim_data = self.animated_object.animation_data
        action = anim_data.action
        if not action:
            self.logger.warning(f"No action found for '{self.animated_object.name}', skipping keyframes.")
            return

        # Compute animation duration (last frame converted to milliseconds)
        duration = max((kp.co.x for fcurve in action.fcurves for kp in fcurve.keyframe_points), default=0)
        duration = (duration / self.fps) * 1000  # Convert to milliseconds

        # Create Clip element inside AnimationSet
        self.clip = xml_i3d.SubElement(self.animation_set, "Clip", {"name": action.name, "duration": f"{duration:.6f}"})
        keyframes_element = xml_i3d.SubElement(self.clip, "Keyframes", {"nodeId": str(self.id)})

        # Extract and store keyframes
        self._extract_keyframes(action, keyframes_element)

    def _extract_keyframes(self, action: bpy.types.Action, keyframes_element: xml_i3d.Element) -> None:
        """Extracts keyframes efficiently, caching transformations and handling hidden object updates."""

        # Collect keyframes from F-Curves
        keyframes = set()
        for fcurve in action.fcurves:
            for keyframe in fcurve.keyframe_points:
                keyframes.add(keyframe.co.x)

        keyframe_data = {}

        export_translation = any("location" in fcurve.data_path for fcurve in action.fcurves)
        export_rotation = any("rotation_euler" in fcurve.data_path for fcurve in action.fcurves)
        export_scale = any("scale" in fcurve.data_path for fcurve in action.fcurves)

        for time in sorted(list(keyframes)):  # Ensure sorted order
            frame = int(time)
            time_ms = (frame / self.fps) * 1000  # Convert to milliseconds

            translation = [0, 0, 0]
            rotation = [0, 0, 0] if export_rotation else None
            scale = [1, 1, 1]

            for fcurve in action.fcurves:
                if "location" in fcurve.data_path:
                    translation[fcurve.array_index] = fcurve.evaluate(frame)
                elif "rotation_euler" in fcurve.data_path:
                    rotation[fcurve.array_index] = fcurve.evaluate(frame)
                elif "scale" in fcurve.data_path:
                    scale[fcurve.array_index] = fcurve.evaluate(frame)

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

            transform_matrix = translation_matrix @ rotation_matrix @ scale_matrix

            conversion_matrix = self.i3d.conversion_matrix @ transform_matrix @ self.i3d.conversion_matrix.inverted()

            final_translation, final_rotation, final_scale = conversion_matrix.decompose()
            if export_rotation:
                final_rotation = final_rotation.to_euler('XYZ')

            visibility = "true"
            if any(fcurve.data_path.endswith("hide_viewport") for fcurve in action.fcurves):
                hide_fcurve = next((f for f in action.fcurves if f.data_path.endswith("hide_viewport")), None)
                if hide_fcurve and hide_fcurve.evaluate(frame) > 0.5:
                    visibility = "false"

            keyframe_attribs = {"time": str(time_ms), "visibility": visibility}
            if export_translation:
                keyframe_attribs["translation"] = "{0:.6g} {1:.6g} {2:.6g}".format(*final_translation)
            if export_rotation:
                keyframe_attribs["rotation"] = "{0:.6g} {1:.6g} {2:.6g}".format(*[math.degrees(angle)
                                                                                  for angle in final_rotation])
            if export_scale:
                keyframe_attribs["scale"] = "{0:.6g} {1:.6g} {2:.6g}".format(*final_scale)

            xml_i3d.SubElement(keyframes_element, "Keyframe", keyframe_attribs)
            self.logger.debug(f"Extracted keyframe at frame {frame} with visibility {visibility}")

        self.logger.debug(f"Extracted {len(keyframe_data)} keyframes for '{self.animated_object.name}'")
