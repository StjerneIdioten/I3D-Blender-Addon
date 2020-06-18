from abc import abstractmethod
import logging
import os
import shutil
import bpy
from .node import Node
from ..i3d import I3D
from .. import (debugging, utility)


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


class Shader(File):
    MODHUB_FOLDER = 'shaders'