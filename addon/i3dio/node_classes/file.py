import logging
import os
import shutil
from inspect import isabstract
from pathlib import Path
from typing import ClassVar

import bpy

from .. import (
    debugging,
    utility,
)
from ..i3d import I3D
from .node import Node


class File(Node):
    ELEMENT_TAG: ClassVar[str] = 'File'
    NAME_FIELD_NAME: ClassVar[str] = 'filename'
    ID_FIELD_NAME: ClassVar[str] = 'fileId'

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if isabstract(cls):
            return
        if "MODHUB_FOLDER" not in cls.__dict__:
            raise TypeError(f"{cls.__name__} must define MODHUB_FOLDER")

    def __init__(self, id_: int, i3d: I3D, filepath: str):
        self.blender_path = filepath  # This should be supplied as the normal blender relative path
        self.resolved_path: Path | None = None
        self.file_name = bpy.path.display_name_from_filepath(self.blender_path)
        self.file_extension = Path(self.blender_path).suffix
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
        return debugging.ObjectNameAdapter(
            logging.getLogger(f"{__name__}.{type(self).__name__}"),
            {'object_name': self.file_name + self.file_extension},
        )

    def _create_xml_element(self):
        # In files, the node name attribute (filename) is also the path to the file. So this needs to be resolved
        # before creating the xml element
        self._resolve_filepath()
        super()._create_xml_element()

    def _resolve_filepath(self):
        """
        Resolves the file path for export.
        - FS data files always reference as $data and are never copied.
        - Other files are copied if copy_files is enabled.
        - Otherwise, relative to blend or absolute.
        """
        if (source_path := utility.as_source_path(self.blender_path)) is None:
            self.logger.warning(
                f"Could not resolve source path for {self.blender_path!r}. "
                "If this is a $data path, check that the FS data path is configured."
            )
        elif not source_path.exists():
            self.logger.warning(f"File {source_path!r} does not exist. The exported I3D may reference a missing file.")

        self.resolved_path = utility.as_export_path(self.blender_path)
        if utility.is_fs_builtin_path(self.resolved_path):
            self.logger.info(f"Resolved as FS $data path: {self.resolved_path}")
            return

        if self.i3d.settings.get('copy_files', False):
            self._copy_file(source_path)
            return

        self.logger.info(f"Resolved filepath: {self.resolved_path}")

        if self.resolved_path.is_absolute():
            self.logger.warning(
                f"File {self.blender_path!r} is outside the blend file folder; using absolute path in I3D."
            )

    def _copy_file(self, source_path: Path | None):
        i3d_folder = Path(self.i3d.paths['i3d_folder'])
        write_directory = i3d_folder
        write_path_full: Path | None = None
        self.logger.info("is not an FS builtin and will be copied")

        if source_path is None:
            self.logger.warning(f"Cannot copy {self.blender_path!r} because the source path could not be resolved")
            return

        if not source_path.exists():
            self.logger.warning(f"File {source_path!r} does not exist, cannot copy")
            return

        match self.i3d.settings.get('file_structure', 'MODHUB'):
            case 'FLAT':
                self.logger.debug("will be copied using the 'FLAT' hierarchy structure")
                self.resolved_path = Path(f"{self.file_name}{self.file_extension}")
                write_path_full = i3d_folder / self.resolved_path
            case 'MODHUB':
                self.logger.debug("will be copied using the 'MODHUB' hierarchy structure")
                self.resolved_path = Path(type(self).MODHUB_FOLDER) / f"{self.file_name}{self.file_extension}"
                write_path_full = i3d_folder / self.resolved_path
            case 'BLENDER':
                self.logger.debug("will be copied using the 'BLENDER' hierarchy structure")

                blend_dir = Path(bpy.data.filepath).parent.resolve(strict=False)
                try:
                    relative_file_path = Path(os.path.relpath(source_path, blend_dir))
                except ValueError:
                    self.logger.debug(
                        "File is on another drive than the .blend file. Defaulting to absolute path and no copying."
                    )
                    self.resolved_path = source_path
                    return

                parent_steps = sum(1 for part in relative_file_path.parts if part == "..")
                blender_relative_distance_limit = 3  # Limits the distance a file can be from the blend file

                if parent_steps > blender_relative_distance_limit:
                    self.logger.debug(
                        f"File exists more than {blender_relative_distance_limit} folders away from .blend file. "
                        "Defaulting to absolute path and no copying."
                    )
                    self.resolved_path = source_path
                    return

                self.resolved_path = relative_file_path
                write_path_full = i3d_folder / relative_file_path

        if write_path_full is None:
            self.logger.warning("Could not resolve write path for file %r", self.blender_path)
            return

        write_path_full = write_path_full.resolve(strict=False)
        write_directory = write_path_full.parent

        if write_path_full == source_path.resolve(strict=False):
            self.logger.debug("Source and destination paths are the same, no need to copy")
            return

        if self.i3d.settings.get('overwrite_files', False) or not write_path_full.exists():
            write_directory.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy(source_path, write_path_full)
            except shutil.SameFileError:
                pass
            else:
                self.logger.info(f"copied to {write_path_full!r}")
        else:
            self.logger.debug("File already in correct path relative to i3d file and overwrite is turned off")


class Image(File):
    MODHUB_FOLDER = 'textures'


class Shader(File):
    MODHUB_FOLDER = 'shaders'


class Reference(File):
    MODHUB_FOLDER = 'assets'
