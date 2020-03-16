from __future__ import annotations  # Enables python 4.0 annotation typehints fx. class self-referencing
from typing import Union
import sys
import os
import time
import shutil
import math
import mathutils
import logging

# Old exporter used cElementTree for speed, but it was deprecated to compatibility status in python 3.3
import xml.etree.ElementTree as ET  # Technically not following pep8, but this is the naming suggestion from the module

import bpy
from bpy_extras.io_utils import (
    axis_conversion
)

from . import shared
from . import xml_i3d
from .xml_i3d import (write_attribute, add_indentations)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.handlers = []


# Exporter is a singleton
class Exporter:

    def __init__(self, filepath: str, axis_forward, axis_up):
        #logger = logging.getLogger(__name__)
        logger.setLevel(logging.DEBUG)
        logger.handlers = []  # Clear handlers between runs since the logging module keeps track outside addon

        formatter = logging.Formatter('%(funcName)s:%(levelname)s: %(message)s')

        if bpy.context.scene.i3dio.log_to_file:
            filename = filepath[0:len(filepath) - 4] + '_export_log.txt'
            self._log_file_handler = logging.FileHandler(filename, mode='w')
            self._log_file_handler.setLevel(logging.DEBUG)

            self._log_file_handler.setFormatter(formatter)

            logger.addHandler(self._log_file_handler)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        if bpy.context.scene.i3dio.verbose_output:
            console_handler.setLevel(logging.DEBUG)
        else:
            console_handler.setLevel(logging.WARNING)
        logger.addHandler(console_handler)

        logger.info(f"Blender version is: {bpy.app.version_string}")
        logger.info(f"I3D Exporter version is: {sys.modules['i3dio'].bl_info.get('version')}")
        logger.info(f"Exporting to {filepath}")
        time_start = time.time()

        if 'MERGE_GROUPS' in bpy.context.scene.i3dio.features_to_export:
            logger.info(f"Mergegroup export is enabled")
            self.export_merge_groups = True
        else:
            logger.info(f"Mergegroup export is disabled")
            self.export_merge_groups = False

        # Wrap everything in a try/catch to handle addon breaking exceptions and also get them in the log file
        # noinspection PyBroadException
        try:
            self._scene_graph = SceneGraph()
            self._filepath = filepath
            self._file_indexes = {}
            self.shape_material_indexes = {}
            self.ids = {
                'shape': 1,
                'material': 1,
                'file': 1
            }

            self._global_matrix = axis_conversion(
                to_forward=axis_forward,
                to_up=axis_up,
            ).to_4x4()

            # Merge Group
            self.merge_group_prefix = 'MergedMesh_'
            self.merge_groups = {}

            # Evaluate the dependency graph to make sure that all data is evaluated. As long as nothing changes, this
            # should only be 'heavy' to call the first time a mesh is exported.
            # https://docs.blender.org/api/current/bpy.types.Depsgraph.html
            self._depsgraph = bpy.context.evaluated_depsgraph_get()

            self._xml_build_skeleton_structure()
            self._xml_build_scene_graph()
            self._xml_parse_scene_graph()
            # Resolve skin id's for mergegroups, since this information requires all of the nodes to have been parsed

            if self.export_merge_groups:
                self._xml_resolve_skin_ids()
                logger.info(f"Number of mergegroups: {len(self.merge_groups)}")
                for name, merge_group in self.merge_groups.items():
                    if merge_group.root_object is not None:
                        logger.info(f"Mergegroup '{name}' has root node {merge_group.root_object.name!r}")
                    else:
                        logger.info(f"Mergegroup '{name}' has no root")
                    logger.info(f"Mergegroup '{name}' has {len(merge_group.members)} members (Root not counted)")
                    for member in merge_group.members:
                        logger.debug(f"\t{member.name!r}")

            self._xml_export_to_file()

        # Global try/catch exception handler. So that any unspecified exception will still end up in the log file
        except Exception:
            logger.exception("Exception that stopped the exporter")

        logger.info(f"Export took {time.time() - time_start:.3f} seconds")

        # EAFP
        try:
            self._log_file_handler.close()
        except AttributeError:
            pass

    def _xml_build_scene_graph(self):

        objects_to_export = bpy.context.scene.i3dio.object_types_to_export
        logger.info(f"Object types selected for export: {objects_to_export}")

        def new_graph_node(obj: Union[bpy.types.Object, bpy.types.CollectionObjects,
                                      bpy.types.Collection, bpy.types.CollectionChildren],
                           parent: ExporterNode,
                           unpack_collection: bool = False):

            if not isinstance(obj, bpy.types.Collection):
                if obj.type not in objects_to_export:
                    logger.debug(f"Object {obj.name!r} has type {obj.type!r}, "
                                      f"which is not a type selected for exporting")

                    return

            if unpack_collection:
                node = parent
            else:
                node = self._scene_graph.add_node(obj, parent)
                logger.debug(f"Added Node with ID {node.id} and name {node.obj.name!r}")

            # Expand collection tree into the collection instance
            if isinstance(obj, bpy.types.Object):
                if obj.type == 'EMPTY':
                    if obj.instance_collection is not None:
                        logger.debug(f'{obj.name!r} is a collection instance and will be unpacked')
                        # print(f'This is a collection instance')
                        new_graph_node(obj.instance_collection, node, unpack_collection=True)

            # Gets child objects/collections
            if isinstance(obj, bpy.types.Object):
                if len(obj.children):
                    logger.debug(f"Adding child objects of object {obj.name!r}")
                    # print(f'Children of object')
                    for child in obj.children:
                        new_graph_node(child, node)
                    logger.debug(f"Done adding child objects of object {obj.name!r}")

            # Gets child objects if it is a collection
            if isinstance(obj, bpy.types.Collection):
                if len(obj.children):
                    logger.debug(f"Adding child collections of collection {obj.name!r}")
                    for child in obj.children:
                        new_graph_node(child, node)
                    logger.debug(f"Done adding child collections of collection {obj.name!r}")

                if len(obj.objects):
                    logger.debug(f"Adding objects of collection {obj.name!r}")
                    for child in obj.objects:
                        if child.parent is None:
                            new_graph_node(child, node)
                    logger.debug(f"Done adding objects of collection {obj.name!r}")

        selection = bpy.context.scene.i3dio.selection
        if selection == 'ALL':
            logger.info("Export selection is master collection 'Scene Collection'")
            selection = bpy.context.scene.collection
            new_graph_node(selection, self._scene_graph.nodes[0])
        elif selection == 'ACTIVE_COLLECTION':
            selection = bpy.context.view_layer.active_layer_collection.collection
            logger.info(f"Export selection is collection {selection.name!r}")
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

        def parse_node(node: ExporterNode):

            logger.info(f"Parsing node with id {node.id} and name {node.obj.name!r}")
            self._xml_scene_object_general_data(node)

            if isinstance(node.obj, bpy.types.Collection):
                logger.info(f"{node.obj.name!r} is a collection, getting parsed as a transformgroup")
                self._xml_scene_object_transform_group(node)
            else:
                node_type = node.obj.type
                logger.info(f"{node.obj.name!r} is parsed as a {node_type!r}")
                # merge group id can only ever be set on an object with a mesh, so no need to check for mesh type
                if self.export_merge_groups and node.obj.i3d_merge_group.group_id != '':
                    self._xml_merge_group(node)
                else:
                    if node_type == 'MESH':
                        self._xml_scene_object_shape(node)
                    elif node_type == 'EMPTY':
                        self._xml_scene_object_transform_group(node)
                    elif node_type == 'LIGHT':
                        self._xml_scene_object_light(node)
                    elif node_type == 'CAMERA':
                        self._xml_scene_object_camera(node)

                    try:
                        self._xml_object_properties(node.obj.data.i3d_attributes, node)
                    except AttributeError:
                        logger.debug(f"{node.obj.name!r} has no i3d_attributes")

            for child in node.children.values():
                logger.info(
                    f"Parsing child node {child.obj.name!r} of node {node.obj.name!r}")
                child.i3d_elements['scene_node'] = ET.SubElement(node.i3d_elements['scene_node'],
                                                                 self.blender_to_i3d(child.obj))
                parse_node(child)

        for root_child in self._scene_graph.nodes[0].children.values():
            logger.info(
                f"Parsing child node {root_child.obj.name!r} of root node")
            root_child.i3d_elements['scene_node'] = ET.SubElement(self._tree.find('Scene'),
                                                                  self.blender_to_i3d(root_child.obj))
            parse_node(root_child)

    def _xml_scene_object_general_data(self, node: ExporterNode):
        element = node.i3d_elements['scene_node']
        write_attribute(element, 'name', node.obj.name)
        write_attribute(element, 'nodeId', node.id)
        if isinstance(node.obj, bpy.types.Collection):
            logger.info(
                f"{node.obj.name!r} is a collection and it will be exported as a transformgroup with no "
                f"translation and rotation")
            # Collections dont have any physical properties, but the transformgroups in i3d has so it is set to the
            # default value of GE, which is just zeroed.
        else:
            # Apply the space transformations depending on object, since lights and cameras has their z-axis reversed
            # in GE
            # If you want an explanation for A * B * A^-1 then go look up Transformation Matrices cause I can't
            # remember the specifics
            logger.info(f"{node.obj.name!r} is a {node.obj.type!r}")
            logger.debug(f"{node.obj.name!r} transforming to new transform-basis")

            if node.obj == 'LIGHT' or node.obj.type == 'CAMERA':
                matrix = self._global_matrix @ node.obj.matrix_local
                logger.debug(
                    f"{node.obj.name!r} will not have inversed transform applied to accommodate flipped "
                    f"z-axis in GE ")
            else:
                matrix = self._global_matrix @ node.obj.matrix_local @ self._global_matrix.inverted()

            if node.obj.parent is not None:
                if node.obj.parent.type == 'CAMERA' or node.obj.parent.type == 'LIGHT':
                    matrix = self._global_matrix.inverted() @ matrix
                    logger.debug(
                        f"{node.obj.name!r} will be transformed once more with inverse to accommodate "
                        f"flipped z-axis in GE of parent Light/Camera")

            # Translation with applied unit scaling
            translation = matrix.to_translation()
            if not self.vector_compare(translation, mathutils.Vector((0, 0, 0))):
                # This is way too much effort to get 4 decimal points of precision and nice formatting :-P
                translation = "{0:.6g} {1:.6g} {2:.6g}".format(
                    *[x * bpy.context.scene.unit_settings.scale_length for x in translation])

                write_attribute(element, 'translation', translation)
                logger.debug(f"{node.obj.name!r} translation: [{translation}]")

            # Rotation, no unit scaling since it will always be degrees.
            rotation = [math.degrees(axis) for axis in matrix.to_euler('XYZ')]
            if not self.vector_compare(mathutils.Vector(rotation), mathutils.Vector((0, 0, 0))):
                rotation = "{0:.6g} {1:.6g} {2:.6g}".format(*rotation)
                write_attribute(element, 'rotation', rotation)
                logger.debug(f"{node.obj.name!r} rotation(degrees): [{rotation}]")

            # Scale
            if matrix.is_negative:
                logger.error(f"{node.obj.name!r} has one or more negative scaling components, "
                                  f"which is not supported in Giants Engine. Scale reset to (1, 1, 1)")
            else:
                scale = matrix.to_scale()
                if not self.vector_compare(scale, mathutils.Vector((1, 1, 1))):
                    scale = "{0:.6g} {1:.6g} {2:.6g}".format(*scale)

                    write_attribute(element, 'scale', scale)
                    logger.debug(f"{node.obj.name!r} scale: [{scale}]")

            # Write the object transform properties from the blender UI into the object
            self._xml_object_properties(node.obj.i3d_attributes, node)

    def _xml_object_properties(self, propertygroup, node):
        logger.info(f"Writing non-default properties from propertygroup: '{type(propertygroup).__name__}'")
        # Since blender properties are basically abusing the annotation system, we can also abuse this to create
        # a generic property export function by accessing the annotation dictionary
        properties_written = 0
        for prop_key in propertygroup.__annotations__.keys():
            prop_name = prop_key
            value = getattr(propertygroup, prop_key)
            value_to_write = value
            default = propertygroup.i3d_map[prop_key].get('default')
            i3d_name = propertygroup.i3d_map[prop_key].get('name')
            field_type = propertygroup.i3d_map[prop_key].get('type')
            i3d_element = node.i3d_elements[propertygroup.i3d_map[prop_key].get('placement', 'scene_node')]

            # Special case of checking floats, since these can be not equal due to floating point errors
            if isinstance(value, float):
                if math.isclose(value, default, abs_tol=0.0000001):
                    continue
            # In the case that the value is default, then just ignore it
            elif value == default:
                continue
            # In some cases of enums the i3d_name is actually the enum value itself. It is signaled by not having a name
            elif i3d_name is None:
                i3d_name = value
                value_to_write = 1
            # String field is used for unique types, that then get converted fx. HEX values. This is signaled by
            # having an extra type field in the i3d_map dictionary entry for the propertygroup
            elif field_type is not None:
                if field_type == 'HEX':
                    try:
                        value_decimal = int(value, 16)
                    except ValueError:
                        logger.error(f"Supplied value '{value}' for '{prop_name}' is not a hex value!")
                        continue
                    else:
                        if 0 <= value_decimal <= 2**32-1:  # Check that it is actually a 32-bit unsigned int
                            value_to_write = value_decimal
                        else:
                            logger.warning(f"Supplied value '{value}' for '{prop_name}' is out of bounds."
                                                f" It should be within range [0, ffffffff] (32-bit unsigned)")
                            continue

            logger.debug(f"\tProperty '{prop_name}' with value '{value}'. Default is '{default}'")
            write_attribute(i3d_element, i3d_name, value_to_write)
            properties_written += 1

        logger.info(f"Wrote '{properties_written}' properties")

    def _xml_add_material(self, material: bpy.types.Material) -> int:

        materials_root = self._tree.find('Materials')
        material_element = materials_root.find(f".Material[@name={material.name!r}]")
        if material_element is None:
            logger.info(f"{material.name!r} is a new material")
            material_element = ET.SubElement(materials_root, 'Material')
            write_attribute(material_element, 'name', material.name)
            write_attribute(material_element, 'materialId', self.ids['material'])

            if material.use_nodes:
                logger.debug(f"{material.name!r} uses nodes")
                material_node = material.node_tree.nodes.get('Principled BSDF')
                if material_node is not None:
                    # Diffuse ##########################################################################################
                    color_socket = material_node.inputs['Base Color']
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
                            logger.exception(f"{material.name!r} has an improperly setup Texture")
                        else:
                            if diffuse_image_path is not None:
                                logger.debug(f"{material.name!r} has Texture "
                                                  f"'{Exporter.as_fs_relative_path(diffuse_image_path)}'")
                                file_id = self._xml_add_file(diffuse_image_path)
                                texture_element = ET.SubElement(material_element, 'Texture')
                                write_attribute(texture_element, 'fileId', f'{file_id:d}')

                    write_attribute(material_element,
                                    'diffuseColor',
                                    "{0:.6f} {1:.6f} {2:.6f} {3:.6f}".format(*diffuse))

                    # Normal ###########################################################################################
                    normal_node_socket = material_node.inputs['Normal']
                    if normal_node_socket.is_linked:
                        try:
                            normal_image_path = normal_node_socket.links[0].from_node.inputs['Color'].links[0] \
                                .from_node.image.filepath
                        except (AttributeError, IndexError, KeyError):
                            logger.exception(f"{material.name!r} has an improperly setup Normalmap")
                        else:
                            logger.debug(f"{material.name!r} has Normalmap "
                                              f"'{Exporter.as_fs_relative_path(normal_image_path)}'")
                            file_id = self._xml_add_file(normal_image_path)
                            normal_element = ET.SubElement(material_element, 'Normalmap')
                            write_attribute(normal_element, 'fileId', f'{file_id:d}')
                    else:
                        logger.debug(f"{material.name!r} has no Normalmap")

                    # Specular #########################################################################################
                    write_attribute(material_element,
                                    'specularColor',
                                    f"{1.0 - material_node.inputs['Roughness'].default_value:f} "
                                    f"{material_node.inputs['Specular'].default_value:.6f} "
                                    f"{material_node.inputs['Metallic'].default_value:f}")
                else:
                    logger.warning(f"{material.name!r} uses nodes but Principled BSDF node is not found!")

                # Gloss ################################################################################################

                # It would be nice to check for a label instead, since this shows up as the name of the node inside of
                # the shader view. But it is harder to index and not unique. So sticking to the name instead.
                gloss_node = material.node_tree.nodes.get('Glossmap')
                if gloss_node is not None:
                    try:
                        gloss_image_path = gloss_node.inputs['Image'].links[0].from_node.image.filepath
                    except (AttributeError, IndexError, KeyError):
                        logger.exception(f"{material.name!r} has an improperly setup Glossmap")
                    else:
                        logger.debug(f"{material.name!r} has Glossmap "
                                          f"'{Exporter.as_fs_relative_path(gloss_image_path)}'")
                        file_id = self._xml_add_file(gloss_image_path)
                        normal_element = ET.SubElement(material_element, 'Glossmap')
                        write_attribute(normal_element, 'fileId', f'{file_id:d}')
                else:
                    logger.debug(f"{material.name!r} has no Glossmap")

            else:
                logger.debug(f"{material.name!r} does not use nodes")
                write_attribute(material_element,
                                'diffuseColor',
                                "{0:.6f} {1:.6f} {2:.6f} {3:.6f}".format(*material.diffuse_color))

                write_attribute(material_element,
                                'specularColor',
                                f"{1.0 - material.roughness:f} {1:.6f} {material.metallic:f}")

            self.ids['material'] += 1
        else:
            logger.info(f"{material.name!r} is already in i3d file")

        material_id = int(material_element.get('materialId'))
        logger.debug(f"{material.name!r} has material ID {material_id}")
        return material_id

    def _xml_add_file(self, filepath, file_folder='textures') -> int:
        # print("Relative path: " + filepath)
        filepath_absolute = bpy.path.abspath(filepath)
        # print("Absolute path: " + filepath_absolute)
        files_root = self._tree.find('Files')
        filename = filepath_absolute[filepath_absolute.rfind('\\') + 1:len(filepath_absolute)]
        filepath_i3d = self._filepath[0:self._filepath.rfind('\\') + 1]
        file_structure = bpy.context.scene.i3dio.file_structure

        logger.debug(f"'{filename}' has blender relative path '{filepath}'")
        logger.debug(f"'{filename}' has absolute path '{filepath_absolute}'")

        # Check if the file is relative to the fs data folder and thus should be references as such
        filepath_resolved = Exporter.as_fs_relative_path(filepath_absolute)

        output_dir = ""
        # Resolve the filename and write the file
        if filepath_resolved[0] != '$':
            if bpy.context.scene.i3dio.copy_files:
                logger.info(f"'{filename}' is non-relative to FS and will be copied")
                if file_structure == 'FLAT':
                    logger.debug(f"'{filename}' will be copied using the 'FLAT' hierarchy structure")
                elif file_structure == 'MODHUB':
                    logger.debug(f"'{filename}' will be copied using the 'MODHUB' hierarchy structure")
                    output_dir = file_folder + '\\'
                elif file_structure == 'BLENDER':
                    logger.debug(f"'{filename}' will be copied using the 'BLENDER' hierarchy structure")
                    # TODO: Rewrite this to make it more than three levels above the blend file but allow deeper nesting
                    #  ,since current code just counts number of slashes
                    blender_relative_distance_limit = 3  # Limits the distance a file can be from the blend file
                    if filepath.count("..\\") <= blender_relative_distance_limit:
                        # relative steps to avoid copying entire folder structures ny mistake.
                        # Defaults to a absolute path.
                        output_dir = filepath[
                                     2:filepath.rfind('\\') + 1]  # Remove blender relative notation and filename
                    else:
                        logger.debug(
                            f"'{filename}' exists more than {blender_relative_distance_limit} folders away "
                            f"from .blend file. Defaulting to absolute path and no copying.")
                        output_dir = filepath_absolute[0:filepath_absolute.rfind('\\') + 1]

                filepath_resolved = output_dir + filename

                # Check to see if the generated output filepath is the same as the original filepath and the file isn't
                # already added to the xml
                if filepath_resolved != filepath_absolute:
                    if filepath_resolved not in self._file_indexes:
                        if bpy.context.scene.i3dio.overwrite_files or \
                                not os.path.exists(filepath_i3d + output_dir + filename):
                            # print("Path: " + filepath_i3d + output_dir)
                            os.makedirs(filepath_i3d + output_dir, exist_ok=True)
                            try:
                                shutil.copy(filepath_absolute, filepath_i3d + output_dir)
                            except shutil.SameFileError:
                                pass  # Ignore if source and destination is the same file
                            else:
                                logger.info(f"'{filename}' copied to '{filepath_i3d + output_dir + filename}'")
                    else:
                        logger.info(f"'{filename}' is already indexed in i3d file")

        else:
            logger.debug(f"'{filename}' was resolved to FS relative path '{filepath_resolved}'")

        # Predicate search feature of ElemTree does NOT play nicely with the filepath names, so we loop the old
        # fashioned way
        if filepath_resolved in self._file_indexes:
            file_id = self._file_indexes[filepath_resolved]
        else:
            file_element = ET.SubElement(files_root, 'File')
            file_id = self.ids['file']
            self.ids['file'] += 1
            self._file_indexes[filepath_resolved] = file_id

            write_attribute(file_element, 'fileId', file_id)
            write_attribute(file_element, 'filename', filepath_resolved)

        logger.debug(f"'{filename}' has file ID {file_id}")
        return file_id

    def _xml_add_indexed_triangle_set(self, name: str) -> [bool, ET.Element]:
        # Get reference to the shape element
        shape_root = self._tree.find('Shapes')
        # Check if the triangle element already exists
        pre_existed = True
        indexed_triangle_element = shape_root.find(f".IndexedTriangleSet[@name='{name}']")
        if indexed_triangle_element is None:
            logger.info(f"'{name}' is a new IndexedTriangleSet")
            pre_existed = False
            # Get and increment shape id
            shape_id = self.ids['shape']
            self.ids['shape'] += 1
            # Create triangle element and necessary sub-elements
            indexed_triangle_element = ET.SubElement(shape_root, 'IndexedTriangleSet')
            write_attribute(indexed_triangle_element, 'name', name)
            write_attribute(indexed_triangle_element, 'shapeId', shape_id)
            ET.SubElement(indexed_triangle_element, 'Vertices')
            ET.SubElement(indexed_triangle_element, 'Triangles')
            ET.SubElement(indexed_triangle_element, 'Subsets')

        return pre_existed, indexed_triangle_element

    def _object_to_evaluated_mesh(self, obj: bpy.types.Object,
                                  from_frame=None) -> [bpy.types.Object, bpy.types.Mesh]:
        """Generates object based on whether or not modifiers are applied. Generates mesh from this object and
        converts it to correct coordinate-frame """
        if bpy.context.scene.i3dio.apply_modifiers:
            # Generate an object evaluated from the dependency graph
            # The copy is important since the depsgraph will store changes to the evaluated object
            obj_resolved = obj.evaluated_get(self._depsgraph).copy()
            logger.info(f"{obj.name!r} is exported with modifiers applied")
        else:
            obj_resolved = obj.copy()
            logger.info(f"{obj.name!r} is exported without modifiers applied")

        # Get the mesh from the resolved object, which contains all of the modifiers applied (but not object transform)
        mesh = obj_resolved.to_mesh(preserve_all_data_layers=True, depsgraph=self._depsgraph)

        if from_frame is not None:
            mesh.transform(from_frame.inverted() @ obj_resolved.matrix_world)

        conversion_matrix = self._global_matrix
        if bpy.context.scene.i3dio.apply_unit_scale:
            logger.info(f"{obj.name!r} has unit scaling applied")
            conversion_matrix = mathutils.Matrix.Scale(bpy.context.scene.unit_settings.scale_length, 4) \
                @ conversion_matrix

        mesh.transform(conversion_matrix)
        if conversion_matrix.is_negative:
            mesh.flip_normals()
            logger.debug(f"{obj.name!r} conversion matrix is negative, flipping normals")

        # Calculates triangles from mesh polygons
        mesh.calc_loop_triangles()
        # Recalculates normals after the scaling has messed with them
        mesh.calc_normals_split()

        return mesh, obj_resolved

    def _mesh_to_indexed_triangle_set(self, mesh: bpy.types.Mesh, mesh_id: int) -> IndexedTriangleSet:
        indexed_triangle_set = IndexedTriangleSet()
        indexed_triangle_set.name = mesh.name
        # Make sure that the mesh has some form of material added. Since GE requires at least a default material
        if len(mesh.materials) == 0:
            logger.info(f"{mesh.name!r} has no material assigned")
            if bpy.data.materials.get('i3d_default_material') is None:
                bpy.data.materials.new('i3d_default_material')
                logger.info(f"Default material does not exist. Creating i3d_default_material")
            mesh.materials.append(bpy.data.materials.get('i3d_default_material'))
            logger.info(f"{mesh.name!r} assigned default material i3d_default_material")

        # Group triangles by subset, since they need to be exported in correct order per material subset to the i3d
        triangle_subsets = {}
        for triangle in mesh.loop_triangles:
            triangle_material = mesh.materials[triangle.material_index]
            if triangle_material.name not in triangle_subsets:
                triangle_subsets[triangle_material.name] = []
                logger.info(f"{mesh.name!r} has material {triangle_material.name!r}")
                # TODO: Look at this material stuff
                material_id = self._xml_add_material(triangle_material)
                if mesh_id in self.shape_material_indexes.keys():
                    self.shape_material_indexes[mesh_id] += f",{material_id:d}"
                else:
                    self.shape_material_indexes[mesh_id] = f"{material_id:d}"

            # Add triangle to subset
            triangle_subsets[triangle_material.name].append(triangle)

        added_vertices = {}  # Key is a unique hashable vertex identifier and the value is a vertex index
        vertex_counter = 0  # Count the total number of unique vertices (total across all subsets)
        indices_total = 0  # Total amount of indices, since i3d format needs this number (for some reason)

        if len(mesh.vertex_colors):
            logger.info(f"{mesh.name!r} has colour painted vertices")

        for mat, subset in triangle_subsets.items():
            number_of_indices = 0
            number_of_vertices = 0
            indexed_triangle_set.subsets.append([indices_total, vertex_counter])

            # Go through every triangle on the subset and extract triangle information
            for triangle in subset:

                # Go through every loop that the triangle consists of and extract vertex information
                triangle_vertex_index = []  # The vertices from the vertex list that specify this triangle
                for loop_index in triangle.loops:
                    vertex = mesh.vertices[mesh.loops[loop_index].vertex_index]
                    normal = mesh.loops[loop_index].normal
                    vertex_data = {'p': f"{vertex.co.xyz[0]:.6f} "
                                        f"{vertex.co.xyz[1]:.6f} "
                                        f"{vertex.co.xyz[2]:.6f}",

                                   'n': f"{normal.xyz[0]:.6f} "
                                        f"{normal.xyz[1]:.6f} "
                                        f"{normal.xyz[2]:.6f}",

                                   'uvs': {},
                                   }

                    # If there is vertex paint, then get the colour from the active layer since only one layer is
                    # supported in GE
                    if len(mesh.vertex_colors):
                        vertex_data['c'] = "{0:.6f} {1:.6f} {2:.6f} {3:.6f}".format(
                            *mesh.vertex_colors.active.data[loop_index].color)

                    # TODO: Check uv limit in GE
                    # Old addon only supported 4
                    for count, uv in enumerate(mesh.uv_layers):
                        if count < 4:
                            vertex_data['uvs'][f't{count:d}'] = f"{uv.data[loop_index].uv[0]:.6f} " \
                                                                f"{uv.data[loop_index].uv[1]:.6f}"
                        else:
                            pass
                            # print(f"Currently only supports four uv layers per vertex")

                    vertex_item = VertexItem(vertex_data, mat)

                    if vertex_item not in added_vertices:
                        added_vertices[vertex_item] = vertex_counter
                        indexed_triangle_set.vertices.append(vertex_data)
                        vertex_counter += 1
                        number_of_vertices += 1

                    triangle_vertex_index.append(added_vertices[vertex_item])

                number_of_indices += 3  # 3 loops = 3 indices per triangle
                indexed_triangle_set.triangles.append(triangle_vertex_index)

            indexed_triangle_set.subsets[-1].append(number_of_indices)
            indexed_triangle_set.subsets[-1].append(number_of_vertices)

            logger.debug(f"{mesh.name!r} has subset '{mat}' with {len(subset)} triangles, "
                              f"{number_of_vertices} vertices and {number_of_indices} indices")
            indices_total += number_of_indices

        logger.debug(f"{mesh.name!r} has a total of {len(indexed_triangle_set.vertices)} vertices")
        logger.debug(f"{mesh.name!r} consists of {len(indexed_triangle_set.triangles)} triangles")
        logger.info(f"{mesh.name!r} has {len(indexed_triangle_set.subsets)} subsets")

        return indexed_triangle_set

    def _xml_indexed_triangle_set(self, indexed_triangle_set: IndexedTriangleSet, indexed_triangle_element: ET.Element,
                                  bind_id=None, append=False):

        # Vertices #################################################################################################
        vertices_element = indexed_triangle_element.find(f".Vertices")

        if bind_id is not None:
            write_attribute(vertices_element, 'singleblendweights', True)

        for vertex_data in indexed_triangle_set.vertices:
            vertex_element = ET.SubElement(vertices_element, 'v')
            write_attribute(vertex_element, 'n', vertex_data['n'])
            write_attribute(vertex_element, 'p', vertex_data['p'])
            if 'c' in vertex_data:
                write_attribute(vertex_element, 'c', vertex_data['c'])
            for uv_key, uv_data in vertex_data['uvs'].items():
                write_attribute(vertex_element, uv_key, uv_data)
            if bind_id is not None:
                write_attribute(vertex_element, 'bi', bind_id)

        # Check the first vertex to see if it has a color component (Since they all have it then)
        if 'c' in indexed_triangle_set.vertices[0]:
            write_attribute(vertices_element, 'color', True)

        # TODO: Check uv limit in GE, Old addon only supported 4
        for count, uv in enumerate(indexed_triangle_set.vertices[0]['uvs']):
            if count < 4:
                write_attribute(vertices_element, f'uv{count}', True)

        prev_vertex_count = int(vertices_element.get('count', 0))

        write_attribute(vertices_element,
                        'count',
                        len(indexed_triangle_set.vertices) + int(vertices_element.get('count', 0)))
        write_attribute(vertices_element, 'normal', True)
        write_attribute(vertices_element, 'tangent', True)

        # Triangles ################################################################################################
        triangles_element = indexed_triangle_element.find(f".Triangles")

        for triangle in indexed_triangle_set.triangles:
            triangle_element = ET.SubElement(triangles_element, 't')
            triangle_vertex_index = ""
            for elem in triangle:
                triangle_vertex_index += f"{elem + prev_vertex_count} "

            write_attribute(triangle_element, 'vi', triangle_vertex_index.strip())

        write_attribute(triangles_element,
                        'count',
                        len(indexed_triangle_set.triangles) + int(triangles_element.get('count', 0)))

        # Subsets ##################################################################################################
        subsets_element = indexed_triangle_element.find(f".Subsets")
        subset_count = len(indexed_triangle_set.subsets)

        if append:
            subset_element = subsets_element.find(f".Subset")
            if subset_count > 1:
                logger.error(f"Multiple subsets(materials) are not supported for mergegroups! "
                                  f"This will most likely crash GE or give weird behaviour!")
                subset_count = 1
            else:
                subset = indexed_triangle_set.subsets[0]
                write_attribute(subset_element, 'firstIndex', subset[0])
                write_attribute(subset_element, 'firstVertex', subset[1])
                write_attribute(subset_element, 'numIndices', subset[2] +
                                int(subset_element.get('numIndices', 0)))
                write_attribute(subset_element, 'numVertices', subset[3] +
                                int(subset_element.get('numVertices', 0)))
        else:
            for idx, subset in enumerate(indexed_triangle_set.subsets):
                subset_element = ET.SubElement(subsets_element, 'Subset')
                write_attribute(subset_element, 'firstIndex', subset[0])
                write_attribute(subset_element, 'firstVertex', subset[1])
                write_attribute(subset_element, 'numIndices', subset[2])
                write_attribute(subset_element, 'numVertices', subset[3])

        write_attribute(subsets_element, 'count', subset_count)

    def _xml_resolve_skin_ids(self):
        for merge_group in self.merge_groups.values():
            if merge_group.root_object is not None:
                skin_bind = ""
                for node_id in merge_group.skin_bind_id:
                    skin_bind += f"{node_id:d} "
                write_attribute(merge_group.root_object_element, 'skinBindNodeIds', skin_bind.strip())

    def _xml_merge_group(self, node):
        obj = node.obj
        element = node.i3d_elements['scene_node']
        logger.info(f"{obj.name!r} is exported as part of a mergegroup")
        merge_group = self.merge_groups.setdefault(obj.i3d_merge_group.group_id,
                                                   MergeGroup(obj.i3d_merge_group.group_id))
        if obj.i3d_merge_group.is_root:
            if merge_group.root_object is not None:
                logger.warning(f"{obj.name!r} is set as a root node, but a "
                                    f"root node has already been registered for "
                                    f"merge group '{merge_group.group_id}'. Object mesh wont be exported!")
            else:
                logger.info(f"{obj.name!r} is the root of mergegroup '{merge_group.group_id}'")
                merge_group.root_object = obj
                merge_group.root_object_element = element
                merge_group.skin_bind_id.insert(0, int(element.get('nodeId')))
                _, merge_group.indexed_triangle_element = \
                    self._xml_add_indexed_triangle_set(f"{self.merge_group_prefix}{merge_group.group_id}")
                node.i3d_elements['indexed_triangle_set'] = merge_group.indexed_triangle_element
                mesh, obj_eval = self._object_to_evaluated_mesh(obj)
                indexed_triangle_set = self._mesh_to_indexed_triangle_set(mesh, merge_group.shape_id)
                self._xml_indexed_triangle_set(indexed_triangle_set, merge_group.indexed_triangle_element,
                                               bind_id=0, append=False)
                obj_eval.to_mesh_clear()
                bpy.data.objects.remove(obj_eval, do_unlink=True)
                write_attribute(element, 'shapeId', merge_group.shape_id)
                write_attribute(element, 'materialIds',
                                self.shape_material_indexes[merge_group.shape_id])
                for bind_id, member in enumerate(merge_group.members, start=1):
                    mesh, obj_eval = self._object_to_evaluated_mesh(member,
                                                                    from_frame=merge_group.root_object.matrix_world)
                    indexed_triangle_set = self._mesh_to_indexed_triangle_set(mesh, merge_group.shape_id)
                    self._xml_indexed_triangle_set(indexed_triangle_set, merge_group.indexed_triangle_element,
                                                   bind_id=bind_id, append=True)
                    obj_eval.to_mesh_clear()
                    bpy.data.objects.remove(obj_eval, do_unlink=True)

                try:
                    self._xml_object_properties(obj.data.i3d_attributes, node)
                except AttributeError:
                    logger.debug(f"{obj.obj.name!r} has no i3d_attributes")
        else:
            if merge_group.root_object is None:
                logger.debug(f"{obj.name!r} handled before root node of mergegroup '{merge_group.group_id}' "
                                  f"has been found, mesh export is deferred till root is found")
                merge_group.add_member(obj, int(element.get('nodeId')))
            else:
                logger.debug(f"{obj.name!r} is added to mergegroup's IndexedTriangleSet element")
                bind_id = merge_group.add_member(obj, int(element.get('nodeId')))
                mesh, obj_eval = self._object_to_evaluated_mesh(obj, from_frame=merge_group.root_object.matrix_world)
                indexed_triangle_set = self._mesh_to_indexed_triangle_set(mesh, merge_group.shape_id)
                self._xml_indexed_triangle_set(indexed_triangle_set, merge_group.indexed_triangle_element,
                                               bind_id=bind_id, append=True)
                obj_eval.to_mesh_clear()
                bpy.data.objects.remove(obj_eval, do_unlink=True)

    def _xml_scene_object_shape(self, node):
        obj = node.obj
        element = node.i3d_elements['scene_node']
        # Check if the mesh has already been defined in the i3d file
        pre_exists, indexed_triangle_element = self._xml_add_indexed_triangle_set(obj.data.name)
        node.i3d_elements['indexed_triangle_set'] = indexed_triangle_element
        shape_id = int(indexed_triangle_element.get('shapeId'))
        if not pre_exists:
            # Fetch an evaluated mesh and the object is was generated from (Needed to clear mesh from memory)
            mesh, obj_eval = self._object_to_evaluated_mesh(obj)
            # Generate the indexed triangle set data needed to describe a mesh in i3d format
            indexed_triangle_set = self._mesh_to_indexed_triangle_set(mesh, shape_id)
            # Write this data to the triangle set, overwriting any existing data
            self._xml_indexed_triangle_set(indexed_triangle_set, indexed_triangle_element, append=False)
            # Clean out the generated mesh so it does not stay in blender memory
            obj_eval.to_mesh_clear()
            # Clean out the object copy
            bpy.data.objects.remove(obj_eval, do_unlink=True)
        else:
            logger.info(f"{obj.name!r} already exists in i3d file")

        logger.debug(f"{obj.name!r} has shape ID {shape_id}")
        write_attribute(element, 'shapeId', shape_id)
        write_attribute(element, 'materialIds', self.shape_material_indexes[shape_id])

    def _xml_scene_object_transform_group(self, node: ExporterNode):
        pass

    def _xml_scene_object_camera(self, node: ExporterNode):
        camera = node.obj.data
        element = node.i3d_elements['scene_node']
        write_attribute(element, 'fov', camera.lens)
        write_attribute(element, 'nearClip', camera.clip_start)
        write_attribute(element, 'farClip', camera.clip_end)
        logger.info(f"{node.obj.name!r} is a camera with fov {camera.lens}, "
                         f"near clipping {camera.clip_start} and far clipping {camera.clip_end}")
        if camera.type == 'ORTHO':
            write_attribute(element, 'orthographic', True)
            write_attribute(element, 'orthographicHeight', camera.ortho_scale)
            logger.info(f"{node.obj.name!r} is orthographic with height {camera.ortho_scale}")
        else:
            logger.info(f"{node.obj.name!r} is not orthographic")

    def _xml_scene_object_light(self, node: ExporterNode):
        light = node.obj.data
        element = node.i3d_elements['scene_node']
        light_type = light.type
        logger.info(f"{node.obj.name!r} is a light of type {light_type!r}")
        falloff_type = None
        if light_type == 'POINT':
            light_type = 'point'
            falloff_type = light.falloff_type
        elif light_type == 'SUN':
            light_type = 'directional'
        elif light_type == 'SPOT':
            light_type = 'spot'
            falloff_type = light.falloff_type
            cone_angle = math.degrees(light.spot_size)
            write_attribute(element, 'coneAngle', cone_angle)
            logger.info(f"{node.obj.name!r} has a cone angle of {cone_angle}")
            # Blender spot 0.0 -> 1.0, GE spot 0.0 -> 5.0
            drop_off = 5.0 * light.spot_blend
            write_attribute(element, 'dropOff', drop_off)
            logger.info(f"{node.obj.name!r} has a drop off of {drop_off}")
        elif light_type == 'AREA':
            light_type = 'point'
            logger.warning(f"{node.obj.name!r} is an AREA light, "
                                f"which is not supported and defaults to point light")

        write_attribute(element, 'type', light_type)

        color = "{0:f} {1:f} {2:f}".format(*light.color)
        write_attribute(element, 'color', color)
        logger.info(f"{node.obj.name!r} has color {color}")

        write_attribute(element, 'range', light.distance)
        logger.info(f"{node.obj.name!r} has range {light.distance}")

        write_attribute(element, 'castShadowMap', light.use_shadow)
        logger.info(f"{node.obj.name!r} "
                         f"{'casts shadows' if light.use_shadow else 'does not cast shadows'}")

        if falloff_type is not None:
            if falloff_type == 'CONSTANT':
                falloff_type = 0
                logger.info(f"{node.obj.name!r} "
                                 f"has decay rate of type {'CONSTANT'} which is 0 in i3d")
            elif falloff_type == 'INVERSE_LINEAR':
                falloff_type = 1
                logger.info(f"{node.obj.name!r} "
                                 f"has decay rate of type {'INVERSE_LINEAR'} which is 1 in i3d")
            elif falloff_type == 'INVERSE_SQUARE':
                falloff_type = 2
                logger.info(f"{node.obj.name!r} "
                                 f"has decay rate of type {'INVERSE_SQUARE'} which is 2 in i3d")
            write_attribute(element, 'decayRate', falloff_type)

    def _xml_export_to_file(self) -> None:
        xml_i3d.add_indentations(self._tree)  # Make the xml human readable by adding indents
        try:
            ET.ElementTree(self._tree).write(self._filepath, xml_declaration=True, encoding='iso-8859-1', method='xml')
        except Exception as error:  # A bit slouchy exception handling. Should be more specific and not catch all
            logger.exception(error)
        else:
            logger.info(f"Wrote i3d to file '{self._filepath}'")

    def blender_to_i3d(self, obj: Union[bpy.types.Object, bpy.types.Collection]):
        # Collections don't have an object type since they aren't objects. If they are used for organisational purposes
        # they are converted into transformgroups in the scenegraph
        if isinstance(obj, bpy.types.Collection):
            return 'TransformGroup'
        # For setting the child meshes of a mergegroups to transformgroups
        elif obj.type == 'MESH' and self.export_merge_groups:
            if obj.i3d_merge_group.group_id != '':
                if not obj.i3d_merge_group.is_root:
                    return 'TransformGroup'

        switcher = {
            'MESH': 'Shape',
            'CURVE': 'Shape',
            'EMPTY': 'TransformGroup',
            'CAMERA': 'Camera',
            'LIGHT': 'Light',
            'COLLECTION': 'TransformGroup'
        }
        return switcher[obj.type]

    @staticmethod
    def as_fs_relative_path(filepath: str):
        """If the filepath is relative to the fs dir, then return it with $ refering to the fs data dir
        else return the path"""
        relative_filter = 'Farming Simulator 19'
        try:
            return '$' + filepath[filepath.index(relative_filter) + len(relative_filter) + 1: len(filepath)]
        except ValueError:
            return filepath

    @staticmethod
    def vector_compare(a: mathutils.Vector, b: mathutils.Vector, epsilon=0.0000001) -> bool:
        print(f"arg type: {type(a)}")
        if len(a) != len(b) or not isinstance(a, mathutils.Vector) or not isinstance(b, mathutils.Vector):
            raise TypeError("Both arguments must be vectors of equal length!")

        for idx in range(0, len(a) - 1):
            if not math.isclose(a[idx], b[idx], abs_tol=epsilon):
                return False

        return True


class MergeGroup(object):
    def __init__(self, merge_group_id):
        self.group_id = merge_group_id
        self.root_object = None
        self.root_object_element = None
        self.indexed_triangle_element = None
        self.members = []
        self.skin_bind_id = []

    @property
    def shape_id(self):
        return int(self.indexed_triangle_element.get('shapeId'))

    def add_member(self, obj, node_id):
        self.members.append(obj)
        self.skin_bind_id.append(node_id)
        return len(self.members)


class IndexedTriangleSet(object):
    def __init__(self):
        self.name = ''
        self.vertices = []
        self.triangles = []
        self.subsets = []


class SceneGraph(object):

    def __init__(self):
        self.ids = {
            'node': 0
        }
        self.nodes = {}
        # Create the root node
        self.add_node()  # Add the root node that contains the tree

    def __str__(self):
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

        traverse(self.nodes[1])  # Start at the first element instead since the root isn't necessary to print out

        tree_string += f"{longest_string * '-'}\n"

        return f"{longest_string * '-'}\n" + tree_string

    def add_node(self,
                 obj: Union[bpy.types.Object, bpy.types.Collection] = None,
                 parent: ExporterNode = None) -> ExporterNode:
        new_node = ExporterNode(self.ids['node'], parent, obj)
        self.nodes[new_node.id] = new_node
        self.ids['node'] += 1
        return new_node


class ExporterNode(shared.Node):
    def __init__(self,
                 node_id: int or None = None,
                 parent: ExporterNode or None = None,
                 obj: Union[bpy.types.Object, bpy.types.Collection] or None = None):
        super().__init__(node_id, parent)
        self.obj = obj

    def __str__(self):
        return super().__str__() + f"|{self.obj.name!r}"


class VertexItem:
    """Define unique vertex items (Could be the same vertex but with a different color or material uv"""

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
