#!/usr/bin/env python3

"""
    ##### BEGIN GPL LICENSE BLOCK #####
  This program is free software; you can redistribute it and/or
  modify it under the terms of the GNU General Public License
  as published by the Free Software Foundation; either version 2
  of the License, or (at your option) any later version.
  This program is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU General Public License for more details.
  You should have received a copy of the GNU General Public License
  along with this program; if not, write to the Free Software Foundation,
  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
 ##### END GPL LICENSE BLOCK #####
"""
from __future__ import annotations  # Enables python 4.0 annotation typehints fx. class self-referencing
from typing import Union
import sys
# Old exporter used cElementTree for speed, but it was deprecated to compatibility status in python 3.3
import xml.etree.ElementTree as ET  # Technically not following pep8, but this is the naming suggestion from the module
import bpy


# Exporter is a singleton
class Exporter:

    def __init__(self, filepath: str):
        self._scene_graph = SceneGraph()
        self._export_only_selection = False
        self._filepath = filepath

        self._generate_scene_graph()
        self._xml_build_structure()

        # self._xml_parse_from_blender()
        # self._xml_export_to_file()

    def _generate_scene_graph(self):

        selection = bpy.context.scene.i3dio.selection
        if selection == 'ALL':
            selection = bpy.context.scene.collection
        elif selection == 'ACTIVE_COLLECTION':
            selection = bpy.context.view_layer.active_layer_collection.collection
        elif selection == 'SELECTED_OBJECTS':
            pass

        self._generate_scene_graph_item(selection, self._scene_graph.nodes[0])

        # for obj in bpy.context.selected_objects:
        #    # Objects directly in the scene only has the 'Master Collection' in the list,
        #    # which disappears once the object is added to any other collection
        #    if bpy.context.scene.collection in obj.users_collection and obj.parent is None:
        #       print(f"{obj.name!r} is at scene root")
        #       self._generate_scene_graph_item(obj, self._scene_graph.nodes[0])
        print(self._scene_graph)

    def _generate_scene_graph_item(self,
                                   blender_object: Union[bpy.types.Object, bpy.types.Collection],
                                   parent: SceneGraph.Node,
                                   unpack_collection: bool = False):

        node = None
        if unpack_collection:
            print(f'Unpack')
            node = parent
        else:
            node = self._scene_graph.add_node(blender_object, parent)
            print(f"Added Node with ID {node.id} and name {node.blender_object.name!r}")

        # Expand collection tree into the collection instance
        if isinstance(blender_object, bpy.types.Object):
            if blender_object.type == 'EMPTY':
                if blender_object.instance_collection is not None:
                    print(f'This is a collection instance')
                    self._generate_scene_graph_item(blender_object.instance_collection, node, unpack_collection=True)

        # Gets child objects/collections
        if isinstance(blender_object, bpy.types.Object):
            print(f'Children of object')
            for child in blender_object.children:
                self._generate_scene_graph_item(child, node)

        # Gets child objects if it is a collection
        if isinstance(blender_object, bpy.types.Collection):
            print(f'Children collections')
            for child in blender_object.children:
                self._generate_scene_graph_item(child, node)

            print(f'Children objects in collection')
            for child in blender_object.objects:
                if child.parent is None:
                    self._generate_scene_graph_item(child, node)

        #             if obj.type == 'EMPTY':
        #                 print(obj.instance_collection)

    def _xml_build_structure(self) -> None:
        """Builds the i3d file conforming to the standard specified at
        https://gdn.giants-software.com/documentation_i3d.php
        """
        self._tree = ET.Element('i3D')  # Create top level element
        self._tree.set('name', bpy.path.display_name_from_filepath(self._filepath))  # Name attribute

        # Xml scheme attributes as required by the i3d standard, even though most of the links are dead.
        self._tree.set('version', "1.6")
        self._tree.set('xmlns:xsi', "http://www.w3.org/2001/XMLSchema-instance")
        self._tree.set('xsi:noNamespaceSchemaLocation', "http://i3d.giants.ch/schema/i3d-1.6.xsd")

        # Asset export: Currently just a notice of which tool was used for generating the file
        element = ET.SubElement(self._tree, 'Asset')
        element = ET.SubElement(element, 'Export')
        element.set('program', 'Blender Exporter (Community)')
        element.set('version', sys.modules['i3dio'].bl_info.get('version'))  # Fetch version directly from bl_info

        # File export: References to external files such as images for materials (diffuse, normals etc.)
        ET.SubElement(self._tree, 'Files')

        # Material export: List of all materials used in the project
        ET.SubElement(self._tree, 'Materials')

        # Shapes export: All the shape data in the form of vertices and triangles. This section takes up a lot of space
        # and it would be preferable to export to an external shapes file (Giants Engine can do it by a binary save)
        ET.SubElement(self._tree, 'Shapes')

        # Dynamics export: Particle systems
        ET.SubElement(self._tree, 'Dynamics')

        # Scenegraph export: The entire scenegraph structure, with references to light, cameras, transforms and shapes
        ET.SubElement(self._tree, 'Scene')

        # Animation export: Animation sets with keyframes
        ET.SubElement(self._tree, 'Animation')

        # User attributes export: User generated attributes that might be used in scripts etc.
        ET.SubElement(self._tree, 'UserAttributes')

    def _xml_export_to_file(self) -> None:

        self._indent(self._tree)

        try:
            ET.ElementTree(self._tree).write(self._filepath, xml_declaration=True, encoding='iso-8859-1', method='xml')
            print(f"Exported to {self._filepath}")
        except Exception as exception:  # A bit slouchy exception handling. Should be more specific and not catch all
            print(exception)

    @staticmethod
    def _xml_write_int(element: ET.Element, attribute: str, value: int) -> None:
        """Writes the attribute into the element with formatting for ints"""
        element.set(attribute, f"{value:d}")

    @staticmethod
    def _xml_write_float(element: ET.Element, attribute: str, value: float) -> None:
        """Writes the attribute into the element with formatting for floats"""
        element.set(attribute, f"{value:.7f}")

    @staticmethod
    def _xml_write_bool(element: ET.Element, attribute: str, value: bool) -> None:
        """Writes the attribute into the element with formatting for booleans"""
        element.set(attribute, f"{value!s}".lower())

    @staticmethod
    def _xml_write_string(element: ET.Element, attribute: str, value: str) -> None:
        """Writes the attribute into the element with formatting for strings"""
        element.set(attribute, value)

    @staticmethod
    def _indent(elem: ET.Element, level: int = 0) -> None:
        """
        Used for pretty printing the xml since etree does not indent elements and keeps everything in one continues
        string and since i3d files are supposed to be human readable, we need indentation. There is a patch for
        pretty printing on its way in the standard library, but it is not available until python 3.9 comes around.

        The module 'lxml' could also be used since it has pretty-printing, but that would introduce an external
        library dependency for the addon.

        The source code from this solution is taken from http://effbot.org/zone/element-lib.htm#prettyprint

        It recursively checks every element and adds a newline + space indents to the element to make it pretty and
        easily readable. This technically changes the xml, but the giants engine does not seem to mind the linebreaks
        and spaces, when parsing the i3d file.
        """
        indents = '\n' + level * '  '
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = indents + '  '
            if not elem.tail or not elem.tail.strip():
                elem.tail = indents
            for elem in elem:
                Exporter._indent(elem, level + 1)
            if not elem.tail or not elem.tail.strip():
                elem.tail = indents
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = indents


class SceneGraph(object):

    class Node(object):
        def __init__(self,
                     node_id: int = 0,
                     blender_object: Union[bpy.types.Object, bpy.types.Collection] = None,
                     parent: SceneGraph.Node = None):

            self.children = {}
            self.blender_object = blender_object
            self.id = node_id
            self.parent = parent

            if parent is not None:
                parent.add_child(self)

        def __str__(self):
            return f"{self.id}|{self.blender_object.name!r}"

        def add_child(self, node: SceneGraph.Node):
            self.children[node.id] = node

        def remove_child(self, node: SceneGraph.Node):
            del self.children[node.id]

    def __init__(self):
        self.ids = {
            'node': 0
        }
        self.nodes = {}
        self.shapes = {}
        self.materials = {}
        self.files = {}
        # Create the root node
        self.add_node()  # Add the root node that contains the tree

    def __str__(self):
        """Three represented as depth first"""
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

        traverse(self.nodes[1])  # Starts at the first element instead since the root isn't necessary to print out

        tree_string += f"{longest_string * '-'}\n"

        return f"{longest_string * '-'}\n" + tree_string

    def add_node(self,
                 blender_object: Union[bpy.types.Object, bpy.types.Collection] = None,
                 parent: SceneGraph.Node = None) -> SceneGraph.Node:
        new_node = SceneGraph.Node(self.ids['node'], blender_object, parent)
        self.nodes[new_node.id] = new_node
        self.ids['node'] += 1
        return new_node


