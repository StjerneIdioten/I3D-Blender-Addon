from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, TypeVar

import bpy
import mathutils

from .. import debugging
from .ids import IdAllocator
from .ir import ExportIR, SceneBuilder, SceneNode
from .messages import ExportMessages
from .reporting import Reporter
from .resources import FileTable, MaterialTable

T = TypeVar("T")


@dataclass(slots=True)
class ExportContext:
    """Shared state for a single export run.
    The context owns export-wide state, but should avoid becoming the place
    where actual export work happens. Traversal/resolve/serialize modules should
    perform the work and use this as shared state.
    """

    is_dev: bool
    operator: Any
    filepath: Path
    depsgraph: bpy.types.Depsgraph
    scene: bpy.types.Scene
    conversion_matrix: mathutils.Matrix
    settings: Mapping[str, Any]

    name: str = field(init=False)
    messages: ExportMessages = field(default_factory=ExportMessages)
    ids: IdAllocator = field(default_factory=IdAllocator)
    ir: ExportIR = field(default_factory=ExportIR)

    features: frozenset[str] = field(init=False, repr=False)
    conversion_matrix_inv: mathutils.Matrix = field(init=False)
    builder: SceneBuilder = field(init=False)
    files: FileTable = field(init=False)
    materials: MaterialTable = field(init=False)
    i3d_folder: Path = field(init=False)

    unit_scale: float = 1.0
    addon_pref: bpy.types.AddonPreferences | None = None

    def __post_init__(self) -> None:
        self.filepath = Path(self.filepath)

        self.name = bpy.path.display_name_from_filepath(str(self.filepath))
        self.unit_scale = self.scene.unit_settings.scale_length
        self.conversion_matrix_inv = self.conversion_matrix.inverted_safe()
        self.builder = SceneBuilder(self)
        self.files = FileTable(self)
        self.materials = MaterialTable(self)
        self.i3d_folder = self.filepath.parent
        self.features = frozenset(self.settings.get("features_to_export", ()))

    def setting(self, key: str, default: T) -> T:
        """Return a setting value, or default if the setting is missing."""
        return self.settings.get(key, default)

    def has_feature(self, feature: str) -> bool:
        return feature in self.features

    def logger(self, name: str = "export") -> logging.Logger:
        return debugging.get_logger(name)

    def ctx_logger(
        self,
        *,
        name: str = "export",
        object_name: str | None = None,
        node_kind: str | None = None,
        node_id: int | None = None,
        prefix: str | None = None,
    ) -> logging.LoggerAdapter:
        """Create a logger adapter with export context labels."""

        return debugging.ContextAdapter(
            self.logger(name),
            {"object_name": object_name, "node_kind": node_kind, "node_id": node_id, "prefix": prefix or ""},
        )

    def node_logger(self, node: SceneNode, *, name: str = "export", prefix: str | None = None) -> logging.LoggerAdapter:
        return self.ctx_logger(
            name=name, object_name=node.name, node_kind=node.kind.value, node_id=node.id, prefix=prefix
        )

    def reporter(self, prefix: str | None = None, *, name: str = "export") -> Reporter:
        return Reporter(self, self.ctx_logger(name=name, prefix=prefix), operator=self.operator)

    def node_reporter(self, node: SceneNode, prefix: str | None = None, *, name: str = "export") -> Reporter:
        return Reporter(self, self.node_logger(node, name=name, prefix=prefix), operator=self.operator)

    def object_reporter(self, obj: bpy.types.ID, prefix: str | None = None, *, name: str = "export") -> Reporter:
        return Reporter(
            self,
            self.ctx_logger(name=name, object_name=getattr(obj, "name", "?"), prefix=prefix),
            operator=self.operator,
        )

    def to_export(self, matrix: mathutils.Matrix) -> mathutils.Matrix:
        """Convert a matrix from Blender space to I3D export space."""
        return self.conversion_matrix @ matrix @ self.conversion_matrix_inv

    def to_export_forward(self, matrix: mathutils.Matrix) -> mathutils.Matrix:
        """Convert a direction/forward matrix from Blender space to I3D export space."""
        return self.conversion_matrix @ matrix
