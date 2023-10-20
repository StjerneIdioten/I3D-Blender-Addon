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

        self._name = self.blender_object.name
        if (prefix:= bpy.context.scene.i3dio.object_sorting_prefix) != "" and (prefix_index := self._name.find(prefix)) != -1 and prefix_index < (len(self._name) - 1):
            self._name = self._name[prefix_index + 1:]

        super().__init__(id_, i3d, parent)

        self.logger.debug(f"New Name: {self._name}")

        try:
            self.parent.add_child(self)
        except AttributeError:
            pass

        self.add_i3d_mapping_to_xml()

        self.logger.debug(f"Initialized as a '{self.__class__.__name__}'")

    @property
    def name(self):
        return self._name

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
            xml_i3d.write_i3d_properties(self.blender_object, self.blender_object.i3d_attributes, self.xml_elements)
        except AttributeError:
            # Not all nodes has general node properties, such as collections.
            pass

        # Try to write node specific properties, not all nodes have these (Such as cameras or collections)
        try:
            data = self.blender_object.data
        except AttributeError:
            self.logger.debug(f'Is a "{type(self.blender_object).__name__}", which does not have "data"')
        else:
            try:
                xml_i3d.write_i3d_properties(data, self.blender_object.data.i3d_attributes, self.xml_elements)
            except AttributeError:
                self.logger.debug(f'Has no data specific attributes')

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

    def add_i3d_mapping_to_xml(self):
        try:
            if getattr(self.blender_object.i3d_mapping, 'is_mapped'):
                self.i3d.i3d_mapping.append(self)
        except AttributeError:
            pass


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
