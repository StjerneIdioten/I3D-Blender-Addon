"""This module contains shared functionality between the different modules of the i3dio addon"""
from __future__ import annotations  # Enables python 4.0 annotation typehints fx. class self-referencing
from typing import (Union, Type)
import logging
from . import xml_i3d

logger = logging.getLogger(__name__)


class I3D:
    """A special node which is the root node for the entire I3D file. It essentially represents the i3d file"""
    def __init__(self, name: str, i3d_file_path: str, conversion_matrix: mathutils.Matrix,
                 depsgraph: bpy.types.Depsgraph, settings: dict):
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
        self.processed_objects: dict[bpy.types.Object, SceneGraphNode] = {}
        self.deferred_constraints: list[tuple[SkinnedMeshBoneNode, bpy.types.Object]] = []
        self.conversion_matrix = conversion_matrix

        self.shapes: dict[Union[str, int], Union[IndexedTriangleSet, NurbsCurve]] = {}
        self.materials: dict[Union[str, int], Material] = {}
        self.files: dict[Union[str, int], File] = {}
        self.merge_groups: dict[int, MergeGroup] = {}
        self.deferred_shapes_to_populate: list[IndexedTriangleSet] = []
        self.skinned_meshes: dict[str, SkinnedMeshRootNode] = {}

        self.i3d_mapping: list[SceneGraphNode] = []

        self.settings = settings

        self.depsgraph = depsgraph

        self.all_objects_to_export: list[bpy.types.Object] = []

    # Private Methods ##################################################################################################
    def _next_available_id(self, id_type: str) -> int:
        next_id = self._ids[id_type]
        self._ids[id_type] += 1
        return next_id

    def _add_node(self, node_type: Type[SceneGraphNode], object_: Type[bpy.types.bpy_struct],
                  parent: Type[SceneGraphNode] = None, **kwargs) -> SceneGraphNode:
        node = node_type(self._next_available_id('node'), object_, self, parent, **kwargs)
        # Populate xml element after node is fully constructed
        node.populate_xml_element()
        self.processed_objects[object_] = node
        if parent is None:
            self.logger.debug(f"Node {node.name!r} has no parent, adding to scene root.")
            self.scene_root_nodes.append(node)
            self.xml_elements['Scene'].append(node.element)
        return node

    def _get_or_create_armature_node(self, armature_object: bpy.types.Object,
                                     parent: SceneGraphNode | None) -> SkinnedMeshRootNode:
        """Retrieves an existing SkinnedMeshRootNode for the armature or creates a new one if needed."""
        node = self.skinned_meshes.get(armature_object.name)
        if node is None:
            self.logger.debug(f"Creating new SkinnedMeshRootNode for armature {armature_object.name!r}.")
            node = SkinnedMeshRootNode(self._next_available_id('node'), armature_object, self, parent=parent)
            node.populate_xml_element()
            self.skinned_meshes[armature_object.name] = node
        elif parent is not None and node.parent is None and not node.is_collapsed:
            self.logger.debug(
                f"Armature {armature_object.name!r} was pre-created by a modifier. "
                f"Now assigning its correct parent: {parent.name!r}."
            )
            node.parent = parent
            parent.add_child(node)
            parent.element.append(node.element)
        return node

    # Public Methods ###################################################################################################
    def add_shape_node(self, mesh_object: bpy.types.Object, parent: SceneGraphNode = None) -> SceneGraphNode:
        """Add a blender object with a data type of MESH to the scenegraph as a Shape node"""
        return self._add_node(ShapeNode, mesh_object, parent)

    def add_merge_group_node(self, merge_group_object: bpy.types.Object,
                             parent: SceneGraphNode | None = None) -> SceneGraphNode:
        self.logger.debug("Adding merge group node")

        # Blender-side and export-side merge group data
        blender_merge_group = bpy.context.scene.i3dio_merge_groups[merge_group_object.i3d_merge_group_index]
        exporter_merge_group = self.merge_groups[merge_group_object.i3d_merge_group_index]

        # Check if a root is assigned in Blender and if that root is part of this export
        root_obj = blender_merge_group.root
        has_valid_root = (root_obj and root_obj in self.all_objects_to_export)

        # Determine if the current object should be the root of the merge group
        # 1. If it is marked as root in Blender and the root object matches the merge group object
        # 2. There is no valid root assigned, and the exporter haven't assigned a root yet
        should_be_root = (
            (has_valid_root and root_obj == merge_group_object)
            or (not has_valid_root and exporter_merge_group.root_node is None)
        )

        if should_be_root:
            if not has_valid_root:
                self.logger.warning(
                    f"No valid root was found for merge group '{blender_merge_group.name}'. "
                    f"Automatically assigning '{merge_group_object.name}' as the root."
                )
            root_node = self._add_node(MergeGroupRoot, merge_group_object, parent)
            exporter_merge_group.set_root(root_node)
            return root_node
        # Child node
        child_node = self._add_node(MergeGroupChild, merge_group_object, parent)
        exporter_merge_group.add_child(child_node)
        return child_node

    def add_merge_children_node(self, merge_children_object: bpy.types.Object,
                                parent: SceneGraphNode | None = None) -> SceneGraphNode:
        return self._add_node(MergeChildrenRoot, merge_children_object, parent)

    def add_bone(self, bone_object: bpy.types.Bone, parent: SceneGraphNode | None,
                 root_node: SkinnedMeshRootNode) -> SceneGraphNode:
        # Prevent the bone from getting added to the scene root node if added through a armature modifier.
        # If it actually should be added to scene root we will handle it when we get to the armature object
        node = SkinnedMeshBoneNode(self._next_available_id('node'), bone_object, self, parent, root_node)
        node.populate_xml_element()
        self.processed_objects[bone_object] = node

        if parent is not None:
            parent.add_child(node)
            parent.element.append(node.element)

        return node

    def add_armature_from_modifier(self, armature_object: bpy.types.Object) -> SkinnedMeshRootNode:
        """
        Gets or creates an armature node when discovered via a Skinned Mesh (armature modifier).
        The parent is unknown at this time, so it's passed as None.
        """
        self.logger.debug(f"Adding armature from modifier: {armature_object.name!r}")
        return self._get_or_create_armature_node(armature_object, parent=None)

    def add_armature_from_scene(self, armature_object: bpy.types.Object, parent: SceneGraphNode) -> SkinnedMeshRootNode:
        """Processes an armature found during the main scene traversal. The parent is known at this time."""
        self.logger.debug(f"Adding armature from scene: {armature_object.name!r} with parent {parent}")
        armature_node = self._get_or_create_armature_node(armature_object, parent)
        armature_node.organize_armature_hierarchy(parent)
        return armature_node

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

    def add_shape(self, evaluated_mesh: EvaluatedMesh, shape_name: str | None = None, is_merge_group: bool = False,
                  is_generic: bool = False, bone_mapping: ChainMap | None = None) -> int:
        name = shape_name or evaluated_mesh.name
        if name not in self.shapes:
            shape_id = self._next_available_id('shape')
            indexed_triangle_set = IndexedTriangleSet(shape_id, self, evaluated_mesh, shape_name=shape_name,
                                                      is_merge_group=is_merge_group, is_generic=is_generic,
                                                      bone_mapping=bone_mapping)
            indexed_triangle_set.populate_xml_element()
            # Store a reference to the shape from both it's name and its shape id
            self.shapes.update(dict.fromkeys([shape_id, name], indexed_triangle_set))
            self.xml_elements['Shapes'].append(indexed_triangle_set.element)
            return shape_id
        return self.shapes[name].id

    def add_curve(self, evaluated_curve: EvaluatedNurbsCurve, curve_name: str | None = None) -> int:
        name = curve_name or evaluated_curve.name
        if name not in self.shapes:
            curve_id = self._next_available_id('shape')
            nurbs_curve = NurbsCurve(curve_id, self, evaluated_curve, curve_name)
            nurbs_curve.populate_xml_element()
            # Store a reference to the curve from both its name and its curve id
            self.shapes.update(dict.fromkeys([curve_id, name], nurbs_curve))
            self.xml_elements['Shapes'].append(nurbs_curve.element)
            return curve_id
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
            material.populate_xml_element()
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
            file.populate_xml_element()
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

    def add_file_reference(self, path_to_file: str) -> int:
        return self.add_file(Reference, path_to_file)

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
        file_path = bpy.path.abspath(self.settings['i3d_mapping_file_path'])
        self.logger.info(f"Exporting i3d mappings to {file_path}")

        # Only use ElementTree for parsing the file, writing is done manually to avoid formatting the entire file
        tree = xml_i3d.parse(file_path)
        if tree is None:
            self.logger.error(f"Failed to parse the XML file: {file_path}")
            return
        root = tree.getroot()
        i3d_mappings_element = root.find('i3dMappings')

        with open(file_path, 'r', encoding='utf-8') as xml_file:
            lines = xml_file.readlines()

        i3d_mapping_idx = None
        closing_root_idx = None
        xml_indentation = ' ' * 4
        for idx, line in enumerate(lines):
            stripped_line = line.strip()  # Remove leading and trailing whitespace
            if '<i3dMappings>' in stripped_line:
                i3d_mapping_idx = idx
                xml_indentation = line[:line.find('<')]  # Preserve indentation
                break
            if stripped_line == f"</{root.tag}>":
                closing_root_idx = idx  # Preserve the index of the closing root tag

        if i3d_mapping_idx is None and closing_root_idx is not None:
            i3d_mapping_idx = closing_root_idx
            lines.insert(i3d_mapping_idx, f"\n{xml_indentation}<i3dMappings>\n")
            self.logger.info(f"Inserted missing <i3dMappings> before </{root.tag}>.")

        if i3d_mapping_idx is None:
            self.logger.warning("Cannot export i3d mapping. No valid root element found!")
            return

        def _build_index_string(node_to_index) -> str:
            if node_to_index.parent is None:  # Root node should end with '>'
                return f"{self.scene_root_nodes.index(node_to_index)}>"
            index = _build_index_string(node_to_index.parent)
            if index[-1] != '>':  # If it's not a root use '|'
                index += '|'
            # Add the child index
            index += str(node_to_index.parent.children.index(node_to_index))
            return index

        new_mappings = []
        for mapping_node in self.i3d_mapping:
            # If the mapping is an empty string, use the node name
            mapping_name = getattr(mapping_node.blender_object.i3d_mapping, 'mapping_name', '') or mapping_node.name
            new_mappings.append(
                f'{xml_indentation*2}<i3dMapping id="{mapping_name}" node="{_build_index_string(mapping_node)}" />\n'
            )

        # Remove old mappings and insert new ones
        if i3d_mappings_element is not None:
            # Remove existing mappings while keeping <i3dMappings> tag
            end_idx = i3d_mapping_idx
            while end_idx < len(lines) and '</i3dMappings>' not in lines[end_idx]:
                end_idx += 1
            lines[i3d_mapping_idx + 1:end_idx] = new_mappings  # Replace contents
        else:
            lines.insert(i3d_mapping_idx + 1, ''.join(new_mappings) + f"{xml_indentation}</i3dMappings>\n")

        with open(file_path, 'w', encoding='utf-8') as xml_file:
            xml_file.writelines(lines)

        self.logger.info(f"Successfully exported i3dMappings to {file_path}")

# To avoid a circular import, since all nodes rely on the I3D class, but i3d itself contains all the different nodes.
from i3dio.node_classes.node import *
from i3dio.node_classes.shape import *
from i3dio.node_classes.merge_group import *
from i3dio.node_classes.merge_children import *
from i3dio.node_classes.skinned_mesh import *
from i3dio.node_classes.material import *
from i3dio.node_classes.file import *
