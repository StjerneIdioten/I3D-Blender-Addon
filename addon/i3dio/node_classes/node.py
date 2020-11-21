from __future__ import annotations  # Enables python 4.0 annotation typehints fx. class self-referencing
from abc import (ABC, abstractmethod)
import logging
from typing import (Union, Dict)
import math
import mathutils
import bpy

from .. import (
            debugging,
            utility,
            xml_i3d
)

from ..i3d import I3D


class Node(ABC):
    @property
    @classmethod
    @abstractmethod
    def ELEMENT_TAG(cls):  # Every node type has a certain tag in the i3d-file fx. 'Shape' or 'Light'
        return NotImplementedError

    @property
    @classmethod
    @abstractmethod
    def ID_FIELD_NAME(cls):  # The name of the id tag changes from node to node, but it is still an ID
        return NotImplementedError

    @property
    @classmethod
    @abstractmethod
    def NAME_FIELD_NAME(cls):  # The name of the name tag can change from node to node
        return NotImplementedError

    def __init__(self, id_: int, i3d: I3D, parent: Union[Node, None] = None):
        self.id = id_
        self.i3d = i3d
        self.parent = parent
        self.xml_elements = {}
        self.logger = self._set_logging_output_name_field()
        self._create_xml_element()
        self.populate_xml_element()

    @property
    @abstractmethod
    def name(self):
        raise NotImplementedError

    @property
    @abstractmethod
    def element(self):
        raise NotImplementedError

    @element.setter
    @abstractmethod
    def element(self, value):
        raise NotImplementedError

    def _set_logging_output_name_field(self):
        return debugging.ObjectNameAdapter(logging.getLogger(f"{__name__}.{type(self).__name__}"),
                                           {'object_name': self.name})

    def _create_xml_element(self):
        self.logger.debug(f"Filling out basic attributes, {{name='{self.name}', nodeId='{self.id}'}}")
        attributes = {type(self).NAME_FIELD_NAME: self.name, type(self).ID_FIELD_NAME: str(self.id)}
        try:
            self.element = xml_i3d.SubElement(self.parent.element, type(self).ELEMENT_TAG, attributes)
            self.logger.debug(f"has parent element with name [{self.parent.name}]")
        except AttributeError:
            self.element = xml_i3d.Element(type(self).ELEMENT_TAG, attributes)

    def populate_xml_element(self):
        # This should be overwritten in derived nodes, if they need to add extra attributes/xml-elements to the base
        # element. This get's call from the default constructor after the base xml element has been created.
        pass

    def _write_attribute(self, name: str, value, element_idx=None) -> None:
        if element_idx is None:
            xml_i3d.write_attribute(self.element, name, value)
        else:
            xml_i3d.write_attribute(self.xml_elements[element_idx], name, value)


class SceneGraphNode(Node):
    NAME_FIELD_NAME = 'name'
    ID_FIELD_NAME = 'nodeId'

    def __init__(self, id_: int,
                 blender_object: [bpy.types.Object, bpy.types.Collection, None],
                 i3d: I3D,
                 parent: Union[SceneGraphNode, None] = None,
                 ):
        self.children = []
        self.blender_object = blender_object
        self.xml_elements: Dict[str, Union[xml_i3d.XML_Element, None]] = {'Node': None}
        super().__init__(id_, i3d, parent)

        try:
            self.parent.add_child(self)
        except AttributeError:
            pass

        try:
            if getattr(self.blender_object.i3d_mapping, 'is_mapped'):
                self.i3d.i3d_mapping.append(self)
        except AttributeError:
            pass

        self.logger.debug(f"Initialized as a '{self.__class__.__name__}'")

    @property
    def name(self):
        return self.blender_object.name

    @property
    def element(self) -> Union[xml_i3d.XML_Element, None]:
        return self.xml_elements['Node']

    @element.setter
    def element(self, value):
        self.xml_elements['Node'] = value

    def __str__(self):
        return f"{self.name}"

    def _write_properties(self):
        # Write general node properties (Transform properties in Giants Engine)
        try:
            xml_i3d.write_property_group(self.blender_object.i3d_attributes, self.xml_elements)
        except AttributeError:
            # Not all nodes has general node properties, such as collections.
            pass

        # Try to write node specific properties, not all nodes have these (Such as cameras)
        try:
            xml_i3d.write_property_group(self.blender_object.data.i3d_attributes, self.xml_elements)
        except AttributeError:
            self.logger.debug('Has no data specific attributes')

    def _write_user_attributes(self):
        try:
            self.i3d.add_user_attributes(self.blender_object.i3d_user_attributes.attribute_list, self.id)
        except AttributeError:
            pass

    @property
    @abstractmethod
    def _transform_for_conversion(self) -> Union[mathutils.Matrix, None]:
        """Different node types have different requirements for getting converted into i3d coordinates"""
        raise NotImplementedError

    def _add_transform_to_xml_element(self, object_transform: Union[mathutils.Matrix, None]) -> None:
        """This method checks the parent and adjusts the transform before exporting"""
        if object_transform is None:
            # This essentially sets the entire transform to be default. Since GE loads defaults when no data is present.
            return

        self.logger.debug(f"transforming to new transform-basis with {object_transform}")
        matrix = object_transform
        if self.parent is not None:
            if type(self.parent) in [CameraNode, LightNode]:
                matrix = self.i3d.conversion_matrix.inverted() @ matrix
                self.logger.debug(f"Is transformed to accommodate flipped z-axis in GE of parent Light/Camera")

        translation = matrix.to_translation()
        self.logger.debug(f"translation is {translation}")
        if not utility.vector_compare(translation, mathutils.Vector((0, 0, 0))):
            translation = "{0:.6g} {1:.6g} {2:.6g}".format(
                *[x * bpy.context.scene.unit_settings.scale_length for x in translation])

            self._write_attribute('translation', translation)
            self.logger.debug(f"has translation: [{translation}]")
        else:
            self.logger.debug(f"translation is default")

        # Rotation, no unit scaling since it will always be degrees.
        rotation = [math.degrees(axis) for axis in matrix.to_euler('XYZ')]
        if not utility.vector_compare(mathutils.Vector(rotation), mathutils.Vector((0, 0, 0))):
            rotation = "{0:.6g} {1:.6g} {2:.6g}".format(*rotation)
            self._write_attribute('rotation', rotation)
            self.logger.debug(f"has rotation(degrees): [{rotation}]")

        # Scale
        if matrix.is_negative:
            self.logger.error(f"has one or more negative scaling components, "
                              f"which is not supported in Giants Engine. Scale reset to (1, 1, 1)")
        else:
            scale = matrix.to_scale()
            if not utility.vector_compare(scale, mathutils.Vector((1, 1, 1))):
                scale = "{0:.6g} {1:.6g} {2:.6g}".format(*scale)

                self._write_attribute('scale', scale)
                self.logger.debug(f"has scale: [{scale}]")

    def populate_xml_element(self):
        self._write_properties()
        self._write_user_attributes()
        self._add_transform_to_xml_element(self._transform_for_conversion)

    def add_child(self, node: SceneGraphNode):
        self.children.append(node)


class TransformGroupNode(SceneGraphNode):
    ELEMENT_TAG = 'TransformGroup'

    def __init__(self, id_: int, empty_object: [bpy.types.Object, bpy.types.Collection],
                 i3d: I3D, parent: SceneGraphNode or None = None):
        super().__init__(id_=id_, blender_object=empty_object, i3d=i3d, parent=parent)

    @property
    def _transform_for_conversion(self) -> mathutils.Matrix:
        try:
            conversion_matrix = self.i3d.conversion_matrix @ \
                                self.blender_object.matrix_local @ \
                                self.i3d.conversion_matrix.inverted()
        except AttributeError:
            self.logger.info(f"is a Collection and it will be exported as a transformgroup with default transform")
            conversion_matrix = None
        return conversion_matrix


class LightNode(SceneGraphNode):
    ELEMENT_TAG = 'Light'

    def __init__(self, id_: int, light_object: bpy.types.Object, i3d: I3D, parent: SceneGraphNode or None = None):
        super().__init__(id_=id_, blender_object=light_object, i3d=i3d, parent=parent)

    @property
    def _transform_for_conversion(self) -> mathutils.Matrix:
        return self.i3d.conversion_matrix @ self.blender_object.matrix_local

    def populate_xml_element(self):
        light = self.blender_object.data
        self.logger.info(f"Is a light of type {light.type!r}")
        falloff_type = None
        if light.type == 'POINT':
            light_type = 'point'
            falloff_type = light.falloff_type
        elif light.type == 'SUN':
            light_type = 'directional'
        elif light.type == 'SPOT':
            light_type = 'spot'
            falloff_type = light.falloff_type
            cone_angle = math.degrees(light.spot_size)
            self._write_attribute('coneAngle', cone_angle)
            self.logger.info(f"Has a cone angle of {cone_angle}")
            # Blender spot 0.0 -> 1.0, GE spot 0.0 -> 5.0
            drop_off = 5.0 * light.spot_blend
            self._write_attribute('dropOff', drop_off)
            self.logger.info(f"Has a drop off of {drop_off}")
        elif light.type == 'AREA':
            light_type = 'point'
            self.logger.warning(f"Is an AREA light, which is not supported and defaults to point light")

        self._write_attribute('type', light_type)

        color = "{0:f} {1:f} {2:f}".format(*light.color)
        self._write_attribute('color', color)
        self.logger.info(f"Has color {color}")

        self._write_attribute('range', light.distance)
        self.logger.info(f"Has range {light.distance}")

        self._write_attribute('castShadowMap', light.use_shadow)
        self.logger.info('casts shadows' if light.use_shadow else 'does not cast shadows')

        if falloff_type is not None:
            if falloff_type == 'CONSTANT':
                falloff_type = 0
                self.logger.info(f"Has decay rate of type {'CONSTANT'} which is '0' in i3d")
            elif falloff_type == 'INVERSE_LINEAR':
                falloff_type = 1
                self.logger.info(f"Has decay rate of type {'INVERSE_LINEAR'} which is '1' in i3d")
            elif falloff_type == 'INVERSE_SQUARE':
                falloff_type = 2
                self.logger.info(f"has decay rate of type {'INVERSE_SQUARE'} which is '2' in i3d")
            self._write_attribute('decayRate', falloff_type)

        super().populate_xml_element()


class CameraNode(SceneGraphNode):
    ELEMENT_TAG = 'Camera'

    def __init__(self, id_: int, camera_object: bpy.types.Object, i3d: I3D, parent: SceneGraphNode or None = None):
        super().__init__(id_=id_, blender_object=camera_object, i3d=i3d, parent=parent)

    @property
    def _transform_for_conversion(self) -> mathutils.Matrix:
        return self.i3d.conversion_matrix @ self.blender_object.matrix_local

    def populate_xml_element(self):
        camera = self.blender_object.data
        self._write_attribute('fov', camera.lens)
        self._write_attribute('nearClip', camera.clip_start)
        self._write_attribute('farClip', camera.clip_end)
        self.logger.info(f"FOV: '{camera.lens}', Near Clip: '{camera.clip_start}', Far Clip: '{camera.clip_end}'")
        if camera.type == 'ORTHO':
            self._write_attribute('orthographic', True)
            self._write_attribute('orthographicHeight', camera.ortho_scale)
            self.logger.info(f"Orthographic camera with height '{camera.ortho_scale}'")
        super().populate_xml_element()
