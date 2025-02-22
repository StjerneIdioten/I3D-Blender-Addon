from __future__ import annotations  # Enables python 4.0 annotation typehints fx. class self-referencing
from typing import List
import sys
from pathlib import PurePath
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

from .utility import (BlenderObject, sort_blender_objects_by_outliner_ordering)
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
    logger.info(f"I3D Exporter version is: {sys.modules['i3dio'].__version__}")
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

        i3d.export_to_i3d_file()

        if operator.binarize_i3d:
            logger.info(f'Starting binarization of "{filepath}"')
            try:
                i3d_binarize_path = PurePath(None if (path := bpy.context.preferences.addons['i3dio'].preferences.i3d_converter_path) == "" else path)
            except TypeError:
                logger.error(f"Empty Converter Binary Path")
            else:
                try:
                    # This is under the assumption that the data folder is always in the gamefolder! (Which is usually the case, but imagine having the data folder on a dev machine just for Blender)
                    game_path = PurePath(None if (path := bpy.context.preferences.addons['i3dio'].preferences.fs_data_path) == "" else path).parent
                except TypeError:
                    logger.error(f"Empty Game Path")
                else:
                    try:
                        conversion_result = subprocess.run(args=[str(i3d_binarize_path), '-in', str(filepath), '-out', str(filepath), '-gamePath', f"{game_path}/"], timeout=BINARIZER_TIMEOUT_IN_SECONDS, check=True, text=True, stdout = subprocess.PIPE, stderr=subprocess.STDOUT)
                    except FileNotFoundError as e:
                        logger.error(f'Invalid path to i3dConverter.exe: "{i3d_binarize_path}"')
                    except subprocess.TimeoutExpired as e:
                        if e.output is not None and "Press any key to continue . . ." in e.output.decode():
                            logger.error(f'i3dConverter.exe could not run with provided arguments: {e.cmd}')
                        else:
                            logger.error(f"i3dConverter.exe took longer than {BINARIZER_TIMEOUT_IN_SECONDS} seconds to run and was cancelled!")
                    except subprocess.CalledProcessError as e:
                        logger.error(f"i3dConverter.exe failed to run with error code: {e.returncode}")
                    else:
                        if error_messages := [f"\t{error_line}" for error_line in conversion_result.stdout.split('\n', -1) if error_line.startswith("Error:")]:
                            logger.error("i3dConverter.exe produced errors:\n" + '\n'.join(error_messages))
                        else:
                            logger.info(f'Finished binarization of "{filepath}"')

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
        objects_to_export = sort_blender_objects_by_outliner_ordering(objects)

    new_objects_to_export = [obj for root_obj in objects for obj in traverse_hierarchy(root_obj)]
    for obj in new_objects_to_export:
        if obj not in i3d.all_objects_to_export:
            i3d.all_objects_to_export.append(obj)

    for blender_object in objects_to_export:
        _add_object_to_i3d(i3d, blender_object)

    if i3d.deferred_constraints:
        _process_deferred_constraints(i3d)


def _add_object_to_i3d(i3d: I3D, obj: BlenderObject, parent: SceneGraphNode = None) -> None:
    # Check if object should be excluded from export (including its children)
    if hasattr(obj, 'i3d_attributes') and obj.i3d_attributes.exclude_from_export:
        logger.info(f"Skipping [{obj.name}] and its children. Excluded from export.")
        return

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
        node = None
        if i3d.settings['keep_collections_as_transformgroups']:
            node = i3d.add_transformgroup_node(obj, _parent)
        else:
            i3d.logger.info(f"[{obj.name}] will be be ignored and its children will be added to nearest parent")
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
                        if modifier.object is None:
                            logger.warning(f"Armature modifier '{modifier.name}' on skinned mesh '{obj.name}' "
                                           "has no armature object assigned. Exporting as a regular shape instead.")
                            break
                        elif modifier.object not in i3d.all_objects_to_export:
                            logger.warning(
                                f"Skinned mesh '{obj.name}' references armature '{modifier.object.name}', "
                                "but the armature is not included in the export hierarchy. "
                                "Exporting as a regular shape instead."
                            )
                            break
                        else:
                            node = i3d.add_skinned_mesh_node(obj, _parent)
                            break

            if node is None:
                if 'MERGE_GROUPS' in i3d.settings['features_to_export'] and obj.i3d_merge_group_index != -1:
                    blender_merge_group = bpy.context.scene.i3dio_merge_groups[obj.i3d_merge_group_index]
                    if obj.i3d_merge_group_index not in i3d.merge_groups:
                        i3d.merge_groups[obj.i3d_merge_group_index] = MergeGroup(xml_i3d.merge_group_prefix + blender_merge_group.name)
                    node = i3d.add_merge_group_node(obj, _parent, blender_merge_group.root is obj)
                else:
                    # Default to a regular shape node
                    node = i3d.add_shape_node(obj, _parent)

        elif obj.type == 'ARMATURE':
            node = i3d.add_armature_from_scene(obj, _parent)
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
        elif obj.type == 'CURVE':
            node = i3d.add_shape_node(obj, _parent)
        else:
            raise NotImplementedError(f"Object type: {obj.type!r} is not supported yet")

        # Process children of objects (other objects) and children of collections (other collections)
        # WARNING: Might be slow due to searching through the entire object list in the blend file:
        # https://docs.blender.org/api/current/bpy.types.Object.html#bpy.types.Object.children
        logger.debug(f"[{obj.name}] processing objects children")
        for child in sort_blender_objects_by_outliner_ordering(obj.children):
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
    for child in sort_blender_objects_by_outliner_ordering(collection.objects):
        # If a collection consists of an object, which has it's own children objects. These children will also be a
        # a part of the collections objects. Which means that they would be added twice without this check. One for the
        # object itself and one for the collection.
        if child.parent is None:
            i3d.all_objects_to_export.append(child)
            _add_object_to_i3d(i3d, child, parent)
    logger.debug(f"[{collection.name}] no more objects to process in collection")


def traverse_hierarchy(obj: BlenderObject) -> List[BlenderObject]:
    """Recursively traverses an object hierarchy and returns all objects."""
    return [obj] + [child for child in obj.children for child in traverse_hierarchy(child)]


def _process_deferred_constraints(i3d: I3D):
    for armature, bone_object, target in i3d.deferred_constraints:
        i3d.logger.debug(f"Processing deferred constraint for: {bone_object}, Target: {target}")

        if target in i3d.processed_objects:
            i3d.logger.debug(f"Target object '{target}' is included in the export hierarchy. Setting bone parent.")
            bone_name = bone_object.name
            bone = next((b for b in i3d.skinned_meshes[armature.name].bones if b.name == bone_name), None)

            if bone is not None:
                i3d.skinned_meshes[armature.name].update_bone_parent(None, custom_target=i3d.processed_objects[target],
                                                                     bone=bone)
            else:
                i3d.logger.warning(f"Could not find bone {bone_name} in the armature's bone list!")
