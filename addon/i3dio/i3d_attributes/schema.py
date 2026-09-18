"""Define Blender properties, their I3D export settings, and their requirements.

Use a plain class to name each property, declaring prerequisites first::

    class ExampleProperties:
        enabled = stored(BoolProperty(default=False))
        count = exported(
            EnumProperty(items=[('1', '1', ''), ('4', '4', '')]),
            i3d_name='count', i3d_default='1',
            requires=(enabled.equals(True),),
        )
        distance = exported(
            FloatProperty(default=80), i3d_name='distance', i3d_default=80,
            requires=(count.equals('4'),),
        )

    @I3DSchema.from_definitions(ExampleProperties).install
    class ExampleAttributes(bpy.types.PropertyGroup):
        pass

The schema keeps declaration order for registration and export. Each entry in
requires must pass; one_of accepts any of its listed values. Comparisons use
Python equality, so enum identifiers remain strings (for example, '4', not 4).
Comparison values must be built-in bool, int, float, str, or None; lists and
vectors are not supported. Requirement objects validate these rules when created.
The schema checks that references belong to it and do not form cycles.

Requirements use the stored value, or the tracked Blender value after any tracking
mapping, before export conversion. The referenced property's own requirements must
also pass. In the example, distance requires both count == '4' and enabled == True.
A prerequisite can still satisfy a requirement when it is stored-only or omitted
from export because it matches its default. Unmet requirements disable UI controls
and omit exported attributes while preserving stored values.

Write property descriptions about what each property does. Installation appends
a Requires section listing direct and transitive conditions with readable labels.
This text describes all conditions, regardless of their current values.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass
from graphlib import TopologicalSorter
from types import MappingProxyType
from typing import Any, Literal, TypeVar

import bpy

PropertyGroupT = TypeVar("PropertyGroupT", bound=bpy.types.PropertyGroup)
Converter = Callable[[object], object]
AttributeName = str | Callable[[object], str]
RequirementValue = bool | int | float | str | None


@dataclass(frozen=True, slots=True)
class TrackingDefinition:
    """Use a Blender datablock's property instead of the stored I3D value.

    member_path names an attribute on the owner passed to the value reader.
    toggle defines the <property_name>_tracking switch. An optional mapping
    translates the Blender value into the value used by the schema.
    """

    member_path: str
    toggle: Any
    mapping: Mapping[object, object] | None = None


@dataclass(frozen=True, slots=True)
class ExportDefinition:
    """Describe how a property becomes an I3D attribute.

    Values matching i3d_default are omitted before converter runs. Both the default
    and any i3d_name callback use the stored or tracked value in its original units.
    target identifies the destination element supplied by the exporter.
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
class Requirement:
    """An immutable comparison against a referenced property's value.

    Create requirements with PropertyDefinition.equals, not_equals, or one_of.
    The shared evaluator checks the referenced property's own requirements first.
    """

    source: PropertyDefinition
    comparison: Literal["equals", "not_equals", "one_of"]
    values: tuple[RequirementValue, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", tuple(self.values))
        if not isinstance(self.source, PropertyDefinition):
            raise TypeError("Requirement source must be a PropertyDefinition")
        if self.comparison not in ("equals", "not_equals", "one_of"):
            raise ValueError(f"Unknown requirement comparison: {self.comparison!r}")
        if not self.values:
            raise ValueError(f"Requirement {self.comparison!r} needs at least one value")
        if self.comparison != "one_of" and len(self.values) != 1:
            raise ValueError(f"Requirement {self.comparison!r} needs exactly one value")
        for value in self.values:
            if type(value) not in (bool, int, float, str, type(None)):
                raise TypeError(
                    f"Requirement values must be bool, int, float, str, or None, got {type(value).__name__}"
                )

    def matches(self, value: object) -> bool:
        """Compare a supplied value; prerequisite checks belong to requirements_met."""
        if self.comparison == "equals":
            return value == self.values[0]
        if self.comparison == "not_equals":
            return value != self.values[0]
        if self.comparison == "one_of":
            return value in self.values
        raise ValueError(f"Unknown requirement comparison: {self.comparison!r}")


@dataclass(frozen=True, slots=True, eq=False)
class PropertyDefinition:
    """A Blender RNA property with optional I3D export metadata.

    Definitions compare and hash by identity, so each declaration is a distinct
    schema member even when its metadata matches another declaration.
    """

    rna: Any
    export: ExportDefinition | None = None
    requires: tuple[Requirement, ...] = ()
    tracking: TrackingDefinition | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "requires", tuple(self.requires))

    def equals(self, value: RequirementValue) -> Requirement:
        return Requirement(self, "equals", (value,))

    def not_equals(self, value: RequirementValue) -> Requirement:
        return Requirement(self, "not_equals", (value,))

    def one_of(self, *values: RequirementValue) -> Requirement:
        return Requirement(self, "one_of", values)


class I3DSchema(Mapping[str, PropertyDefinition]):
    """Keep named property definitions in declaration order and validate their links.

    Each definition must have exactly one name in the schema. Requirements must
    reference definitions in the same schema, and cycles raise graphlib.CycleError.
    """

    def __init__(self, **definitions: PropertyDefinition) -> None:
        self._definitions = MappingProxyType(definitions)
        self._names_by_definition: dict[PropertyDefinition, str] = {}
        self._validate()

    @classmethod
    def from_definitions(cls, definitions: type) -> I3DSchema:
        """Collect public definitions from a plain class, in declaration order.

        Declare prerequisites first so later definitions can reference them.
        Private attributes are ignored; inheritance and public helpers are rejected.
        The declaration class is not a Blender PropertyGroup.
        """
        if not isinstance(definitions, type):
            raise TypeError("Schema definitions must be a plain class")
        if definitions.__bases__ != (object,):
            raise TypeError("Schema definition classes must not use inheritance")
        return cls(**{name: value for name, value in vars(definitions).items() if not name.startswith("_")})

    def name_of(self, definition: PropertyDefinition) -> str:
        """Return the name bound to this exact definition."""
        try:
            return self._names_by_definition[definition]
        except KeyError:
            raise ValueError("Property definition does not belong to this schema") from None

    def __getitem__(self, name: str) -> PropertyDefinition:
        return self._definitions[name]

    def __iter__(self) -> Iterator[str]:
        return iter(self._definitions)

    def __len__(self) -> int:
        return len(self._definitions)

    def exported(self) -> Iterator[tuple[str, PropertyDefinition]]:
        """Yield definitions with export settings in declaration order, without reading values."""
        return ((name, definition) for name, definition in self._definitions.items() if definition.export is not None)

    def _rna_annotations(self) -> Iterator[tuple[str, Any]]:
        for name, definition in self._definitions.items():
            rna = definition.rna
            if definition.requires:
                requirements = self._requirements_description(name)
                description = rna.keywords.get("description", "")
                description = f"{description}\n\n{requirements}" if description else requirements
                # Copy the RNA property so reusing the definition does not append the text again.
                rna = rna.function(**dict(rna.keywords, description=description))
            yield name, rna
            if definition.tracking is not None:
                yield f"{name}_tracking", definition.tracking.toggle

    def _requirements_description(self, name: str) -> str:
        """Build tooltip text with prerequisites first and each distinct condition once."""
        visited: set[str] = set()
        seen: set[Requirement] = set()
        lines = ["Requires:"]

        def visit(source: str) -> None:
            if source in visited:
                return
            visited.add(source)
            for requirement in self[source].requires:
                prerequisite = self.name_of(requirement.source)
                visit(prerequisite)
                if requirement not in seen:
                    seen.add(requirement)
                    lines.append(self._requirement_description(requirement))

        visit(name)
        return "\n".join(lines)

    def _requirement_description(self, requirement: Requirement) -> str:
        keywords = requirement.source.rna.keywords
        label = keywords.get("name") or self.name_of(requirement.source).replace("_", " ").title()
        items = keywords.get("items", ())

        def value_label(value: object) -> str:
            if isinstance(value, bool):
                return "Enabled" if value else "Disabled"
            # Dynamic enum callbacks require context and must not run at installation.
            if isinstance(items, (list, tuple)):
                for item in items:
                    if item and item[0] == value and item[1]:
                        return item[1]
            return str(value)

        values = ", ".join(value_label(value) for value in requirement.values)
        if requirement.comparison == "not_equals":
            values = f"not {values}"
        elif requirement.comparison == "one_of":
            values = f"one of {values}"
        return f"{label}: {values}"

    def install(self, cls: type[PropertyGroupT]) -> type[PropertyGroupT]:
        """Add RNA properties, tracking toggles, and i3d_schema to a PropertyGroup class.

        Use as a decorator before registering the class with Blender. Existing
        property annotations are preserved; conflicting names are rejected.
        """
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

            if definition in self._names_by_definition:
                previous = self._names_by_definition[definition]
                raise ValueError(f"Property definition is registered under multiple names: {previous!r}, {name!r}")
            self._names_by_definition[definition] = name

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

        for name, definition in self._definitions.items():
            for requirement in definition.requires:
                if not isinstance(requirement, Requirement):
                    raise TypeError(f"{name!r} requires a Requirement, got {type(requirement).__name__}")
                if requirement.source not in self._names_by_definition:
                    raise ValueError(f"{name!r} requires a property definition outside this schema")

        TopologicalSorter(
            {
                name: [self.name_of(requirement.source) for requirement in definition.requires]
                for name, definition in self._definitions.items()
            }
        ).prepare()


def exported(
    rna: Any,
    *,
    i3d_name: AttributeName,
    i3d_default: object,
    target: str = "Node",
    converter: Converter | None = None,
    requires: Iterable[Requirement] = (),
    tracking: TrackingDefinition | None = None,
) -> PropertyDefinition:
    """Define a Blender property that can be written as an I3D attribute.

    All requirements must pass, and values matching i3d_default are omitted.
    Tracking selects the value source; converter runs only when preparing export.
    """
    return PropertyDefinition(
        rna=rna,
        export=ExportDefinition(i3d_name=i3d_name, i3d_default=i3d_default, target=target, converter=converter),
        requires=tuple(requires),
        tracking=tracking,
    )


def stored(
    rna: Any, *, requires: Iterable[Requirement] = (), tracking: TrackingDefinition | None = None
) -> PropertyDefinition:
    """Define a Blender property for UI or exporter logic, without an I3D attribute.

    Stored-only properties can be prerequisites for other properties.
    """
    return PropertyDefinition(rna=rna, requires=tuple(requires), tracking=tracking)


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
