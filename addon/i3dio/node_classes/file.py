from abc import abstractmethod
import logging
from pathlib import Path
import shutil
import bpy

from .node import Node

from .. import (
    debugging,
    utility,
)

from ..i3d import I3D


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
        self.resolved_path: Path = None
        self.file_name = bpy.path.display_name_from_filepath(self.blender_path)
        self.file_extension = self.blender_path[self.blender_path.rfind('.'):len(self.blender_path)]
        self._xml_element = None
        super().__init__(id_, i3d, None)

    @property
    def name(self):
        return self.resolved_path.as_posix()

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
        filepath_relative_to_fs = utility.as_fs_relative_path(self.blender_path)

        if filepath_relative_to_fs.startswith('$data'):
            self.resolved_path = Path(filepath_relative_to_fs)
        elif self.i3d.settings.get('copy_files', False):
            self._copy_file()
        else:
            self.resolved_path = Path(filepath_relative_to_fs)

        self.logger.info(f"Resolved filepath: {self.resolved_path}")

    def _copy_file(self):
        resolved_directory = Path()
        write_directory = Path(self.i3d.paths['i3d_folder'])
        self.logger.info("is not an FS builtin and will be copied")

        match self.i3d.settings.get('file_structure', 'MODHUB'):
            case 'FLAT':
                self.logger.debug("will be copied using the 'FLAT' hierarchy structure")
            case 'MODHUB':
                self.logger.debug("will be copied using the 'MODHUB' hierarchy structure")
                resolved_directory = Path(type(self).MODHUB_FOLDER)
                write_directory /= resolved_directory
            case 'BLENDER':
                self.logger.debug("'will be copied using the 'BLENDER' hierarchy structure")
                # TODO: Rewrite this to make it more than three levels above the blend file but allow deeper nesting
                #  ,since current code just counts number of slashes
                blender_relative_distance_limit = 3  # Limits the distance a file can be from the blend file
                blender_path = Path(self.blender_path)
                # relative steps to avoid copying entire folder structures ny mistake. Defaults to an absolute path.
                if self.blender_path.count("..\\") <= blender_relative_distance_limit:
                    # Remove relative notation and get the directory path
                    resolved_directory = Path(*blender_path.parts[2:])
                    write_directory /= resolved_directory
                else:
                    self.logger.debug(
                        f"exists more than {blender_relative_distance_limit} folders away from .blend file. "
                        f"Defaulting to absolute path and no copying."
                    )
                    self.resolved_path = Path(bpy.path.abspath(self.blender_path))
                    return

        self.resolved_path = resolved_directory / f"{self.file_name}{self.file_extension}"

        # Ensure we do not overwrite the source file
        source_path = Path(bpy.path.abspath(self.blender_path))
        if self.resolved_path != source_path:
            # We write the file if it doesn't exist or if overwrite is allowed
            write_path_full = write_directory / f"{self.file_name}{self.file_extension}"
            overwrite_files = self.i3d.settings.get('overwrite_files', False)
            if overwrite_files or not write_path_full.exists():
                write_directory.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.copy(source_path, write_directory)
                except shutil.SameFileError:
                    pass  # Ignore if source and destination is the same file
                else:
                    self.logger.info(f"copied to '{write_path_full}'")
            else:
                self.logger.debug("File already in correct path relative to i3d file and overwrite is turned off")


class Image(File):
    MODHUB_FOLDER = 'textures'


class Shader(File):
    MODHUB_FOLDER = 'shaders'


class Reference(File):
    MODHUB_FOLDER = 'assets'
