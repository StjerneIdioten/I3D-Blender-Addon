from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .. import utility
from .schema import I3DSchema, PropertyDefinition

ErrorHandler = Callable[[str, Exception], None]
ValueReader = Callable[[str], object]
AttributeValue = bool | int | float | str | tuple[int | float, ...]

# Distinguish a failed read from legitimate stored values such as None.
UNAVAILABLE = object()
_VALUE_ERRORS = (AttributeError, KeyError, TypeError, ValueError)


@dataclass(frozen=True, slots=True)
class ResolvedAttribute:
    """An I3D attribute ready to be written or added to the export IR."""

    source: str
    target: str
    name: str
    value: AttributeValue


def make_value_reader(
    values: object, schema: I3DSchema, *, owner: object | None = None, on_error: ErrorHandler | None = None
) -> ValueReader:
    """Read effective values lazily, once per source, for one export or panel draw.

    With an error handler, failed reads return UNAVAILABLE and are reported once.
    Without a handler, errors propagate. Export type checks happen after conversion
    in resolve_attributes.
    """
    if owner is None:
        owner = getattr(values, "id_data", values)
    cache: dict[str, object] = {}

    def read(source: str) -> object:
        if source not in cache:
            definition = schema[source]
            try:
                tracking = definition.tracking
                if tracking is not None and getattr(values, f"{source}_tracking"):
                    value = getattr(owner, tracking.member_path)
                    if tracking.mapping is not None:
                        value = tracking.mapping[value]
                else:
                    value = getattr(values, source)
                sequence = utility.as_export_tuple(value)
                cache[source] = sequence if sequence is not None else value
            except _VALUE_ERRORS as error:
                if on_error is None:
                    error.add_note(f"While reading I3D property {source!r}.")
                    raise
                cache[source] = UNAVAILABLE
                on_error(source, error)
        return cache[source]

    return read


def dependencies_met(definition: PropertyDefinition, read_value: ValueReader) -> bool:
    """Compare dependencies with effective, unconverted property values."""
    for source, expected in definition.dependencies:
        value = read_value(source)
        if value is UNAVAILABLE or value != expected:
            return False
    return True


def _attribute_value(value: object) -> AttributeValue:
    if isinstance(value, (bool, int, float, str)):
        return value
    sequence = utility.as_export_tuple(value)
    if sequence is not None and all(isinstance(item, (int, float)) for item in sequence):
        return sequence
    raise TypeError(f"Unsupported I3D attribute value: {type(value).__name__}")


def resolve_attributes(
    values: object,
    schema: I3DSchema | None = None,
    *,
    owner: object | None = None,
    on_error: ErrorHandler | None = None,
) -> tuple[ResolvedAttribute, ...]:
    """Capture ordered, detached attributes without changing the Blender source.

    Defaults and dynamic names use the property domain (e.g. radians for angles),
    before conversion into the export domain. Destinations are owned by the caller.
    """
    if schema is None:
        schema = getattr(type(values), "i3d_schema")
    read_value = make_value_reader(values, schema, owner=owner, on_error=on_error)
    resolved: list[ResolvedAttribute] = []

    for source, definition in schema.exported():
        if not dependencies_met(definition, read_value):
            continue

        if (value := read_value(source)) is UNAVAILABLE:
            continue

        export = definition.export
        try:
            if utility.isclose_value(value, export.i3d_default):
                continue
            name = export.resolve_name(value)
            if export.converter is not None:
                value = export.converter(value)
            value = _attribute_value(value)
        except _VALUE_ERRORS as error:
            if on_error is None:
                error.add_note(f"While resolving I3D property {source!r}.")
                raise

            on_error(source, error)
            continue

        resolved.append(ResolvedAttribute(source=source, target=export.target, name=name, value=value))

    return tuple(resolved)
