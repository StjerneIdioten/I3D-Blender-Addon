from __future__ import annotations  # Enables python 4.0 annotation typehints fx. class self-referencing
from typing import List
import sys
import time
import logging
import bpy
from bpy_extras.io_utils import (
    axis_conversion
)

from . import (
    debugging,
    xml_i3d
)

from .utility import (BlenderObject, sort_blender_objects_by_name)
from .i3d import I3D
from .node_classes.node import SceneGraphNode
from .node_classes.skinned_mesh import SkinnedMeshRootNode

logger = logging.getLogger(__name__)
logger.debug(f"Loading: {__name__}")


def export_blend_to_i3d(filepath: str, axis_forward, axis_up) -> dict:

    export_data = {}

    if bpy.context.scene.i3dio.log_to_file:
        # Remove the file ending from path and append log specific naming
        filename = filepath[0:len(filepath) - len(xml_i3d.file_ending)] + debugging.export_log_file_ending
        log_file_handler = logging.FileHandler(filename, mode='w')
        log_file_handler.setLevel(logging.DEBUG)
        log_file_handler.setFormatter(debugging.addon_export_log_formatter)
        # Add the handler to top-level exporter, since we want any debug output during the export to be logged.
        debugging.addon_logger.addHandler(log_file_handler)
    else:
        log_file_handler = None

    # Output info about the addon
    debugging.addon_console_handler.setLevel(logging.INFO)
    logger.info(f"Blender version is: {bpy.app.version_string}")
    logger.info(f"I3D Exporter version is: {sys.modules['i3dio'].__version__}")
    logger.info(f"Exported using '{xml_i3d.xml_current_library}'")
    logger.info(f"Exporting to {filepath}")

    if bpy.context.scene.i3dio.verbose_output:
        debugging.addon_console_handler.setLevel(logging.DEBUG)
    else:
        debugging.addon_console_handler.setLevel(debugging.addon_console_handler_default_level)

    time_start = time.time()

    # Wrap everything in a try/catch to handle addon breaking exceptions and also get them in the log file
    try:

        depsgraph = bpy.context.evaluated_depsgraph_get()

        i3d = I3D(name=bpy.path.display_name_from_filepath(filepath),
                  i3d_file_path=filepath,
                  conversion_matrix=axis_conversion(to_forward=axis_forward, to_up=axis_up,).to_4x4(),
                  depsgraph=depsgraph)

        export_selection = bpy.context.scene.i3dio.selection
        if export_selection == 'ALL':
            _export_active_scene_master_collection(i3d)
        elif export_selection == 'ACTIVE_COLLECTION':
            _export_active_collection(i3d)
        elif export_selection == 'ACTIVE_OBJECT':
            _export_active_object(i3d)
        elif export_selection == 'SELECTED_OBJECTS':
            _export_selected_objects(i3d)

        i3d.export_to_i3d_file()

        # Global try/catch exception handler. So that any unspecified exception will still end up in the log file
    except Exception:
        logger.exception("Exception that stopped the exporter")
        export_data['success'] = False
    else:
        export_data['success'] = True

    export_data['time'] = time.time() - time_start

    print(f"Export took {export_data['time']:.3f} seconds")

    # EAFP
    try:
        log_file_handler.close()
    except AttributeError:
        pass

    debugging.addon_logger.removeHandler(log_file_handler)
    debugging.addon_console_handler.setLevel(debugging.addon_console_handler_default_level)
    return export_data


def _export_active_scene_master_collection(i3d: I3D):
    logger.info("'Master Collection' export is selected")
    _export_collection_content(i3d, bpy.context.scene.collection)


def _export_active_collection(i3d: I3D):
    logger.info("'Active collection' export is selected")
    _export_collection_content(i3d, bpy.context.view_layer.active_layer_collection.collection)


def _export_collection_content(i3d: I3D, collection):
    # First export child collections. Collections are not sorted alphabetically in the blender outliner
    _export(i3d, collection.children.values(), sort_alphabetical=False)
    # Then export objects in the collection.
    # `objects` contain every object, also children of other objects, so export only root ones.
    _export(i3d, [obj for obj in collection.objects if obj.parent is None])


def _export_active_object(i3d: I3D):
    logger.info("'Active Object' export is selected")
    if bpy.context.active_object is not None:
        _export(i3d, [bpy.context.active_object])
    else:
        logger.warning("No active object, aborting export")


# TODO: Maybe this should export a sort of skeleton structure if the parents of an object isn't selected?
def _export_selected_objects(i3d: I3D):
    logger.info("'Selected Objects' export is selected'")
    if bpy.context.selected_objects:
        _export(i3d, bpy.context.selected_objects)
    else:
        logger.warning("No selected objects, aborting export")


def _export(i3d: I3D, objects: List[BlenderObject], sort_alphabetical: bool = True):
    objects_to_export = objects
    if sort_alphabetical:
        objects_to_export = sort_blender_objects_by_name(objects)
    for blender_object in objects_to_export:
        _add_object_to_i3d(i3d, blender_object)


def _add_object_to_i3d(i3d: I3D, obj: BlenderObject, parent: SceneGraphNode = None) -> None:
    # Special handling of armature nodes, since they are sort of "extra" compared to how other programs like Maya
    # handles bones. So the option for turning them off is provided.
    _parent = parent
    if not i3d.settings['collapse_armatures'] and isinstance(parent, SkinnedMeshRootNode):
        try:
            _parent = parent.parent
        except AttributeError:
            pass

    # Collections are checked first since these are always exported in some form
    if isinstance(obj, bpy.types.Collection):
        logger.debug(f"[{obj.name}] is a 'Collection'")
        node = i3d.add_transformgroup_node(obj, _parent)
        _process_collection_objects(i3d, obj, node)
        return  # Early return because collections are special
    else:
        logger.debug(f"[{obj.name}] is of type {obj.type!r}")
        if obj.type not in i3d.settings['object_types_to_export']:
            logger.debug(f"[{obj.name}] has type {obj.type!r} which is not a type selected for exporting")
            return
        elif obj.type == 'MESH':
            node = None
            # Skinned meshes takes precedence over merge groups. They can't co-exist on the same object, for export.
            if 'SKINNED_MESHES' in i3d.settings['features_to_export'] \
                    and 'ARMATURE' in i3d.settings['object_types_to_export']:
                # Armatures need to be exported and skinned meshes enabled to create a skinned mesh node
                for modifier in obj.modifiers:
                    # We only need to find one armature to know it should be an armature node
                    if modifier.type == 'ARMATURE':
                        node = i3d.add_skinned_mesh_node(obj, _parent)
                        break

            if node is None:
                if 'MERGE_GROUPS' in i3d.settings['features_to_export'] and obj.i3d_merge_group.group_id != "":
                    # Currently the check for a mergegroup relies solely on whether or not a name is set for it
                    node = i3d.add_merge_group_node(obj, _parent)
                else:
                    # Default to a regular shape node
                    node = i3d.add_shape_node(obj, _parent)

        elif obj.type == 'ARMATURE':
            node = i3d.add_armature(obj, _parent, is_located=True)
        elif obj.type == 'EMPTY':
            node = i3d.add_transformgroup_node(obj, _parent)
            if obj.instance_collection is not None:
                logger.debug(f"[{obj.name}] is a collection instance and will be instanced into the 'Empty' object")
                # This is a collection instance so the children needs to be fetched from the referenced collection and
                # be 'instanced' as children of the 'Empty' object directly.
                _process_collection_objects(i3d, obj.instance_collection, node)
                return
        elif obj.type == 'LIGHT':
            node = i3d.add_light_node(obj, _parent)
        elif obj.type == 'CAMERA':
            node = i3d.add_camera_node(obj, _parent)
        else:
            raise NotImplementedError(f"Object type: {obj.type!r} is not supported yet")

        # Process children of objects (other objects) and children of collections (other collections)
        # WARNING: Might be slow due to searching through the entire object list in the blend file:
        # https://docs.blender.org/api/current/bpy.types.Object.html#bpy.types.Object.children
        logger.debug(f"[{obj.name}] processing objects children")
        for child in sort_blender_objects_by_name(obj.children):
            _add_object_to_i3d(i3d, child, node)
        logger.debug(f"[{obj.name}] no more children to process in object")


def _process_collection_objects(i3d: I3D, collection: bpy.types.Collection, parent: SceneGraphNode):
    """Handles adding object children of collections. Since collections stores their objects in a list named 'objects'
    instead of the 'children' list, which only contains child collections. And they need to be iterated slightly
    different"""

    # Iterate child collections first, since they appear at the top in the blender outliner
    logger.debug(f"[{collection.name}] processing collections children")
    for child in collection.children.values():
        _add_object_to_i3d(i3d, child, parent)
    logger.debug(f"[{collection.name}] no more children to process in collection")

    # Then iterate over the objects contained in the collection
    logger.debug(f"[{collection.name}] processing collection objects")
    for child in sort_blender_objects_by_name(collection.objects):
        # If a collection consists of an object, which has it's own children objects. These children will also be a
        # a part of the collections objects. Which means that they would be added twice without this check. One for the
        # object itself and one for the collection.
        if child.parent is None:
            _add_object_to_i3d(i3d, child, parent)
    logger.debug(f"[{collection.name}] no more objects to process in collection")





