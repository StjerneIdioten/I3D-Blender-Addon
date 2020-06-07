"""This module contains shared functionality between the different modules of the i3dio addon"""
from __future__ import annotations  # Enables python 4.0 annotation typehints fx. class self-referencing
from typing import (Union, Dict, List, Type, OrderedDict, Optional)
import xml.etree.ElementTree as ET
import logging
import mathutils

import bpy

from . import debugging
from . import xml_i3d

logger = logging.getLogger(__name__)


class I3D:
    """A special node which is the root node for the entire I3D file. It essentially represents the i3d file"""
    def __init__(self, name: str, i3d_file_path: str, conversion_matrix: mathutils.Matrix):
        self.logger = debugging.ObjectNameAdapter(logging.getLogger(f"{__name__}.{type(self).__name__}"),
                                                  {'object_name': name})
        self._ids = {
            'node': 1,
            'shape': 1,
            'material': 1,
            'file': 1,
        }
        self.paths = {
            'i3d_file_path': i3d_file_path,
            'i3d_folder': i3d_file_path[0:i3d_file_path.rfind('\\')],
        }

        # Initialize top-level categories
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

        self.shapes: Dict[Union[str, int], IndexedTriangleSet] = {}
        self.materials: Dict[Union[str, int], Material] = {}
        self.files: Dict[Union[str, int], File] = {}
        self.merge_groups: Dict[str, MergeGroup] = {}

        # Save all settings for the current run unto the I3D to abstract it from the nodes themselves
        self.settings = {}
        for setting in bpy.context.scene.i3dio.__annotations__.keys():
            self.settings[setting] = getattr(bpy.context.scene.i3dio, setting)

    # Private Methods ##################################################################################################
    def _next_available_id(self, id_type: str) -> int:
        next_id = self._ids[id_type]
        self._ids[id_type] += 1
        return next_id

    def _add_node(self, node_type: Type[SceneGraphNode], object_: bpy.types.Object, parent: SceneGraphNode = None) \
            -> SceneGraphNode:
        node = node_type(self._next_available_id('node'), object_, self, parent)
        if parent is None:
            self.scene_root_nodes.append(node)
            self.xml_elements['Scene'].append(node.element)
        return node

    # Public Methods ###################################################################################################
    def add_shape_node(self, mesh_object: bpy.types.Object, parent: SceneGraphNode = None) -> SceneGraphNode:
        """Add a blender object with a data type of MESH to the scenegraph as a Shape node"""
        return self._add_node(ShapeNode, mesh_object, parent)

    def add_merge_group_node(self, merge_group_object: bpy.types.Object, parent: SceneGraphNode = None) \
            -> [SceneGraphNode, None]:
        self.logger.debug("Adding merge group node")
        merge_group_id = merge_group_object.i3d_merge_group.group_id
        merge_group_name = xml_i3d.merge_group_prefix + merge_group_id
        node_to_return: [MergeGroupRoot or MergeGroupRoot] = None
        if merge_group_name not in self.merge_groups:
            self.logger.debug("New merge group")
            merge_group = self.merge_groups[merge_group_name] = MergeGroup(merge_group_name)
            if merge_group_object.i3d_merge_group.is_root:
                node_to_return = self._add_node(MergeGroupRoot, merge_group_object, parent)
                merge_group.set_root(node_to_return)
            else:
                node_to_return = self._add_node(MergeGroupChild, merge_group_object, parent)
                merge_group.add_child(node_to_return)
        else:
            self.logger.debug("Merge group already exists")
            merge_group = self.merge_groups[merge_group_name]
            if merge_group_object.i3d_merge_group.is_root:
                if merge_group.root_node is not None:
                    self.logger.warning(f"Merge group '{merge_group_id}' already has a root node! "
                                        f"The object '{merge_group_object.name}' will be ignored for export")
                else:
                    node_to_return = self._add_node(MergeGroupRoot, merge_group_object, parent)
                    merge_group.set_root(node_to_return)
            else:
                node_to_return = self._add_node(MergeGroupChild, merge_group_object, parent)
                merge_group.add_child(node_to_return)
        return node_to_return

    def add_transformgroup_node(self, empty_object: [bpy.types.Object, bpy.types.Collection],
                                parent: SceneGraphNode = None) -> SceneGraphNode:
        return self._add_node(TransformGroupNode, empty_object, parent)

    def add_light_node(self, light_object: bpy.types.Object, parent: SceneGraphNode = None) -> SceneGraphNode:
        """Add a blender object with a data type of MESH to the scenegraph as a Shape node"""
        return self._add_node(LightNode, light_object, parent)

    def add_camera_node(self, camera_object: bpy.types.Object, parent: SceneGraphNode = None) -> SceneGraphNode:
        """Add a blender object with a data type of MESH to the scenegraph as a Shape node"""
        return self._add_node(CameraNode, camera_object, parent)

    def add_shape(self, evaluated_mesh: EvaluatedMesh, shape_name: Optional[str] = None, is_merge_group=None) -> int:
        if shape_name is None:
            name = evaluated_mesh.name
        else:
            name = shape_name

        if name not in self.shapes:
            shape_id = self._next_available_id('shape')
            indexed_triangle_set = IndexedTriangleSet(shape_id, self, evaluated_mesh, shape_name, is_merge_group)
            # Store a reference to the shape from both it's name and its shape id
            self.shapes.update(dict.fromkeys([shape_id, name], indexed_triangle_set))
            self.xml_elements['Shapes'].append(indexed_triangle_set.element)
            return shape_id
        return self.shapes[name].id

    def get_shape_by_id(self, shape_id: int):
        return self.shapes[shape_id]

    def add_material(self, blender_material: bpy.types.Material) -> int:
        name = blender_material.name
        if name not in self.materials:
            self.logger.debug(f"New Material")
            material_id = self._next_available_id('material')
            material = Material(material_id, self, blender_material)
            self.materials.update(dict.fromkeys([material_id, name], material))
            self.xml_elements['Materials'].append(material.element)
            return material_id
        return self.materials[name].id

    def get_default_material(self) -> Material:
        default_material_name = 'i3d_default_material'
        blender_material = bpy.data.materials.get(default_material_name)
        # If the material doesn't pre-exist in the blend file, then add it.
        if blender_material is None:
            material = bpy.data.materials.new(default_material_name)
            self.logger.info(f"Default material does not exist. Creating 'i3d_default_material'")
            self.add_material(material)
        # If it already exists in the blend file (Due to a previous export) add it to the i3d material list
        elif default_material_name not in self.materials:
            self.add_material(blender_material)
        # Return the default material
        return self.materials[default_material_name]

    def add_file(self, file_type: Type[File], path_to_file: str) -> int:
        if path_to_file not in self.files:
            self.logger.debug(f"New File")
            file_id = self._next_available_id('file')
            file = file_type(file_id, self, path_to_file)
            # Store with reference to blender path instead of potential relative path, to avoid unnecessary creation of
            # a file before looking it up in the files dictionary.
            self.files.update(dict.fromkeys([file_id, file.blender_path], file))
            self.xml_elements['Files'].append(file.element)
            return file_id
        return self.files[path_to_file].id

    def add_file_image(self, path_to_file: str) -> int:
        return self.add_file(Image, path_to_file)

    def get_setting(self, setting: str):
        return self.settings[setting]

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


# To avoid a circular import, since all nodes rely on the I3D class, but i3d itself contains all the different nodes.
from i3dio.node_classes.node import *
from i3dio.node_classes.shape import *
from i3dio.node_classes.merge_group import *
from i3dio.node_classes.material import *
from i3dio.node_classes.file import *
