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
from .resources.files import FileTable
from .resources.materials import MaterialTable
from .resources.shapes import ShapeTable

T = TypeVar("T")


@dataclass(slots=True)
class ExportContext:
    name: str
    is_dev: bool
    operator: Any  # Blender export operator
    filepath: Path
    depsgraph: bpy.types.Depsgraph
    scene: bpy.types.Scene
    conversion_matrix: mathutils.Matrix
    settings: Mapping[str, Any]

    features: frozenset[str] = field(init=False, repr=False)

    conversion_matrix_inv: mathutils.Matrix = field(init=False)
    builder: SceneBuilder = field(init=False)
    i3d_folder: Path = field(init=False)
    files: FileTable = field(init=False)
    shapes: ShapeTable = field(init=False)
    materials: MaterialTable = field(init=False)

    messages: ExportMessages = field(default_factory=ExportMessages)
    ids: IdAllocator = field(default_factory=IdAllocator)
    ir: ExportIR = field(default_factory=ExportIR)

    unit_scale: float = 1.0
    addon_pref: bpy.types.AddonPreferences | None = None

    def init_settings_cache(self) -> None:
        self.features = frozenset(self.settings.get("features_to_export", ()))

    def setting(self, key: str, default: T) -> T:
        """Return the setting value for key, or default if not set."""
        return self.settings.get(key, default)

    def has_feature(self, feature: str) -> bool:
        """Return True if the given feature is enabled for export."""
        return feature in self.features

    @classmethod
    def create(
        cls,
        *,
        is_dev: bool,
        operator: Any,
        filepath: str | Path,
        depsgraph: bpy.types.Depsgraph,
        scene: bpy.types.Scene,
        conversion_matrix: mathutils.Matrix,
        settings: dict,
    ) -> ExportContext:
        i3d_path = Path(filepath)
        ctx = cls(
            name=bpy.path.display_name_from_filepath(str(i3d_path)),
            is_dev=is_dev,
            operator=operator,
            filepath=i3d_path,
            depsgraph=depsgraph,
            scene=scene,
            conversion_matrix=conversion_matrix,
            settings=settings,
            unit_scale=scene.unit_settings.scale_length,
        )
        ctx.conversion_matrix_inv = conversion_matrix.inverted_safe()
        ctx.builder = SceneBuilder(ctx)

        ctx.i3d_folder = i3d_path.parent
        ctx.files = FileTable(ctx)
        ctx.shapes = ShapeTable(ctx)
        ctx.materials = MaterialTable(ctx)
        ctx.init_settings_cache()
        return ctx

    def ctx_logger(
        self,
        *,
        name: str = "export",
        object_name: str | None = None,
        node_kind: str | None = None,
        node_id: int | None = None,
        prefix: str | None = None,
    ) -> logging.LoggerAdapter:
        p = (prefix if prefix and prefix.endswith(": ") else f"{prefix}: ") if prefix else ""
        return debugging.ContextAdapter(
            self.logger(name),
            {"object_name": object_name, "node_kind": node_kind, "node_id": node_id, "prefix": p},
        )

    def node_logger(self, node: SceneNode, *, name: str = "export", prefix: str | None = None) -> logging.LoggerAdapter:
        return self.ctx_logger(
            name=name, object_name=node.name, node_kind=node.kind.name, node_id=node.id, prefix=prefix
        )

    def reporter(self, prefix: str | None = None, *, name: str = "export") -> Reporter:
        return Reporter(self, self.ctx_logger(name=name, prefix=prefix), operator=self.operator)

    def node_reporter(self, node: SceneNode, prefix: str | None = None, *, name: str = "export") -> Reporter:
        return Reporter(self, self.node_logger(node, name=name, prefix=prefix), operator=self.operator)

    def object_reporter(self, obj: bpy.types.ID, prefix: str | None = None, *, name: str = "export") -> Reporter:
        return Reporter(self, self.ctx_logger(name=name, object_name=getattr(obj, "name", "?")), self.operator)

    def logger(self, name: str = "export") -> logging.Logger:
        return debugging.get_logger(name)

    def to_export(self, m: mathutils.Matrix) -> mathutils.Matrix:
        """Convert a matrix from Blender space to export (i3d) space."""
        return self.conversion_matrix @ m @ self.conversion_matrix_inv

    def to_export_forward(self, m: mathutils.Matrix) -> mathutils.Matrix:
        """Convert a direction/forward matrix from Blender space to export (i3d) space."""
        return self.conversion_matrix @ m
