"""This module contains shared functionality between the different modules of the i3dio addon"""
from __future__ import annotations  # Enables python 4.0 annotation typehints fx. class self-referencing
from typing import (Union)
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from typing import Type
import logging

import bpy

from . import debugging
from . import xml_i3d


class I3D:
    """A special node which is the root node for the entire I3D file. It essentially represents the i3d file"""
    def __init__(self, name: str, i3d_file_path: str):
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

    # Private Methods ##################################################################################################
    def _next_available_id(self, id_type: str) -> int:
        next_id = self._ids[id_type]
        self._ids[id_type] += 1
        return next_id

    def _add_node(self, node_type: Type[Node], object_: bpy.types.Object, parent: Node = None) -> Node:
        node = node_type(self._next_available_id('node'), object_, parent)
        if parent is None:
            self.scene_root_nodes.append(node)
        return node

    # Public Methods ###################################################################################################
    def add_shape_node(self, mesh_object: bpy.types.Object, parent: Node = None) -> Node:
        """Add a blender object with a data type of MESH to the scenegraph as a Shape node"""
        return self._add_node(ShapeNode, mesh_object, parent)

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

    def __init__(self, id_: int, blender_object: [bpy.types.Object, bpy.types.Collection], parent: Node or None = None):
        self.id = id_
        self.parent = parent
        self.children = []

        self.blender_object = blender_object

        attributes = {'name': blender_object.name, 'nodeId': id_}
        try:
            parent.add_child(self)
            self.element = ET.SubElement(type(self).ELEMENT_TAG, attributes, parent.element)
        except AttributeError:
            self.element = ET.Element(type(self).ELEMENT_TAG, attributes)

    def __str__(self):
        return f"{self.id}"

    def add_child(self, node: Node):
        self.children.append(node)


class ShapeNode(Node):
    @property
    @classmethod
    def ELEMENT_TAG(cls):
        return 'Shape'

    def __init__(self, id_: int, mesh_object: bpy.types.Object, parent: Node or None = None):
        super().__init__(id_, mesh_object, parent)
        self.indexed_triangle_set = None