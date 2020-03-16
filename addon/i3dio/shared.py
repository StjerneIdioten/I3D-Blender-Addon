"""This module contains shared functionality between the different modules of the i3dio addon"""
from __future__ import annotations  # Enables python 4.0 annotation typehints fx. class self-referencing
from typing import (Union)
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from typing import Type

import bpy


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


class I3D:
    """A special node which is the root node for the entire I3D file. It essentially represents the i3d file"""
    def __init__(self):
        self._ids = {
            'node': 1,
            'material': 1,
            'file': 1,
        }

        self.children = []

    # Private Methods ##################################################################################################
    def _next_available_id(self, id_type: str) -> int:
        next_id = self._ids[id_type]
        self._ids[id_type] += 1
        return next_id

    def _add_node(self, node_type: Type[Node], object_: bpy.types.Object, parent: Node = None) -> Node:
        node = node_type(self._next_available_id('node'), object_, parent)
        if parent is None:
            self.children.append(node)
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

        traverse(self.children[0])

        tree_string += f"{longest_string * '-'}\n"

        return f"{longest_string * '-'}\n" + tree_string

