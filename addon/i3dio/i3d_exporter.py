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

        self._xml_build()

    def _xml_build(self) -> int:
        """Builds the i3d file conforming to the standard specified at
        https://gdn.giants-software.com/documentation_i3d.php
        """
        self._root_element = ET.Element('i3D')  # Create top level element
        self._root_element.set('name', bpy.path.display_name_from_filepath(self._filepath))  # Name attribute

        # Xml scheme attributes as required by the i3d standard, even though most of the links are dead.
        self._root_element.set('version', "1.6")
        self._root_element.set('xmlns:xsi', "http://www.w3.org/2001/XMLSchema-instance")
        self._root_element.set('xsi:noNamespaceSchemaLocation', "http://i3d.giants.ch/schema/i3d-1.6.xsd")

        # Asset export: Currently just a notice of which tool was used for generating the file
        element = ET.SubElement(self._root_element, 'Asset')
        element = ET.SubElement(element, 'Export')
        element.set('program', 'Blender Exporter (Community)')
        element.set('version', sys.modules['i3dio'].bl_info.get('version'))  # Fetch version directly from bl_info

        # File export: References to external files such as images for materials (diffuse, normals etc.)
        ET.SubElement(self._root_element, 'Files')

        # Material export: List of all materials used in the project
        ET.SubElement(self._root_element, 'Materials')

        # Shapes export: All the shape data in the form of vertices and triangles. This section takes up a lot of space
        # and it would be preferable to export to an external shapes file (Giants Engine can do it by a binary save)
        ET.SubElement(self._root_element, 'Shapes')

        # Dynamics export: Particle systems
        ET.SubElement(self._root_element, 'Dynamics')

        # Scenegraph export: The entire scenegraph structure, with references to light, cameras, transforms and shapes
        ET.SubElement(self._root_element, 'Scene')

        # Animation export: Animation sets with keyframes
        ET.SubElement(self._root_element, 'Animation')

        # User attributes export: User generated attributes that might be used in scripts etc.
        ET.SubElement(self._root_element, 'UserAttributes')

        self._indent(self._root_element)
        self._tree = ET.ElementTree(self._root_element)
        try:
            self._tree.write(self._filepath, xml_declaration=True, encoding='iso-8859-1', method='xml')
            print("Exported to {0}".format(self._filepath))
        except Exception as exception:  # A bit slouchy exception handling. Should be more specific and not catch all
            print(exception)
            return 1
        return 0


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

    def __init__(self):
        self.ids = {
            'node':     0,
            'shape':    0,
            'mat':      0
        }
        self._nodes = {}
        self._shapes = {}
        self._materials = {}
        self._files = {}
        self._nodes["ROOT"] = SceneNode("ROOT")


class SceneNode(object):
    def __init__(self, node, parent="ROOT", node_id=0):
        self.children = []
