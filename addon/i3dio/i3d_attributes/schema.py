from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, TypeVar

import bpy

PropertyGroupT = TypeVar("PropertyGroupT", bound=bpy.types.PropertyGroup)
Converter = Callable[[object], object]
AttributeName = str | Callable[[object], str]


@dataclass(frozen=True, slots=True)
class TrackingDefinition:
    """Resolve a property from its owning Blender datablock while tracking is enabled."""

    member_path: str
    toggle: Any
    mapping: Mapping[object, object] | None = None


@dataclass(frozen=True, slots=True)
class ExportDefinition:
    """Map a property to an attribute in a caller-supplied destination.

    i3d_default is compared before conversion, in the effective property's units.
    A target label is not an instruction to create an XML child element.
    """

    i3d_name: AttributeName
    i3d_default: object
    target: str = "Node"
    converter: Converter | None = None

    def resolve_name(self, value: object) -> str:
        name = self.i3d_name(value) if callable(self.i3d_name) else self.i3d_name
        if not isinstance(name, str):
            raise TypeError(f"Resolved I3D name must be a string, got {type(name).__name__}")
        if not name:
            raise ValueError("Resolved I3D name must not be empty")
        return name


@dataclass(frozen=True, slots=True)
class PropertyDefinition:
    """A Blender RNA property with optional I3D export metadata."""

    rna: Any
    export: ExportDefinition | None = None
    dependencies: tuple[tuple[str, object], ...] = ()
    tracking: TrackingDefinition | None = None


class I3DSchema(Mapping[str, PropertyDefinition]):
    """An immutable, validated collection of I3D property definitions."""

    def __init__(self, **definitions: PropertyDefinition) -> None:
        self._definitions = MappingProxyType(definitions)
        self._validate()

    def __getitem__(self, name: str) -> PropertyDefinition:
        return self._definitions[name]

    def __iter__(self) -> Iterator[str]:
        return iter(self._definitions)

    def __len__(self) -> int:
        return len(self._definitions)

    def exported(self) -> Iterator[tuple[str, PropertyDefinition]]:
        return ((name, definition) for name, definition in self._definitions.items() if definition.export is not None)

    def _rna_annotations(self) -> Iterator[tuple[str, Any]]:
        for name, definition in self._definitions.items():
            yield name, definition.rna
            if definition.tracking is not None:
                yield f"{name}_tracking", definition.tracking.toggle

    def install(self, cls: type[PropertyGroupT]) -> type[PropertyGroupT]:
        if "i3d_schema" in cls.__dict__ and cls.__dict__["i3d_schema"] is not self:
            raise TypeError(f"{cls.__name__}.i3d_schema already references a different schema")

        annotations = dict(cls.__dict__.get("__annotations__", {}))
        schema_annotations = dict(self._rna_annotations())
        if duplicates := annotations.keys() & schema_annotations.keys():
            raise TypeError(f"{cls.__name__} already defines properties: {', '.join(sorted(duplicates))}")

        annotations.update(schema_annotations)
        cls.__annotations__ = annotations
        cls.i3d_schema = self
        return cls

    def _validate(self) -> None:
        for name, definition in self._definitions.items():
            if not isinstance(definition, PropertyDefinition):
                raise TypeError(f"{name!r} must be a PropertyDefinition, got {type(definition).__name__}")

            tracking_name = f"{name}_tracking"
            if definition.tracking is not None and tracking_name in self._definitions:
                raise ValueError(f"{name!r} tracking toggle conflicts with schema property {tracking_name!r}")

            export = definition.export
            if export is not None:
                if not isinstance(export.i3d_name, str) and not callable(export.i3d_name):
                    raise TypeError(f"{name!r} has an I3D name that is neither a string nor callable")
                if isinstance(export.i3d_name, str) and not export.i3d_name:
                    raise ValueError(f"{name!r} has an empty I3D name")
                if not isinstance(export.target, str):
                    raise TypeError(f"{name!r} has a non-string I3D target")
                if not export.target:
                    raise ValueError(f"{name!r} has an empty I3D target")

            for dependency, _expected in definition.dependencies:
                if dependency not in self._definitions:
                    raise ValueError(f"{name!r} depends on unknown property {dependency!r}")


def exported(
    rna: Any,
    *,
    i3d_name: AttributeName,
    i3d_default: object,
    target: str = "Node",
    converter: Converter | None = None,
    dependencies: Mapping[str, object] | None = None,
    tracking: TrackingDefinition | None = None,
) -> PropertyDefinition:
    return PropertyDefinition(
        rna=rna,
        export=ExportDefinition(i3d_name=i3d_name, i3d_default=i3d_default, target=target, converter=converter),
        dependencies=tuple(dependencies.items()) if dependencies is not None else (),
        tracking=tracking,
    )


def stored(rna: Any, *, tracking: TrackingDefinition | None = None) -> PropertyDefinition:
    """Define an RNA property that is not directly exported."""
    return PropertyDefinition(rna=rna, tracking=tracking)


def parse_hex_u32(value: object) -> int:
    if not isinstance(value, str):
        raise TypeError(f"Expected a hexadecimal string, got {type(value).__name__}")

    try:
        converted = int(value, 16)
    except ValueError as error:
        raise ValueError(f"{value!r} is not a valid hexadecimal value") from error

    if not 0 <= converted <= 0xFFFFFFFF:
        raise ValueError(f"{value!r} is outside the unsigned 32-bit range")

    return converted
