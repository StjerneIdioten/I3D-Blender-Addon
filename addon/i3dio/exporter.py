from __future__ import annotations  # Enables python 4.0 annotation typehints fx. class self-referencing
from typing import List
import sys
import subprocess
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

from .utility import (BlenderObject, sort_blender_objects_by_outliner_ordering, get_fs_data_path)
from .i3d import I3D
from .node_classes.node import SceneGraphNode
from .node_classes.skinned_mesh import SkinnedMeshRootNode
from .node_classes.merge_group import MergeGroup

logger = logging.getLogger(__name__)
logger.debug(f"Loading: {__name__}")

BINARIZER_TIMEOUT_IN_SECONDS = 30


def export_blend_to_i3d(operator, filepath: str, axis_forward, axis_up, settings) -> dict:
    export_data = {}

    if operator.log_to_file:
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
    logger.info(f"I3D Exporter version is: {sys.modules[__package__].__version__}")
    logger.info(f"Exporting to {filepath}")

    if operator.verbose_output:
        debugging.addon_console_handler.setLevel(logging.DEBUG)
    else:
        debugging.addon_console_handler.setLevel(debugging.addon_console_handler_default_level)

    time_start = time.time()

    # Wrap everything in a try/catch to handle addon breaking exceptions and also get them in the log file
    try:

        depsgraph = bpy.context.evaluated_depsgraph_get()

        i3d = I3D(name=bpy.path.display_name_from_filepath(filepath),
                  i3d_file_path=filepath,
                  conversion_matrix=axis_conversion(to_forward=axis_forward, to_up=axis_up, ).to_4x4(),
                  depsgraph=depsgraph,
                  settings=settings)

        # Log export settings
        logger.info("Exporter settings:")
        for setting, value in i3d.settings.items():
            logger.info(f"  {setting}: {value}")

        # Handle case when export is triggered from a collection
        source_collection = None
        if operator.collection:
            source_collection = bpy.data.collections.get(operator.collection)
            if not source_collection:
                operator.report({'ERROR'}, f"Collection '{operator.collection}' was not found")
                return None

        if source_collection:
            logger.info(f"Exporting using Blender's collection export feature. Collection: '{source_collection.name}'")
            _export_collection_content(i3d, source_collection)
        else:
            match operator.selection:
                case 'ALL':
                    _export_active_scene_master_collection(i3d)
                case 'ACTIVE_COLLECTION':
                    _export_active_collection(i3d)
                case 'ACTIVE_OBJECT':
                    _export_active_object(i3d)
                case 'SELECTED_OBJECTS':
                    _export_selected_objects(i3d)

        if i3d.deferred_constraints:
            _process_deferred_constraints(i3d)

        if i3d.deferred_shapes_to_populate:
            logger.info(f"Processing {len(i3d.deferred_shapes_to_populate)} deferred shapes (Merge Groups / Generics)")
            for shape_to_process in i3d.deferred_shapes_to_populate:
                shape_to_process.process_and_write_mesh_data()

        if i3d.anim_links:
            i3d.add_animations()

        i3d.export_to_i3d_file()

        if operator.binarize_i3d:
            _binarize_i3d(filepath, operator, logger)

    # Global try/catch exception handler. So that any unspecified exception will still end up in the log file
    except Exception:
        logger.exception("Exception that stopped the exporter")
        export_data['success'] = False
    else:
        export_data['success'] = True

    export_data['time'] = time.time() - time_start

    logger.info(f"Export took {export_data['time']:.3f} seconds")

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


def _export_selected_objects(i3d: I3D):
    if not bpy.context.selected_objects:
        logger.warning("No objects selected for export")
        return
    if i3d.settings['selection_traverse_children']:
        logger.info("'Selected Objects' export is selected, traversing children")
        _export(i3d, bpy.context.selected_objects)
    else:
        logger.info("'Selected Objects' export is selected, exporting only selected objects without children traversal")
        _export_selected_only(i3d, bpy.context.selected_objects)


def _export_selected_only(i3d: I3D, selected_objs: list[BlenderObject]):
    """Export only the selected objects, without traversing their children."""
    selection_set = set(selected_objs)
    i3d.all_objects_to_export.extend(selected_objs)
    # Create a parent map to keep track of the "new" hierarchy based on the selection
    parent_map = {}
    roots = []
    for obj in selected_objs:
        parent = obj.parent
        # Find the nearest parent that is also in the selection set
        while parent and parent not in selection_set:
            parent = parent.parent
        if parent and parent in selection_set:
            parent_map[obj] = parent
        else:
            roots.append(obj)
    i3d._selection_set = selection_set
    i3d._parent_map = parent_map
    for root in sort_blender_objects_by_outliner_ordering(roots):
        _add_object_to_i3d(i3d, root)


def _export(i3d: I3D, objects: List[BlenderObject], sort_alphabetical: bool = True):
    objects_to_export = sort_blender_objects_by_outliner_ordering(objects) if sort_alphabetical else objects

    _all_objects = [obj for root_obj in objects for obj in traverse_hierarchy(root_obj)]
    existing_objects = set(i3d.all_objects_to_export)
    i3d.all_objects_to_export.extend([obj for obj in _all_objects if obj not in existing_objects])

    for blender_object in objects_to_export:
        _add_object_to_i3d(i3d, blender_object)


def _add_object_to_i3d(i3d: I3D, obj: BlenderObject, parent: SceneGraphNode = None) -> None:
    # Collections are checked first since these are always exported in some form
    if isinstance(obj, bpy.types.Collection):
        logger.debug(f"[{obj.name}] is a 'Collection'")
        node = None
        if i3d.settings['keep_collections_as_transformgroups']:
            node = i3d.add_transformgroup_node(obj, parent)
        else:
            i3d.logger.info(f"[{obj.name}] will be ignored and its children will be added to nearest parent")
        _process_collection_objects(i3d, obj, node)
        return  # Collections use a different hierarchy and are handled separately in _process_collection_objects

    # Check if object should be excluded from export (including its children)
    if obj.i3d_attributes.exclude_from_export:
        logger.info(f"Skipping [{obj.name}] and its children. Excluded from export.")
        return

    if obj.type not in i3d.settings['object_types_to_export']:
        logger.debug(f"[{obj.name}] has type {obj.type!r} which is not a type selected for exporting")
        return

    _parent = parent
    # Special handling for collapsed armatures: Unlike Maya, Blender treats armatures differently, so when an armature
    # is collapsed, its children should be reassigned to the armature's parent (or scene root) to maintain hierarchy.
    if isinstance(parent, SkinnedMeshRootNode) and parent.is_collapsed:
        logger.debug(f"[{obj.name}] is under a collapsed armature. Moving it to the armature's parent.")
        _parent = parent.parent

    logger.debug(f"[{obj.name}] is of type {obj.type!r}")
    match obj.type:
        case 'MESH':
            # MergeChildren objects take precedence over any other Shape type
            if 'MERGE_CHILDREN' in i3d.settings['features_to_export'] and obj.i3d_merge_children.enabled:
                if obj.children and any(child.type == 'MESH' for child in obj.children):
                    logger.debug(f"Processing MergeChildren for: {obj.name}")
                    node = i3d.add_merge_children_node(obj, _parent)
                    return  # Return to prevent children from being processed the "normal" way
                else:
                    logger.warning(
                        f"[{obj.name}] is marked as 'MergeChildren' "
                        "but has no child meshes. Exporting as regular Shape."
                    )

            # Merge Groups take precedence over Skinned Meshes
            elif 'MERGE_GROUPS' in i3d.settings['features_to_export'] and obj.i3d_merge_group_index > -1:
                blender_merge_group = bpy.context.scene.i3dio_merge_groups[obj.i3d_merge_group_index]
                i3d.merge_groups.setdefault(
                    obj.i3d_merge_group_index, MergeGroup(xml_i3d.merge_group_prefix + blender_merge_group.name)
                )
                node = i3d.add_merge_group_node(obj, _parent)

            # Process Skinned Meshes if enabled and MergeChildren wasn't applied
            elif ('SKINNED_MESHES' in i3d.settings['features_to_export']
                  and 'ARMATURE' in i3d.settings['object_types_to_export']
                  and (armature_mod := next((mod for mod in obj.modifiers if mod.type == 'ARMATURE'), None))
                  ):
                if armature_mod.object is None:
                    logger.warning(
                        f"Armature modifier '{armature_mod.name}' on skinned mesh '{obj.name}' "
                        "has no armature object assigned. Exporting as a regular shape instead."
                    )
                elif armature_mod.object not in i3d.all_objects_to_export:
                    logger.warning(
                        f"Skinned mesh '{obj.name}' references armature '{armature_mod.object.name}', but the "
                        "armature is not included in the export hierarchy. Exporting as a regular shape instead."
                    )
                else:
                    # Armatures need to be exported and skinned meshes enabled to create a skinned mesh node
                    # We only need to find one armature to confirm it should be a skinned mesh
                    node = i3d.add_skinned_mesh_node(obj, _parent)

            # Default to a regular Shape if none of the special types applied
            else:
                node = i3d.add_shape_node(obj, _parent)
        case 'ARMATURE':
            node = i3d.add_armature_from_scene(obj, _parent)
        case 'EMPTY':
            node = i3d.add_transformgroup_node(obj, _parent)
            if obj.instance_collection is not None:
                logger.debug(f"[{obj.name}] is a collection instance and will be instanced into the 'Empty' object")
                # This is a collection instance so the children needs to be fetched from the referenced
                # collection and be 'instanced' as children of the 'Empty' object directly.
                _process_collection_objects(i3d, obj.instance_collection, node)
                return
        case 'LIGHT':
            node = i3d.add_light_node(obj, _parent)
        case 'CAMERA':
            node = i3d.add_camera_node(obj, _parent)
        case 'CURVE':
            node = i3d.add_shape_node(obj, _parent)
        case _:
            raise NotImplementedError(f"Object type: {obj.type!r} is not supported yet")

    # Process children of objects (other objects) and children of collections (other collections)
    # WARNING: Might be slow due to searching through the entire object list in the blend file:
    # https://docs.blender.org/api/current/bpy.types.Object.html#bpy.types.Object.children
    if getattr(i3d, '_selection_set', None) is not None:
        children = [child for child in i3d._selection_set if i3d._parent_map.get(child) == obj]
        for child in sort_blender_objects_by_outliner_ordering(children):
            _add_object_to_i3d(i3d, child, node)
    else:
        logger.debug(f"[{obj.name}] processing objects children")
        for child in sort_blender_objects_by_outliner_ordering(obj.children):
            _add_object_to_i3d(i3d, child, node)
        logger.debug(f"[{obj.name}] no more children to process in object")


def _process_collection_objects(i3d: I3D, collection: bpy.types.Collection, parent: SceneGraphNode):
    """Handles adding object children of collections. Since collections stores their objects in a list named 'objects'
    instead of the 'children' list, which only contains child collections. And they need to be iterated slightly
    different"""

    _all_objects = [obj for root_obj in collection.objects for obj in traverse_hierarchy(root_obj)]
    existing_objects = set(i3d.all_objects_to_export)
    i3d.all_objects_to_export.extend([obj for obj in _all_objects if obj not in existing_objects])

    # Iterate child collections first, since they appear at the top in the blender outliner
    logger.debug(f"[{collection.name}] processing collections children")
    for child in collection.children.values():
        _add_object_to_i3d(i3d, child, parent)
    logger.debug(f"[{collection.name}] no more children to process in collection")

    # Then iterate over the objects contained in the collection
    logger.debug(f"[{collection.name}] processing collection objects")
    for child in sort_blender_objects_by_outliner_ordering(collection.objects):
        # If a collection consists of an object, which has it's own children objects. These children will also be a
        # a part of the collections objects. Which means that they would be added twice without this check. One for the
        # object itself and one for the collection.
        if child.parent is None:
            _add_object_to_i3d(i3d, child, parent)
    logger.debug(f"[{collection.name}] no more objects to process in collection")


def traverse_hierarchy(obj: BlenderObject) -> List[BlenderObject]:
    """Recursively traverses an object hierarchy and returns all objects."""
    return [obj] + [child for child in obj.children for child in traverse_hierarchy(child)]


def _process_deferred_constraints(i3d: I3D):
    for bone_node, target_obj in i3d.deferred_constraints:
        i3d.logger.debug(f"Processing deferred constraint for: {bone_node}, Target: {target_obj}")
        if target_node := i3d.processed_objects.get(target_obj):
            bone_node.reparent(target_node)
        else:
            i3d.logger.warning(f"Target '{target_obj}' is not processed or not in export list. Skipping.")


def _binarize_i3d(filepath: str, operator, logger: logging.Logger):
    """Tries to binarize the exported I3D file"""
    if not (converter_path := bpy.context.preferences.addons[__package__].preferences.i3d_converter_path):
        logger.error("No i3dConverter path set in preferences. Skipping binarization.")
        return
    if not (game_path := get_fs_data_path(as_path=True).parent):
        logger.error("No game data path set in preferences. Skipping binarization.")
        return

    logger.info(f"Starting binarization of {filepath!r}")
    try:
        conversion_result = subprocess.run(
            args=[
                str(converter_path),
                '-in', str(filepath),
                '-out', str(filepath),
                '-gamePath', f"{game_path}/"
            ],
            timeout=BINARIZER_TIMEOUT_IN_SECONDS,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )
    except FileNotFoundError:
        logger.error(f"Invalid path to i3dConverter.exe: {converter_path!r}")
    except subprocess.TimeoutExpired as e:
        logger.error(f"i3dConverter.exe timed out after {BINARIZER_TIMEOUT_IN_SECONDS} seconds. Output: {e.output!r}")
    except subprocess.CalledProcessError as e:
        logger.error(f"i3dConverter.exe failed to run with error code: {e.returncode}")
    else:
        error_messages = [f"\t{line}" for line in conversion_result.stdout.split('\n') if line.startswith("Error:")]
        if error_messages:
            logger.error("i3dConverter.exe produced errors:\n" + '\n'.join(error_messages))
            operator.report({'ERROR'}, "i3dConverter.exe reported errors. See log for details.")
        else:
            logger.info(f'Finished binarization of "{filepath}"')
            operator.report({'INFO'}, "Binarization completed successfully.")
