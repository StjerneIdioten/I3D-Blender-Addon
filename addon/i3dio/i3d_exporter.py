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
from enum import Enum
import sys
import math
import mathutils
# Old exporter used cElementTree for speed, but it was deprecated to compatibility status in python 3.3
import xml.etree.ElementTree as ET  # Technically not following pep8, but this is the naming suggestion from the module
import bpy
import bpy_extras
import bmesh


# Exporter is a singleton
class Exporter:

    def __init__(self, filepath: str):
        self._scene_graph = SceneGraph()
        self._export_only_selection = False
        self._filepath = filepath

        self.ids = {
            'shape': 1,
            'material': 1,
            'file': 1
        }

        self.shape_material_indexes = {}

        self._xml_build_skeleton_structure()
        self._xml_build_scene_graph()
        self._xml_parse_scene_graph()

        self._xml_export_to_file()

    def _xml_build_scene_graph(self):

        def new_graph_node(blender_object: Union[bpy.types.Object, bpy.types.Collection],
                           parent: SceneGraph.Node,
                           unpack_collection: bool = False):

            node = None
            if unpack_collection:
                node = parent
            else:
                node = self._scene_graph.add_node(blender_object, parent)
                print(f"Added Node with ID {node.id} and name {node.blender_object.name!r}")

            # Expand collection tree into the collection instance
            if isinstance(blender_object, bpy.types.Object):
                if blender_object.type == 'EMPTY':
                    if blender_object.instance_collection is not None:
                        # print(f'This is a collection instance')
                        new_graph_node(blender_object.instance_collection, node, unpack_collection=True)

            # Gets child objects/collections
            if isinstance(blender_object, bpy.types.Object):
                # print(f'Children of object')
                for child in blender_object.children:
                    new_graph_node(child, node)

            # Gets child objects if it is a collection
            if isinstance(blender_object, bpy.types.Collection):
                # print(f'Children collections')
                for child in blender_object.children:
                    new_graph_node(child, node)

                # print(f'Children objects in collection')
                for child in blender_object.objects:
                    if child.parent is None:
                        new_graph_node(child, node)

            #             if obj.type == 'EMPTY':
            #                 print(obj.instance_collection)

        selection = bpy.context.scene.i3dio.selection
        if selection == 'ALL':
            selection = bpy.context.scene.collection
            new_graph_node(selection, self._scene_graph.nodes[0])
        elif selection == 'ACTIVE_COLLECTION':
            selection = bpy.context.view_layer.active_layer_collection.collection
            new_graph_node(selection, self._scene_graph.nodes[0])
        elif selection == 'SELECTED_OBJECTS':
            # Generate active object list and loop over that somehow
            pass

        # for obj in bpy.context.selected_objects:
        #    # Objects directly in the scene only has the 'Master Collection' in the list,
        #    # which disappears once the object is added to any other collection
        #    if bpy.context.scene.collection in obj.users_collection and obj.parent is None:
        #       print(f"{obj.name!r} is at scene root")
        #       self.new_graph_node(obj, self._scene_graph.nodes[0])
        print(self._scene_graph)

    def _xml_build_skeleton_structure(self) -> None:
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

    def _xml_parse_scene_graph(self):

        def parse_node(node: SceneGraph.Node, node_element: ET.Element):

            self._xml_scene_object_general_data(node, node_element)

            # TODO: Categorize node and write other stuff like materials and shapes

            if isinstance(node.blender_object, bpy.types.Collection):
                self._xml_scene_object_transform_group(node, node_element)
            else:
                node_type = node.blender_object.type
                if node_type == 'MESH':
                    self._xml_scene_object_shape(node, node_element)
                elif node_type == 'EMPTY':
                    self._xml_scene_object_transform_group(node, node_element)

            for child in node.children.values():
                # print(f"{child.blender_object.name} : {Exporter.blender_to_i3d(child.blender_object)}")
                child_element = ET.SubElement(node_element,
                                              Exporter.blender_to_i3d(child.blender_object))
                parse_node(child, child_element)

        for root_child in self._scene_graph.nodes[0].children.values():
            # print(f"{root_child.blender_object.name} : {Exporter.blender_to_i3d(root_child.blender_object)}")
            root_child_element = ET.SubElement(self._tree.find('Scene'),
                                               Exporter.blender_to_i3d(root_child.blender_object))
            parse_node(root_child, root_child_element)

    def _xml_scene_object_general_data(self, node: SceneGraph.Node, node_element: ET.Element):
        # print("Writing general data")
        self._xml_write_string(node_element, 'name', node.blender_object.name)
        self._xml_write_int(node_element, 'nodeId', node.id)
        if isinstance(node.blender_object, bpy.types.Collection):
            # Collections dont have any physical properties, but the transformgroups in i3d has so it is set to 0
            # in relation to it's parent so it stays purely organisational
            self._xml_write_string(node_element, 'translation', "0 0 0")
            self._xml_write_string(node_element, 'rotation', "0 0 0")
            self._xml_write_string(node_element, 'scale', "1 1 1")
            # TODO: Make visibility check more elaborate since visibility can be many things. Right now it is only
            #  viewport visibility that is taken into account. Issue #1
            self._xml_write_bool(node_element, 'visibility', not node.blender_object.hide_viewport)
        else:

            # TODO: Investigate how to use the export helper functions to convert instead of hardcoding the rotations

            # Perform rotation of object so it fits GE
            matrix = mathutils.Matrix.Rotation(math.radians(-90), 4, "X")
            matrix @= node.blender_object.matrix_local
            matrix @= mathutils.Matrix.Rotation(math.radians(90), 4, "X")

            self._xml_write_string(node_element,
                                   'translation',
                                   "{0:.6f} {1:.6f} {2:.6f}".format(*matrix.to_translation()))

            self._xml_write_string(node_element,
                                   'rotation',
                                   "{0:.3f} {1:.3f} {2:.3f}".format(*[math.degrees(axis)
                                                                      for axis in matrix.to_euler('XYZ')]))

            self._xml_write_string(node_element,
                                   'scale',
                                   "{0:.6f} {1:.6f} {2:.6f}".format(*matrix.to_scale()))

            # visible_get() should determine visibility based on all visibility flags
            self._xml_write_bool(node_element, 'visibility', node.blender_object.visible_get())

        # TODO: Check for clip distance
        # self._xml_write_string(node_element, 'clipDistance', '300')

    def _xml_add_material(self, material):
        materials_root = self._tree.find('Materials')
        material_element = materials_root.find(f".Material[@name={material.name!r}]")
        if material_element is None:
            # print(f"New material")
            material_element = ET.SubElement(materials_root, 'Material')
            self._xml_write_string(material_element, 'name', material.name)
            self._xml_write_int(material_element, 'materialId', self.ids['material'])

            if material.use_nodes:
                # print(f"{material.name!r} uses nodes, not supported for now so using defaults")
                self._xml_write_string(material_element,
                                       'diffuseColor',
                                       f"{0.5:f} {0.5:f} {0.5:f} {1.0:f}")
            else:
                # print(f"{material.name!r} does not use nodes")
                self._xml_write_string(material_element,
                                       'diffuseColor',
                                       "{0:.6f} {1:.6f} {2:.6f} {3:.6f}".format(*material.diffuse_color))

            self._xml_write_string(material_element,
                                   'specularColor',
                                   f"{material.roughness:f} {1:.6f} {material.metallic:f}")

            self.ids['material'] += 1

        return int(material_element.get('materialId'))

    def _xml_add_file(self, filename):
        print("Adding file")

    def _xml_scene_object_shape(self, node: SceneGraph.Node, node_element: ET.Element):

        ###############################################
        # Mesh export section
        ###############################################

        shape_root = self._tree.find('Shapes')
        obj = node.blender_object

        # Check if the mesh has already been defined in the i3d file
        indexed_triangle_element = shape_root.find(f".IndexedTriangleSet[@name={obj.data.name!r}]")
        if indexed_triangle_element is None:
            shape_id = self.ids['shape']
            self.ids['shape'] += 1

            indexed_triangle_element = ET.SubElement(shape_root, 'IndexedTriangleSet')

            self._xml_write_string(indexed_triangle_element, 'name', obj.data.name)
            self._xml_write_int(indexed_triangle_element, 'shapeId', shape_id)

            # TODO: All shape related parsing code

            # Evaluate the dependency graph to make sure that all data is evaluated. As long as nothing changes, this
            # should only be 'heavy' to call the first time a mesh is exported.
            # https://docs.blender.org/api/current/bpy.types.Depsgraph.html
            depsgraph = bpy.context.evaluated_depsgraph_get()

            # Generate an object evaluated from the dependency graph
            object_evaluated = obj.evaluated_get(depsgraph)

            # Generates a mesh with all modifiers applied and access to all data layers
            mesh = object_evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)

            # TODO: Look into if there is a smarter way to triangulate mesh data rather than using a bmesh operator
            #  since this supposedly wrecks custom normals

            # Triangulate mesh data
            bm = bmesh.new()
            bm.from_mesh(mesh)
            bmesh.ops.triangulate(bm, faces=bm.faces, quad_method='BEAUTY', ngon_method='BEAUTY')
            bm.to_mesh(mesh)
            bm.free()

            vertices_element = ET.SubElement(indexed_triangle_element, 'Vertices')
            triangles_element = ET.SubElement(indexed_triangle_element, 'Triangles')
            subsets_element = ET.SubElement(indexed_triangle_element, 'Subsets')

            self._xml_write_int(triangles_element, 'count', len(mesh.polygons))

            polygon_subsets = {}

            # Create and assign default material if it does not exist already. This material will persist in the blender
            # file so you can change the default look if you want to through the blender interface
            if len(mesh.materials) == 0:
                if bpy.data.materials.get('i3d_default_material') is None:
                    bpy.data.materials.new('i3d_default_material')

                mesh.materials.append(bpy.data.materials.get('i3d_default_material'))

            for polygon in mesh.polygons:

                polygon_material = mesh.materials[polygon.material_index]
                # Loops are divided into subsets based on materials
                if polygon_material.name not in polygon_subsets:
                    # print(f'{polygon_material.name!r} is a new material')
                    polygon_subsets[polygon_material.name] = []
                    # Add material to material section in i3d file and append to the materialIds that the shape
                    # object should have
                    material_id = self._xml_add_material(polygon_material)
                    # print(f"Mat id: {material_id:d}")

                    if shape_id in self.shape_material_indexes.keys():
                        # print(f"mat index: {self.shape_material_indexes[shape_id]}")
                        self.shape_material_indexes[shape_id] += f",{material_id:d}"
                    else:
                        self.shape_material_indexes[shape_id] = f"{material_id:d}"
                        # print(f"new mat index: {self.shape_material_indexes[shape_id]}")

                polygon_subsets[polygon_material.name].append(polygon)

            self._xml_write_int(subsets_element, 'count', len(polygon_subsets))

            added_vertices = {}  # Key is a unique vertex identifier and the value is a vertex index
            vertex_counter = 0
            indices_total = 0

            # Vertices are written to the i3d vertex list in an order based on the subsets and the triangles then index
            # into this list to define themselves

            for mat, subset in polygon_subsets.items():
                number_of_indices = 0
                number_of_vertices = 0
                subset_element = ET.SubElement(subsets_element, 'Subset')
                self._xml_write_int(subset_element, 'firstIndex', indices_total)
                self._xml_write_int(subset_element, 'firstVertex', vertex_counter)

                # print(f"Subset {mat}:")
                # Go through every polygon on the subset and extract triangle information
                for polygon in subset:
                    triangle_element = ET.SubElement(triangles_element, 't')
                    # print(f'\tPolygon Index: {polygon.index}, length: {polygon.loop_total}')
                    # Go through every loop in the polygon and extract vertex information
                    polygon_vertex_index = ""  # The vertices from the vertex list that specify this triangle
                    for loop_index in polygon.loop_indices:
                        vertex = mesh.vertices[mesh.loops[loop_index].vertex_index]
                        vertex_data = {'p': f"{vertex.co.xyz[0]:.6f} "
                                            f"{vertex.co.xyz[2]:.6f} "
                                            f"{-vertex.co.xyz[1]:.6f}",

                                       'n': f"{vertex.normal.xyz[0]:.6f} "
                                            f"{vertex.normal.xyz[2]:.6f} "
                                            f"{-vertex.normal.xyz[1]:.6f}",

                                       't0': f"{mesh.uv_layers[0].data[loop_index].uv[0]:.6f} "
                                             f"{mesh.uv_layers[0].data[loop_index].uv[1]:.6f}"
                                       }

                        vertex_item = VertexItem(vertex_data, mat)

                        if vertex_item not in added_vertices:
                            added_vertices[vertex_item] = vertex_counter

                            vertex_element = ET.SubElement(vertices_element, 'v')
                            self._xml_write_string(vertex_element, 'n', vertex_data['n'])
                            self._xml_write_string(vertex_element, 'p', vertex_data['p'])
                            self._xml_write_string(vertex_element, 't0', vertex_data['t0'])

                            vertex_counter += 1
                            number_of_vertices += 1

                        polygon_vertex_index += f"{added_vertices[vertex_item]} "
                        number_of_indices += 1

                    self._xml_write_string(triangle_element, 'vi', polygon_vertex_index.strip(' '))

                self._xml_write_int(subset_element, 'numIndices', number_of_indices)
                self._xml_write_int(subset_element, 'numVertices', number_of_vertices)
                indices_total += number_of_indices

            self._xml_write_int(vertices_element, 'count', vertex_counter)
            self._xml_write_bool(vertices_element, 'normal', True)
            self._xml_write_bool(vertices_element, 'tangent', True)
            self._xml_write_bool(vertices_element, 'uv0', True)

            # Clean out the generated mesh so it does not stay in blender memory
            object_evaluated.to_mesh_clear()

            # TODO: Write mesh related attributes

        else:
            shape_id = int(indexed_triangle_element.get('shapeId'))

        self._xml_write_int(node_element, 'shapeId', shape_id)
        self._xml_write_string(node_element, 'materialIds', self.shape_material_indexes[shape_id])
        # print(self.shape_material_indexes[shape_id])

    def _xml_scene_object_transform_group(self, node: SceneGraph.Node, node_element: ET.Element):
        # TODO: Add parameters to UI and extract here
        pass
        # print(f"This is a transformgroup: {node.blender_object.name!r}")

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

    @staticmethod
    def blender_to_i3d(blender_object: Union[bpy.types.Object, bpy.types.Collection]):
        # Collections don't have an object type since they aren't objects. If they are used for organisational purposes
        # they are converted into transformgroups in the scenegraph
        if isinstance(blender_object, bpy.types.Collection):
            return 'TransformGroup'

        switcher = {
            'MESH': 'Shape',
            'CURVE': 'Shape',
            'EMPTY': 'TransformGroup',
            'CAMERA': 'Camera',
            'LIGHT': 'Light',
            'COLLECTION': 'TransformGroup'
        }
        return switcher[blender_object.type]


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


class VertexItem:
    """Used for defining unique vertex items (Could be the same vertex but with a different color or material uv"""
    def __init__(self, vertex_item, material_name):
        self._str = f"{material_name}"
        for key, item in vertex_item.items():
            self._str += f" {item}"

    def __str__(self):
        return self._str

    def __hash__(self):
        return hash(self._str)

    def __eq__(self, other):
        return self._str == f'{other!s}'
