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
from . import debugging

logger = logging.getLogger(__name__)


def export_blend_to_i3d(filepath: str, axis_forward, axis_up) -> None:
    if bpy.context.scene.i3dio.verbose_output:
        debugging.addon_console_handler.setLevel(logging.DEBUG)

    log_file_handler = None
    if bpy.context.scene.i3dio.log_to_file:
        # Remove the file ending from path and append log specific naming
        filename = filepath[0:len(filepath) - len(xml_i3d.file_ending)] + debugging.export_log_file_ending
        log_file_handler = logging.FileHandler(filename, mode='w')
        log_file_handler.setLevel(logging.DEBUG)
        log_file_handler.setFormatter(debugging.addon_export_log_formatter)
        # Add the handler to top-level exporter, since we want any debug output during the export to be logged.
        debugging.addon_logger.addHandler(log_file_handler)

        logger.info(f"Blender version is: {bpy.app.version_string}")
        logger.info(f"I3D Exporter version is: {sys.modules['i3dio'].bl_info.get('version')}")
        logger.info(f"Exporting to {filepath}")
        time_start = time.time()

        # Wrap everything in a try/catch to handle addon breaking exceptions and also get them in the log file
        try:
            i3d = shared.I3D(name=bpy.path.display_name_from_filepath(filepath),
                             i3d_file_path=filepath,
                             conversion_matrix=axis_conversion(to_forward=axis_forward,
                                                               to_up=axis_up,).to_4x4())

            export_selection = bpy.context.scene.i3dio.selection
            if export_selection == 'ALL':
                _export_active_scene_master_collection(i3d)
            elif export_selection == 'ACTIVE_COLLECTION':
                _export_active_collection(i3d)
            elif export_selection == 'ACTIVE_OBJECT':
                _export_active_object(i3d)
            elif export_selection == 'SELECTED_OBJECTS':
                _export_selected_objects(i3d)

            # Global try/catch exception handler. So that any unspecified exception will still end up in the log file
        except Exception:
            logger.exception("Exception that stopped the exporter")

        logger.info(f"Export took {time.time() - time_start:.3f} seconds")

        # EAFP
        try:
            log_file_handler.close()
        except AttributeError:
            pass

        debugging.addon_logger.removeHandler(log_file_handler)
        debugging.addon_console_handler.setLevel(debugging.addon_console_handler_default_level)


def _export_active_scene_master_collection(i3d: shared.I3D):
    pass


def _export_active_collection(i3d: shared.I3D):
    pass


def _export_active_object(i3d: shared.I3D):
    obj = bpy.context.active_object
    i3d.add_transformgroup_node(obj)
    i3d.export_to_i3d_file()


def _export_selected_objects(i3d: shared.I3D):
    pass
