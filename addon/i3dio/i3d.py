"""This module contains shared functionality between the different modules of the i3dio addon"""
from __future__ import annotations  # Enables python 4.0 annotation typehints fx. class self-referencing
from typing import (Union, Dict, List, Type, OrderedDict, Optional)
import logging
from . import xml_i3d

logger = logging.getLogger(__name__)


class I3D:
    """A special node which is the root node for the entire I3D file. It essentially represents the i3d file"""
    def __init__(self, name: str, i3d_file_path: str, conversion_matrix: mathutils.Matrix,
                 depsgraph: bpy.types.Depsgraph):
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
        self.xml_elements = {'Root': xml_i3d.i3d_root_element(name)}
        self.xml_elements['Asset'] = xml_i3d.SubElement(self.xml_elements['Root'], 'Asset')
        self.xml_elements['Files'] = xml_i3d.SubElement(self.xml_elements['Root'], 'Files')
        self.xml_elements['Materials'] = xml_i3d.SubElement(self.xml_elements['Root'], 'Materials')
        self.xml_elements['Shapes'] = xml_i3d.SubElement(self.xml_elements['Root'], 'Shapes')
        self.xml_elements['Dynamics'] = xml_i3d.SubElement(self.xml_elements['Root'], 'Dynamics')
        self.xml_elements['Scene'] = xml_i3d.SubElement(self.xml_elements['Root'], 'Scene')
        self.xml_elements['Animation'] = xml_i3d.SubElement(self.xml_elements['Root'], 'Animation')
        self.xml_elements['UserAttributes'] = xml_i3d.SubElement(self.xml_elements['Root'], 'UserAttributes')

        self.scene_root_nodes = []
        self.conversion_matrix = conversion_matrix

        self.shapes: Dict[Union[str, int], IndexedTriangleSet] = {}
        self.materials: Dict[Union[str, int], Material] = {}
        self.files: Dict[Union[str, int], File] = {}
        self.merge_groups: Dict[str, MergeGroup] = {}
        self.skinned_meshes: Dict[str, SkinnedMeshRootNode] = {}

        self.i3d_mapping: List[SceneGraphNode] = []

        # Save all settings for the current run unto the I3D to abstract it from the nodes themselves
        self.settings = {}
        for setting in bpy.context.scene.i3dio.__annotations__.keys():
            self.settings[setting] = getattr(bpy.context.scene.i3dio, setting)

        self.depsgraph = depsgraph

    # Private Methods ##################################################################################################
    def _next_available_id(self, id_type: str) -> int:
        next_id = self._ids[id_type]
        self._ids[id_type] += 1
        return next_id

    def _add_node(self, node_type: Type[SceneGraphNode], object_: Type[bpy.types.bpy_struct],
                  parent: Type[SceneGraphNode] = None) -> SceneGraphNode:
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

    def add_bone(self, bone_object: bpy.types.Bone, parent: Union[SkinnedMeshBoneNode, SkinnedMeshRootNode]) \
            -> SceneGraphNode:
        return self._add_node(SkinnedMeshBoneNode, bone_object, parent)

    # TODO: Rethink this to not include an extra argument for when the node is actually discovered.
    #  Maybe two separate functions instead? This is just hack'n'slash code at this point!
    def add_armature(self, armature_object: bpy.types.Armature, parent: SceneGraphNode = None,
                     is_located: bool = False) -> SceneGraphNode:
        if armature_object.name not in self.skinned_meshes:
            if is_located and not self.settings['collapse_armatures']:
                skinned_mesh_root_node = self._add_node(SkinnedMeshRootNode, armature_object, parent)
            elif is_located and self.settings['collapse_armatures']:
                skinned_mesh_root_node = SkinnedMeshRootNode(self._next_available_id('node'), armature_object, self,
                                                             None)
                skinned_mesh_root_node.update_bone_parent(parent)

            else:
                skinned_mesh_root_node = SkinnedMeshRootNode(self._next_available_id('node'), armature_object, self,
                                                             None)

            skinned_mesh_root_node.is_located = is_located
            self.skinned_meshes[armature_object.name] = skinned_mesh_root_node
        elif is_located:
            if not self.settings['collapse_armatures']:
                if parent is not None:
                    parent.add_child(self.skinned_meshes[armature_object.name])
                    parent.element.append(self.skinned_meshes[armature_object.name].element)
                else:
                    self.scene_root_nodes.append(self.skinned_meshes[armature_object.name])
                    self.xml_elements['Scene'].append(self.skinned_meshes[armature_object.name].element)
            else:
                self.skinned_meshes[armature_object.name].update_bone_parent(parent)

            self.skinned_meshes[armature_object.name].is_located = is_located

        return self.skinned_meshes[armature_object.name]

    def add_skinned_mesh_node(self, mesh_object: bpy.types.Object, parent: SceneGraphNode = None) -> SceneGraphNode:
        return self._add_node(SkinnedMeshShapeNode, mesh_object, parent)

    def add_transformgroup_node(self, empty_object: [bpy.types.Object, bpy.types.Collection],
                                parent: SceneGraphNode = None) -> SceneGraphNode:
        return self._add_node(TransformGroupNode, empty_object, parent)

    def add_light_node(self, light_object: bpy.types.Object, parent: SceneGraphNode = None) -> SceneGraphNode:
        """Add a blender object with a data type of MESH to the scenegraph as a Shape node"""
        return self._add_node(LightNode, light_object, parent)

    def add_camera_node(self, camera_object: bpy.types.Object, parent: SceneGraphNode = None) -> SceneGraphNode:
        """Add a blender object with a data type of MESH to the scenegraph as a Shape node"""
        return self._add_node(CameraNode, camera_object, parent)

    def add_shape(self, evaluated_mesh: EvaluatedMesh, shape_name: Optional[str] = None, is_merge_group=None,
                  bone_mapping: ChainMap = None) -> int:
        if shape_name is None:
            name = evaluated_mesh.name
        else:
            name = shape_name

        if name not in self.shapes:
            shape_id = self._next_available_id('shape')
            indexed_triangle_set = IndexedTriangleSet(shape_id, self, evaluated_mesh, shape_name, is_merge_group,
                                                      bone_mapping)
            # Store a reference to the shape from both it's name and its shape id
            self.shapes.update(dict.fromkeys([shape_id, name], indexed_triangle_set))
            self.xml_elements['Shapes'].append(indexed_triangle_set.element)
            return shape_id
        return self.shapes[name].id

    def get_shape_by_id(self, shape_id: int):
        return self.shapes[shape_id]

    def add_user_attributes(self, user_attributes, node_id):
        node_attribute_element = self.xml_elements['UserAttributes'].find(f"UserAttribute[@nodeId='{node_id:d}']")
        if node_attribute_element is None:
            node_attribute_element = xml_i3d.SubElement(self.xml_elements['UserAttributes'], 'UserAttribute',
                                                   attrib={'nodeId': str(node_id)})

        for attribute in user_attributes:
            attrib = {'name': attribute.name, 'type': attribute.type.replace('data_', '')}
            attribute_element = xml_i3d.SubElement(node_attribute_element, 'Attribute', attrib=attrib)
            xml_i3d.write_attribute(attribute_element, 'value', getattr(attribute, attribute.type))

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

    def add_file_shader(self, path_to_file: str) -> int:
        return self.add_file(Shader, path_to_file)

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
            for child in node.children:
                traverse(child, indents + 1)

        for root_node in self.scene_root_nodes:
            traverse(root_node)

        tree_string += f"{longest_string * '-'}\n"

        return f"{longest_string * '-'}\n" + tree_string

    def export_to_i3d_file(self) -> None:
        xml_i3d.export_to_i3d_file(self.xml_elements['Root'], self.paths['i3d_file_path'])

        if self.settings['i3d_mapping_file_path'] != '':
            self.export_i3d_mapping()

    def export_i3d_mapping(self) -> None:
        tree = xml_i3d.parse(bpy.path.abspath(self.settings['i3d_mapping_file_path']))
        if tree is None:
            self.logger.warning(f"Supplied mapping file is not correct xml, failed with error")
        else:
            root = tree.getroot()
            i3d_mappings_element = root.find('i3dMappings')
            if i3d_mappings_element is not None:
                if self.settings['i3d_mapping_overwrite_mode'] == 'CLEAN':
                    i3d_mappings_element.clear()
                elif self.settings['i3d_mapping_overwrite_mode'] == 'OVERWRITE':
                    pass

                def build_index_string(node_to_index):
                    if node_to_index.parent is None:
                        index = f"{self.scene_root_nodes.index(node_to_index):d}>"
                    else:
                        index = build_index_string(node_to_index.parent)
                        if index[-1] != '>':
                            index += '|'
                        index += str(node_to_index.parent.children.index(node_to_index))
                    return index

                for mapping_node in self.i3d_mapping:
                    if getattr(mapping_node.blender_object.i3d_mapping, 'mapping_name') != '':
                        name = getattr(mapping_node.blender_object.i3d_mapping, 'mapping_name')
                    else:
                        name = mapping_node.name

                    attributes = {'id': name, 'node': build_index_string(mapping_node)}
                    xml_i3d.SubElement(i3d_mappings_element, 'i3dMapping', attributes)

                xml_i3d.write_tree_to_file(tree, bpy.path.abspath(self.settings['i3d_mapping_file_path']),
                                           xml_declaration=True,
                                           encoding='utf-8')
            else:
                self.logger.warning(f"Supplied mapping file does not contain an <i3dMappings> tag anywhere! Cannot"
                                    f"export mappings.")


# To avoid a circular import, since all nodes rely on the I3D class, but i3d itself contains all the different nodes.
from i3dio.node_classes.node import *
from i3dio.node_classes.shape import *
from i3dio.node_classes.merge_group import *
from i3dio.node_classes.skinned_mesh import *
from i3dio.node_classes.material import *
from i3dio.node_classes.file import *
