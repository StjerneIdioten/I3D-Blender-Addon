"""This module contains shared functionality between the different modules of the i3dio addon"""
from __future__ import annotations  # Enables python 4.0 annotation typehints fx. class self-referencing
from typing import (Union, Dict)
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from typing import Type
import logging
import math
import mathutils
import bpy

from . import debugging
from . import xml_i3d
from . import utility

logger = logging.getLogger(__name__)


class I3D:
    """A special node which is the root node for the entire I3D file. It essentially represents the i3d file"""
    def __init__(self, name: str, i3d_file_path: str, conversion_matrix: mathutils.Matrix):
        self.logger = debugging.ObjectNameAdapter(logging.getLogger(f"{__name__}.{type(self).__name__}"),
                                                  {'object_name': name})
        self._ids = {
            'node': 1,
            'material': 1,
            'file': 1,
        }

        self.paths = {
            'i3d_file_path': i3d_file_path,
        }

        self.xml_elements = {'Root': ET.Element('i3D', {**{'name': name}, **xml_i3d.root_attributes})}
        self.xml_elements['Asset'] = ET.SubElement(self.xml_elements['Root'], 'Asset')
        self.xml_elements['Files'] = ET.SubElement(self.xml_elements['Root'], 'Files')
        self.xml_elements['Materials'] = ET.SubElement(self.xml_elements['Root'], 'Materials')
        self.xml_elements['Shapes'] = ET.SubElement(self.xml_elements['Root'], 'Shapes')
        self.xml_elements['Dynamics'] = ET.SubElement(self.xml_elements['Root'], 'Dynamics')
        self.xml_elements['Scene'] = ET.SubElement(self.xml_elements['Root'], 'Scene')
        self.xml_elements['Animation'] = ET.SubElement(self.xml_elements['Root'], 'Animation')
        self.xml_elements['UserAttributes'] = ET.SubElement(self.xml_elements['Root'], 'UserAttributes')

        self.scene_root_nodes = []
        self.conversion_matrix = conversion_matrix

    # Private Methods ##################################################################################################
    def _next_available_id(self, id_type: str) -> int:
        next_id = self._ids[id_type]
        self._ids[id_type] += 1
        return next_id

    def _add_node(self, node_type: Type[Node], object_: bpy.types.Object, parent: Node = None) -> Node:
        node = node_type(self._next_available_id('node'), object_, self, parent)
        node.export_object_to_xml()
        if parent is None:
            self.scene_root_nodes.append(node)
            self.xml_elements['Scene'].append(node.element)
        return node

    # Public Methods ###################################################################################################
    def add_shape_node(self, mesh_object: bpy.types.Object, parent: Node = None) -> Node:
        """Add a blender object with a data type of MESH to the scenegraph as a Shape node"""
        return self._add_node(ShapeNode, mesh_object, parent)

    def add_transformgroup_node(self, empty_object: [bpy.types.Object, bpy.types.Collection], parent: Node = None) -> Node:
        return self._add_node(TransformGroupNode, empty_object, parent)

    def add_light_node(self, light_object: bpy.types.Object, parent: Node = None) -> Node:
        """Add a blender object with a data type of MESH to the scenegraph as a Shape node"""
        return self._add_node(LightNode, light_object, parent)

    def add_camera_node(self, camera_object: bpy.types.Object, parent: Node = None) -> Node:
        """Add a blender object with a data type of MESH to the scenegraph as a Shape node"""
        return self._add_node(CameraNode, camera_object, parent)

    def get_scene_as_formatted_string(self):
        """Tree represented as depth first"""
        tree_string = ""
        longest_string = 0

        def traverse(node, indents=0):
            nonlocal tree_string, longest_string
            indent = indents * '  '
            line = f"|{indent}{node}\n"
            longest_string = len(line) if len(line) > longest_string else longest_string
            tree_string += line
            for child in node.children.values():
                traverse(child, indents + 1)

        traverse(self.scene_root_nodes[0])

        tree_string += f"{longest_string * '-'}\n"

        return f"{longest_string * '-'}\n" + tree_string

    def export_to_i3d_file(self) -> None:
        xml_i3d.add_indentations(self.xml_elements['Root'])
        ET.ElementTree(self.xml_elements['Root']).write(self.paths['i3d_file_path'],
                                                        xml_declaration=True,
                                                        encoding='iso-8859-1',
                                                        method='xml')


class Node(ABC):
    @property
    @classmethod
    @abstractmethod
    def ELEMENT_TAG(cls):  # Every node type has a certain tag in the i3d-file fx. 'Shape' or 'Light'
        return NotImplementedError

    def __init__(self, id_: int,
                 blender_object: [bpy.types.Object, bpy.types.Collection],
                 i3d: I3D,
                 parent: Node or None = None,
                 ):
        self.id = id_
        self.parent = parent
        self.children = []
        self.i3d = i3d
        self.blender_object = blender_object
        self.xml_elements: Dict[str, Union[ET.Element, None]] = {'Node': None}
        self.logger = debugging.ObjectNameAdapter(logging.getLogger(f"{__name__}.{type(self).__name__}"),
                                                  {'object_name': self.blender_object.name})

        try:
            self.parent.add_child(self)
        except AttributeError:
            pass

        self._create_xml_element()
        self.logger.debug(f"Initialized as a '{self.__class__.__name__}'")

    @property
    def element(self) -> Union[ET.Element, None]:
        return self.xml_elements['Node']

    @element.setter
    def element(self, value):
        self.xml_elements['Node'] = value

    def __str__(self):
        return f"{self.id}"

    def _write_attribute(self, name: str, value, element_idx='Node') -> None:
        xml_i3d.write_attribute(self.xml_elements[element_idx], name, value)

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

    @property
    @abstractmethod
    def _transform_for_conversion(self) -> Union[mathutils.Matrix, None]:
        """Different node types have different requirements for getting converted into i3d coordinates"""
        raise NotImplementedError

    def _create_xml_element(self) -> ET.Element:
        self.logger.debug(f"Filling out basic attributes, {{name='{self.blender_object.name}', nodeId='{self.id}'}}")
        attributes = {'name': self.blender_object.name, 'nodeId': self.id}
        try:
            self.element = ET.SubElement(self.parent.element, type(self).ELEMENT_TAG, attributes)
            self.logger.debug(f"has parent element with name [{self.parent.blender_object.name}]")
        except AttributeError:
            self.logger.debug(f"has no parent element")
            self.element = ET.Element(type(self).ELEMENT_TAG, attributes)

        self._write_attribute('name', self.blender_object.name)
        self._write_attribute('nodeId', self.id)

        return self.element

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

    def export_object_to_xml(self):
        self._write_properties()
        self._add_transform_to_xml_element(self._transform_for_conversion)

    def add_child(self, node: Node):
        self.children.append(node)


class ShapeNode(Node):
    ELEMENT_TAG = 'Shape'

    def __init__(self, id_: int, mesh_object: bpy.types.Object, i3d: I3D, parent: Node or None = None):
        super().__init__(id_=id_, blender_object=mesh_object, i3d=i3d, parent=parent)
        self.xml_elements['IndexedTriangleSet'] = None

    @property
    def _transform_for_conversion(self) -> mathutils.Matrix:
        return self.i3d.conversion_matrix @ self.blender_object.matrix_local @ self.i3d.conversion_matrix.inverted()


class TransformGroupNode(Node):
    ELEMENT_TAG = 'TransformGroup'

    def __init__(self, id_: int, empty_object: [bpy.types.Object, bpy.types.Collection],
                 i3d: I3D, parent: Node or None = None):
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


class LightNode(Node):
    ELEMENT_TAG = 'Light'

    def __init__(self, id_: int, light_object: bpy.types.Object, i3d: I3D, parent: Node or None = None):
        super().__init__(id_=id_, blender_object=light_object, i3d=i3d, parent=parent)

    @property
    def _transform_for_conversion(self) -> mathutils.Matrix:
        return self.i3d.conversion_matrix @ self.blender_object.matrix_local

    def export_object_to_xml(self):
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


class CameraNode(Node):
    ELEMENT_TAG = 'Camera'

    def __init__(self, id_: int, camera_object: bpy.types.Object, i3d: I3D, parent: Node or None = None):
        super().__init__(id_=id_, blender_object=camera_object, i3d=i3d, parent=parent)

    @property
    def _transform_for_conversion(self) -> mathutils.Matrix:
        return self.i3d.conversion_matrix @ self.blender_object.matrix_local

    def export_object_to_xml(self):
        super().export_object_to_xml()
        camera = self.blender_object.data
        self._write_attribute('fov', camera.lens)
        self._write_attribute('nearClip', camera.clip_start)
        self._write_attribute('farClip', camera.clip_end)
        self.logger.info(f"FOV: '{camera.lens}', Near Clip: '{camera.clip_start}', Far Clip: '{camera.clip_end}'")
        if camera.type == 'ORTHO':
            self._write_attribute('orthographic', True)
            self._write_attribute('orthographicHeight', camera.ortho_scale)
            self.logger.info(f"Orthographic camera with height '{camera.ortho_scale}'")
