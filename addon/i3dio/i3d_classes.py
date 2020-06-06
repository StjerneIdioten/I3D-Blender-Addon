"""This module contains shared functionality between the different modules of the i3dio addon"""
from __future__ import annotations  # Enables python 4.0 annotation typehints fx. class self-referencing
from typing import (Union, Dict, List, Type, OrderedDict, Optional)
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
import collections
import logging
import math
import mathutils
import os
import shutil
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
            self.element = ET.SubElement(self.parent.element, type(self).ELEMENT_TAG, attributes)
            self.logger.debug(f"has parent element with name [{self.parent.name}]")
        except AttributeError:
            self.element = ET.Element(type(self).ELEMENT_TAG, attributes)

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
        self.xml_elements: Dict[str, Union[ET.Element, None]] = {'Node': None}
        try:
            self.parent.add_child(self)
        except AttributeError:
            pass

        super().__init__(id_, i3d, parent)
        self.logger.debug(f"Initialized as a '{self.__class__.__name__}'")

    @property
    def name(self):
        return self.blender_object.name

    @property
    def element(self) -> Union[ET.Element, None]:
        return self.xml_elements['Node']

    @element.setter
    def element(self, value):
        self.xml_elements['Node'] = value

    def __str__(self):
        return f"{self.id}"

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
        self._add_transform_to_xml_element(self._transform_for_conversion)

    def add_child(self, node: SceneGraphNode):
        self.children.append(node)


class ShapeNode(SceneGraphNode):
    ELEMENT_TAG = 'Shape'

    def __init__(self, id_: int, mesh_object: [bpy.types.Object, None], i3d: I3D, parent: [SceneGraphNode or None] = None):
        self.shape_id = None
        super().__init__(id_=id_, blender_object=mesh_object, i3d=i3d, parent=parent)

    @property
    def _transform_for_conversion(self) -> mathutils.Matrix:
        return self.i3d.conversion_matrix @ self.blender_object.matrix_local @ self.i3d.conversion_matrix.inverted()

    def add_shape(self):
        self.shape_id = self.i3d.add_shape(EvaluatedMesh(self.i3d, self.blender_object))

    def populate_xml_element(self):
        self.add_shape()
        self.logger.debug(f"has shape ID '{self.shape_id}'")
        self._write_attribute('shapeId', self.shape_id)
        self._write_attribute('materialIds', self.i3d.shapes[self.shape_id].material_indexes)
        super().populate_xml_element()


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


class MergeGroup:
    def __init__(self, name: str):
        self.name = name
        self.root_node: [MergeGroupRoot, None] = None
        self.child_nodes: List[MergeGroupChild] = list()  # List of child nodes for the merge group
        self.logger = debugging.ObjectNameAdapter(logging.getLogger(f"{__name__}.{type(self).__name__}"),
                                                  {'object_name': self.name})
        self.logger.debug("Initialized merge group")

    # Should only be run once, when the root node is found.
    def set_root(self, root_node: MergeGroupRoot):
        self.root_node = root_node
        if self.child_nodes:
            self.logger.debug(f"{len(self.child_nodes)} were added before the root node was found")
            for child in self.child_nodes:
                self.root_node.add_child(child)
        else:
            self.logger.debug("No pre-added children before root was found")
        return self.root_node

    def add_child(self, child_node: MergeGroupChild):
        self.child_nodes.append(child_node)
        if self.root_node is not None:
            self.root_node.add_child(self.child_nodes[-1])
        return self.child_nodes[-1]


class MergeGroupRoot(ShapeNode):

    def __init__(self, id_: int, merge_group_object: [bpy.types.Object, None], i3d: I3D, parent: [SceneGraphNode or None] = None):
        self.merge_group_name = xml_i3d.merge_group_prefix + merge_group_object.i3d_merge_group.group_id
        self.skin_bind_ids = f"{id_:d} "
        super().__init__(id_=id_, mesh_object=merge_group_object, i3d=i3d, parent=parent)

    # Override default shape behaviour to use the merge group mesh name instead of the blender objects name
    def add_shape(self):
        self.shape_id = self.i3d.add_shape(EvaluatedMesh(self.i3d, self.blender_object), self.merge_group_name, True)

    def add_child(self, child: MergeGroupChild):
        self.logger.debug("Adding Child")
        self.skin_bind_ids += f"{child.id:d} "
        self._write_attribute('skinBindNodeIds', self.skin_bind_ids[:-1])
        self.i3d.shapes[self.shape_id].append_from_evaluated_mesh(
            EvaluatedMesh(self.i3d, child.blender_object, reference_frame=self.blender_object.matrix_world))


class MergeGroupChild(TransformGroupNode):
    pass


class IndexedTriangleSet(Node):
    ELEMENT_TAG = 'IndexedTriangleSet'
    NAME_FIELD_NAME = 'name'
    ID_FIELD_NAME = 'shapeId'

    def __init__(self, id_: int, i3d: I3D, evaluated_mesh: EvaluatedMesh, shape_name: Optional[str] = None,
                 is_merge_group: bool = False):
        self.id: int = id_
        self.i3d: I3D = i3d
        self.evaluated_mesh: EvaluatedMesh = evaluated_mesh
        self.vertices: OrderedDict[Vertex, int] = collections.OrderedDict()
        self.triangles: List[List[int]] = list()  # List of lists of vertex indexes
        self.subsets: OrderedDict[str, SubSet] = collections.OrderedDict()
        self.material_indexes: str = ''
        self.is_merge_group = is_merge_group
        self.bind_index = 0
        if shape_name is None:
            self.shape_name = self.evaluated_mesh.name
        else:
            self.shape_name = shape_name
        super().__init__(id_, i3d, None)

    def _create_xml_element(self) -> None:
        super()._create_xml_element()
        self.xml_elements['vertices'] = ET.SubElement(self.element, 'Vertices')
        self.xml_elements['triangles'] = ET.SubElement(self.element, 'Triangles')
        self.xml_elements['subsets'] = ET.SubElement(self.element, 'Subsets')

    @property
    def name(self):
        return self.shape_name

    @property
    def element(self):
        return self.xml_elements['node']

    @element.setter
    def element(self, value):
        self.xml_elements['node'] = value

    def process_subsets(self, mesh):
        for idx, (material_name, subset) in enumerate(self.subsets.items()):
            self.logger.debug(f"Subset with index [{idx}] based on material '{material_name}'")

            if idx > 0:
                self.logger.debug(f"Previous subset exists")
                _, previous_subset = list(self.subsets.items())[idx-1]
                subset.first_vertex = previous_subset.first_vertex + previous_subset.number_of_vertices
                subset.first_index = previous_subset.first_index + previous_subset.number_of_indices

            self.process_subset(mesh, material_name)

    def process_subset(self, mesh, material_name: str, triangle_offset: int = 0):
        subset = self.subsets[material_name]
        self.logger.debug(f"Processing subset: {subset}")
        for triangle in subset.triangles[triangle_offset:]:

            # Add a new empty container for the vertex indexes of the triangle
            self.triangles.append(list())

            for loop_index in triangle.loops:
                blender_vertex = mesh.vertices[mesh.loops[loop_index].vertex_index]

                # Add vertex color
                vertex_color = None
                if len(mesh.vertex_colors):
                    # Get the color from the active layer, since only one vertex color layer is supported in GE
                    vertex_color = mesh.vertex_colors.active.data[loop_index].color

                # Add uvs
                uvs = []
                for count, uv in enumerate(mesh.uv_layers):
                    if count < 4:
                        uvs.append(uv.data[loop_index].uv)

                vertex = Vertex(material_name,
                                blender_vertex.co.xyz,
                                mesh.loops[loop_index].normal,
                                vertex_color,
                                uvs)

                if vertex not in self.vertices:
                    vertex_index = len(self.vertices)
                    self.vertices[vertex] = vertex_index
                    subset.number_of_vertices += 1
                else:
                    vertex_index = self.vertices[vertex]

                self.triangles[-1].append(vertex_index)

            subset.number_of_indices += 3

        self.logger.debug(f"Has subset '{material_name}' with '{len(subset.triangles)}' triangles and {subset}")

    def populate_from_evaluated_mesh(self):
        mesh = self.evaluated_mesh.mesh
        if len(mesh.materials) == 0:
            self.logger.info(f"has no material assigned, assigning default material")
            mesh.materials.append(self.i3d.get_default_material().blender_material)
            self.logger.info(f"assigned default material i3d_default_material")

        for triangle in mesh.loop_triangles:
            triangle_material = mesh.materials[triangle.material_index]
            if triangle_material.name not in self.subsets:
                self.logger.info(f"Has material {triangle_material.name!r}")
                material_id = self.i3d.add_material(triangle_material)
                self.subsets[triangle_material.name] = SubSet(material_id)

            # Add triangle to subset
            self.subsets[triangle_material.name].add_triangle(triangle)

        self.process_subsets(mesh)

    def append_from_evaluated_mesh(self, mesh_to_append):
        if not self.is_merge_group:
            self.logger.warning("Can't add a mesh to a IndexedTriangleSet that is not a merge group")
            return

        # Material checks for subset consistency
        mesh = mesh_to_append.mesh
        if len(mesh.materials) == 0:
            self.logger.warning(f"Mesh '{mesh.name}' to be added has no materials, "
                                f"mergegroups need to share the same subset!")
            return
        elif len(mesh.materials) > 1:
            self.logger.warning(f"Mesh '{mesh.name}' has more than one material, "
                                f"merge groups need to share the same subset!")
            return
        else:
            if mesh.materials[0].name not in self.subsets:
                self.logger.warning(f"Mesh '{mesh.name}' has a different material from merge group root, "
                                    f"which is not allowed!")
                return

        material_name = mesh.materials[0].name
        triangle_offset = len(self.subsets[material_name].triangles)
        vertex_offset = self.subsets[material_name].number_of_vertices
        for triangle in mesh.loop_triangles:
            self.subsets[material_name].add_triangle(triangle)

        self.bind_index += 1
        self.process_subset(mesh, material_name, triangle_offset)
        self.write_vertices(vertex_offset)
        self.write_triangles(triangle_offset)
        list(self.xml_elements['subsets'])[0].attrib = self.subsets[material_name].as_dict()

    def write_vertices(self, offset=0):
        # Vertices
        self._write_attribute('count', len(self.vertices), 'vertices')
        self._write_attribute('normal', True, 'vertices')
        self._write_attribute('tangent', True, 'vertices')
        for count, _ in enumerate(list(self.vertices.keys())[0].uvs_for_xml()):
            self._write_attribute(f"uv{count}", True, 'vertices')

        if self.is_merge_group:
            self._write_attribute('singleblendweights', True, 'vertices')

        # Write vertices to xml
        for vertex in list(self.vertices.keys())[offset:]:
            vertex_attributes = {'p': vertex.position_for_xml(),
                                 'n': vertex.normal_for_xml()
                                 }

            for count, uv in enumerate(vertex.uvs_for_xml()):
                vertex_attributes[f"t{count}"] = uv

            vertex_color = vertex.vertex_color_for_xml()
            if vertex_color != '':
                vertex_attributes['c'] = vertex_color

            if self.is_merge_group:
                vertex_attributes['bi'] = str(self.bind_index)

            ET.SubElement(self.xml_elements['vertices'], 'v', vertex_attributes)

    def write_triangles(self, offset=0):
        self._write_attribute('count', len(self.triangles), 'triangles')

        # Write triangles to xml
        for triangle in self.triangles[offset:]:
            ET.SubElement(self.xml_elements['triangles'], 't', {'vi': "{0} {1} {2}".format(*triangle)})

    def populate_xml_element(self):
        self.populate_from_evaluated_mesh()
        self.logger.debug(f"Has '{len(self.subsets)}' subsets, "
                          f"'{len(self.triangles)}' triangles and "
                          f"'{len(self.vertices)}' vertices")

        self.write_vertices()
        self.write_triangles()

        # Subsets
        self._write_attribute('count', len(self.subsets), 'subsets')

        # Write subsets
        for _, subset in self.subsets.items():
            self.material_indexes += f"{subset.material_id}"
            ET.SubElement(self.xml_elements['subsets'], 'Subset', subset.as_dict())

        # Removes the last whitespace from the string, since an extra will always be added
        self.material_indexes = self.material_indexes.strip()


class SubSet:
    def __init__(self, material_id: int):
        self.first_index = 0
        self.first_vertex = 0
        self.number_of_indices = 0
        self.number_of_vertices = 0
        self.triangles = []
        self.material_id = material_id

    def as_dict(self):
        subset_attributes = {'firstIndex': f"{self.first_index}",
                             'firstVertex': f"{self.first_vertex}",
                             'numIndices': f"{self.number_of_indices}",
                             'numVertices': f"{self.number_of_vertices}"}
        return subset_attributes

    def __str__(self):
        return f'materialId="{self.material_id}" numTriangles="{len(self.triangles)}" ' \
               f'firstIndex="{self.first_index}" firstVertex="{self.first_vertex}" ' \
               f'numIndices="{self.number_of_indices}" numVertices="{self.number_of_vertices}"'

    def add_triangle(self, triangle):
        self.triangles.append(triangle)


class Vertex:
    def __init__(self, material_name, position, normal, vertex_color, uvs):
        self._material_name = material_name
        self._position = position
        self._normal = normal
        self._vertex_color = vertex_color
        self._uvs = uvs
        self._str = ''
        self._make_hash_string()

    def _make_hash_string(self):
        self._str = f"{self._material_name}{self._position}{self._normal}{self._vertex_color}"

        for uv in self._uvs:
            self._str += f"{uv}"

    def __str__(self):
        return self._str

    def __hash__(self):
        return hash(self._str)

    def __eq__(self, other):
        return f"{self!s}" == f'{other!s}'

    def position_for_xml(self):
        return "{0:.6f} {1:.6f} {2:.6f}".format(*self._position)

    def normal_for_xml(self):
        return "{0:.6f} {1:.6f} {2:.6f}".format(*self._normal)

    def vertex_color_for_xml(self):
        if self._vertex_color is not None:
            return "{0:.6f} {1:.6f} {2:.6f} {3:.6f}".format(*self._vertex_color)
        else:
            return ''

    def uvs_for_xml(self):
        uvs = []
        for uv in self._uvs:
            uvs.append("{0:.6f} {1:.6f}".format(*uv))
        return uvs


class EvaluatedMesh:
    def __init__(self, i3d: I3D, mesh_object: bpy.types.Object, name: str = None,
                 reference_frame: mathutils.Matrix = None):
        if name is None:
            self.name = mesh_object.data.name
        else:
            self.name = name
        self.i3d = i3d
        self.object = None
        self.mesh = None
        self.generate_evaluated_mesh(mesh_object, reference_frame)

    def generate_evaluated_mesh(self, mesh_object: bpy.types.Object, reference_frame: mathutils.Matrix = None):
        # Evaluate the dependency graph to make sure that all data is evaluated. As long as nothing changes, this
        # should only be 'heavy' to call the first time a mesh is exported.
        # https://docs.blender.org/api/current/bpy.types.Depsgraph.html
        depsgraph = bpy.context.evaluated_depsgraph_get()
        if self.i3d.get_setting('apply_modifiers'):
            self.object = mesh_object.evaluated_get(depsgraph).copy()
            logger.debug(f"[{self.name}] is exported with modifiers applied")
        else:
            self.object = mesh_object.copy()
            logger.debug(f"[{self.name}] is exported without modifiers applied")

        self.mesh = self.object.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)

        # If a reference is given transform the generated mesh by that frame to place it somewhere else than center of
        # the mesh origo
        if reference_frame is not None:
            self.mesh.transform(reference_frame.inverted() @ self.object.matrix_world)

        conversion_matrix = self.i3d.conversion_matrix
        if self.i3d.get_setting('apply_unit_scale'):
            logger.debug(f"[{self.name}] applying unit scaling")
            conversion_matrix = \
                mathutils.Matrix.Scale(bpy.context.scene.unit_settings.scale_length, 4) @ conversion_matrix

        self.mesh.transform(conversion_matrix)
        if conversion_matrix.is_negative:
            self.mesh.flip_normals()
            logger.debug(f"[{self.name}] conversion matrix is negative, flipping normals")

        # Calculates triangles from mesh polygons
        self.mesh.calc_loop_triangles()
        # Recalculates normals after the scaling has messed with them
        self.mesh.calc_normals_split()

    def __del__(self):
        self.object.to_mesh_clear()
        bpy.data.objects.remove(self.object, do_unlink=True)


class Material(Node):
    ELEMENT_TAG = 'Material'
    NAME_FIELD_NAME = 'name'
    ID_FIELD_NAME = 'materialId'

    def __init__(self, id_: int, i3d: I3D, blender_material: bpy.types.Material):
        self.blender_material = blender_material
        super().__init__(id_, i3d, None)

    @property
    def name(self):
        return self.blender_material.name

    @property
    def element(self):
        return self.xml_elements['node']

    @element.setter
    def element(self, value):
        self.xml_elements['node'] = value

    def populate_xml_element(self):
        if self.blender_material.use_nodes:
            self._resolve_with_nodes()
        else:
            self._resolve_without_nodes()

    def _resolve_with_nodes(self):
        main_node = self.blender_material.node_tree.nodes.get('Principled BSDF')
        if main_node is not None:
            self._diffuse_from_nodes(main_node)
            self._normal_from_nodes(main_node)
            self._specular_from_nodes(main_node)
        else:
            self.logger.warning(f"Uses nodes but Principled BSDF node is not found!")

        gloss_node = self.blender_material.node_tree.nodes.get('Glossmap')
        if gloss_node is not None:
            try:
                gloss_image_path = gloss_node.inputs['Image'].links[0].from_node.image.filepath
            except (AttributeError, IndexError, KeyError):
                self.logger.exception(f"Has an improperly setup Glossmap")
            else:
                self.logger.debug(f"Has Glossmap '{utility.as_fs_relative_path(gloss_image_path)}'")
                file_id = self.i3d.add_file_image(gloss_image_path)
                self.xml_elements['Glossmap'] = ET.SubElement(self.element, 'Glossmap')
                self._write_attribute('fileId', file_id, 'Glossmap')
        else:
            self.logger.debug(f"Has no Glossmap")

    def _specular_from_nodes(self, node):
        specular = [1.0 - node.inputs['Roughness'].default_value,
                    node.inputs['Specular'].default_value,
                    node.inputs['Metallic'].default_value]
        self._write_specular(specular)

    def _normal_from_nodes(self, node):
        normal_node_socket = node.inputs['Normal']
        if normal_node_socket.is_linked:
            try:
                normal_image_path = normal_node_socket.links[0].from_node.inputs['Color'].links[0] \
                    .from_node.image.filepath
            except (AttributeError, IndexError, KeyError):
                self.logger.exception(f"Has an improperly setup Normalmap")
            else:
                self.logger.debug(f"Has Normalmap '{utility.as_fs_relative_path(normal_image_path)}'")
                file_id = self.i3d.add_file_image(normal_image_path)
                self.xml_elements['Normalmap'] = ET.SubElement(self.element, 'Normalmap')
                self._write_attribute('fileId', file_id, 'Normalmap')
        else:
            self.logger.debug(f"Has no Normalmap")

    def _diffuse_from_nodes(self, node):
        color_socket = node.inputs['Base Color']
        diffuse = color_socket.default_value
        if color_socket.is_linked:
            try:
                color_connected_node = color_socket.links[0].from_node
                if color_connected_node.bl_idname == 'ShaderNodeRGB':
                    diffuse = color_connected_node.outputs[0].default_value
                    diffuse_image_path = None
                else:
                    diffuse_image_path = color_connected_node.image.filepath
            except (AttributeError, IndexError, KeyError):
                self.logger.exception(f"Has an improperly setup Texture")
            else:
                if diffuse_image_path is not None:
                    self.logger.debug(f"Has diffuse texture '{utility.as_fs_relative_path(diffuse_image_path)}'")
                    file_id = self.i3d.add_file_image(diffuse_image_path)
                    self.xml_elements['Texture'] = ET.SubElement(self.element, 'Texture')
                    self._write_attribute('fileId', file_id, 'Texture')
        # Write the diffuse colors
        self._write_diffuse(diffuse)

    def _resolve_without_nodes(self):
        material = self.blender_material
        self._write_diffuse(material.diffuse_color)
        self._write_specular([1.0 - material.roughness, 1, material.metallic])
        self.logger.debug(f"Does not use nodes")

    def _write_diffuse(self, diffuse_color):
        self._write_attribute('diffuseColor', "{0:.6f} {1:.6f} {2:.6f} {3:.6f}".format(*diffuse_color))

    def _write_specular(self, specular_color):
        self._write_attribute('specularColor', "{0:.6f} {1:.6f} {2:.6f}".format(*specular_color))


class File(Node):
    ELEMENT_TAG = 'File'
    NAME_FIELD_NAME = 'filename'
    ID_FIELD_NAME = 'fileId'
    @property
    @classmethod
    @abstractmethod
    def MODHUB_FOLDER(cls):  # The name of the folder that it should go in for the modhub export type
        return NotImplementedError

    def __init__(self, id_: int, i3d: I3D, filepath: str):
        self.blender_path = filepath  # This should be supplied as the normal blender relative path
        self.resolved_path = bpy.path.abspath(self.blender_path)  # Initialize as blender path as default if no changes are made
        self.file_name = bpy.path.display_name_from_filepath(self.blender_path)
        self.file_extension = self.blender_path[self.blender_path.rfind('.'):len(self.blender_path)]
        self._xml_element = None
        super().__init__(id_, i3d, None)

    @property
    def name(self):
        return self.resolved_path

    @property
    def element(self):
        return self._xml_element

    @element.setter
    def element(self, value):
        self._xml_element = value

    # The log gets to scrambled if files are referred by their full path, so just use the filename instead
    def _set_logging_output_name_field(self):
        return debugging.ObjectNameAdapter(logging.getLogger(f"{__name__}.{type(self).__name__}"),
                                           {'object_name': self.file_name + self.file_extension})

    def _create_xml_element(self):
        # In files, the node name attribute (filename) is also the path to the file. So this needs to be resolved
        # before creating the xml element
        self._resolve_filepath()
        super()._create_xml_element()

    def _resolve_filepath(self):
        filepath_absolute = bpy.path.abspath(self.blender_path)
        filepath_relative_to_fs = utility.as_fs_relative_path(filepath_absolute)

        if filepath_relative_to_fs[0] == '$':
            self.resolved_path = filepath_relative_to_fs
        elif bpy.context.scene.i3dio.copy_files:
            self._copy_file()
        else:
            self.resolved_path = filepath_absolute

        self.logger.info(f"Resolved filepath: {self.resolved_path}")

    def _copy_file(self):
        resolved_directory = ""
        write_directory = self.i3d.paths['i3d_folder']
        self.logger.info(f"is not an FS builtin and will be copied")
        file_structure = bpy.context.scene.i3dio.file_structure
        if file_structure == 'FLAT':
            self.logger.debug(f"will be copied using the 'FLAT' hierarchy structure")
        elif file_structure == 'MODHUB':
            self.logger.debug(f"will be copied using the 'MODHUB' hierarchy structure")
            resolved_directory = type(self).MODHUB_FOLDER
            write_directory += '\\' + resolved_directory
        elif file_structure == 'BLENDER':
            self.logger.debug(f"'will be copied using the 'BLENDER' hierarchy structure")
            # TODO: Rewrite this to make it more than three levels above the blend file but allow deeper nesting
            #  ,since current code just counts number of slashes
            blender_relative_distance_limit = 3  # Limits the distance a file can be from the blend file
            # relative steps to avoid copying entire folder structures ny mistake. Defaults to an absolute path.
            if self.blender_path.count("..\\") <= blender_relative_distance_limit:
                # Remove blender relative notation and filename
                resolved_directory = self.blender_path[2:self.blender_path.rfind('\\')]
                write_directory += '\\' + resolved_directory
            else:
                self.logger.debug(f"'exists more than {blender_relative_distance_limit} folders away "
                                  f"from .blend file. Defaulting to absolute path and no copying.")
                self.resolved_path = bpy.path.abspath(self.blender_path)
                return

        self.resolved_path = resolved_directory + '\\' + self.file_name + self.file_extension

        if self.resolved_path != bpy.path.abspath(self.blender_path):  # Check to make sure not to overwrite the file

            # We write the file if it either doesn't exists or if it exists, but we are allowed to overwrite.
            write_path_full = write_directory + '\\' + self.file_name + self.file_extension
            if bpy.context.scene.i3dio.overwrite_files or not os.path.exists(write_path_full):
                os.makedirs(write_directory, exist_ok=True)
                try:
                    shutil.copy(bpy.path.abspath(self.blender_path), write_directory)
                except shutil.SameFileError:
                    pass  # Ignore if source and destination is the same file
                else:
                    self.logger.info(f"copied to '{write_path_full}'")
            else:
                self.logger.debug(f"File already in correct path relative to i3d file and overwrite is turned off")


class Image(File):
    MODHUB_FOLDER = 'textures'





