from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, TypeVar

import bpy

from .. import addon_logging
from .ids import IdAllocator
from .ir import ExportIR, SceneNode
from .ir.builder import SceneBuilder

if TYPE_CHECKING:
    import mathutils

T = TypeVar("T")


@dataclass(slots=True)
class ExportContext:
    """Shared state for a single export run.
    The context owns export-wide state, but should avoid becoming the place
    where actual export work happens. Traversal/resolve/serialize modules should
    perform the work and use this as shared state.
    """

    name: str
    filepath: Path
    depsgraph: bpy.types.Depsgraph
    scene: bpy.types.Scene
    conversion_matrix: mathutils.Matrix
    settings: Mapping[str, Any]

    ids: IdAllocator = field(default_factory=IdAllocator)
    ir: ExportIR = field(default_factory=ExportIR)

    features: frozenset[str] = field(init=False, repr=False)
    conversion_matrix_inv: mathutils.Matrix = field(init=False)
    builder: SceneBuilder = field(init=False)
    i3d_folder: Path = field(init=False)

    unit_scale: float = 1.0

    def __post_init__(self) -> None:
        self.filepath = Path(self.filepath)
        self.conversion_matrix_inv = self.conversion_matrix.inverted_safe()
        self.builder = SceneBuilder(self)
        self.i3d_folder = self.filepath.parent
        self.features = frozenset(self.settings.get("features_to_export", ()))

    @classmethod
    def create(
        cls,
        *,
        filepath: str | Path,
        depsgraph: bpy.types.Depsgraph,
        scene: bpy.types.Scene,
        conversion_matrix: mathutils.Matrix,
        settings: Mapping[str, Any],
    ) -> ExportContext:
        i3d_path = Path(filepath)

        return cls(
            name=bpy.path.display_name_from_filepath(str(i3d_path)),
            filepath=i3d_path,
            depsgraph=depsgraph,
            scene=scene,
            conversion_matrix=conversion_matrix,
            settings=settings,
            unit_scale=scene.unit_settings.scale_length,
        )

    def setting(self, key: str, default: T) -> T:
        """Return a setting value, or default if the setting is missing."""
        return self.settings.get(key, default)

    def has_feature(self, feature: str) -> bool:
        return feature in self.features

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

        return addon_logging.get_export_logger(
            name, object_name=object_name, node_kind=node_kind, node_id=node_id, prefix=prefix or ""
        )

    def node_logger(self, node: SceneNode, *, name: str = "export", prefix: str | None = None) -> logging.LoggerAdapter:
        return self.ctx_logger(
            name=name, object_name=node.name, node_kind=node.kind.value, node_id=node.id, prefix=prefix
        )

    def to_export(self, matrix: mathutils.Matrix) -> mathutils.Matrix:
        """Convert a matrix from Blender space to I3D export space."""
        return self.conversion_matrix @ matrix @ self.conversion_matrix_inv

    def to_export_forward(self, matrix: mathutils.Matrix) -> mathutils.Matrix:
        """Convert a direction/forward matrix from Blender space to I3D export space."""
        return self.conversion_matrix @ matrix
