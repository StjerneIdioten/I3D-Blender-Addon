from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import cache

from .. import utility
from .schema import I3DSchema

ErrorHandler = Callable[[str, Exception], None]
ValueReader = Callable[[str], object]
AttributeValue = bool | int | float | str | tuple[int | float, ...]

# Distinguish a failed read from legitimate stored values such as None.
UNAVAILABLE = object()
_VALUE_ERRORS = (AttributeError, KeyError, TypeError, ValueError)


@dataclass(frozen=True, slots=True)
class ResolvedAttribute:
    """An export-ready value with its schema name, I3D name, and destination label."""

    source: str
    target: str
    name: str
    value: AttributeValue


def make_value_reader(
    values: object, schema: I3DSchema, *, owner: object | None = None, on_error: ErrorHandler | None = None
) -> ValueReader:
    """Create a cached value reader for one export or panel draw.

    Read stored values unless tracking is enabled, then use the owner's Blender
    property and any tracking mapping. Copy supported sequences to tuples; leave
    export conversion to resolve_attributes. Create a new reader for each draw or
    export so cached values cannot carry over to the next operation.

    With on_error, AttributeError, KeyError, TypeError, and ValueError during a read
    are reported once per property and cached as UNAVAILABLE. Without a handler,
    these errors propagate with the property name in an exception note. Unexpected
    exceptions and errors raised by on_error propagate without being cached.
    """
    if owner is None:
        owner = getattr(values, "id_data", values)

    @cache
    def read(source: str) -> object:
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
            return sequence if sequence is not None else value
        except _VALUE_ERRORS as error:
            if on_error is None:
                error.add_note(f"While reading I3D property {source!r}.")
                raise
            on_error(source, error)
            return UNAVAILABLE

    return read


def requirements_met(source: str, schema: I3DSchema, read_value: ValueReader) -> bool:
    """Return whether a property's requirements and all their prerequisites pass.

    Use read_value to compare stored or tracked values before export conversion.
    UNAVAILABLE fails every comparison, including not_equals. A prerequisite can
    pass even if it has no exported attribute or matches its export default.
    Shared prerequisites are checked once per call; stored values are never changed.
    """

    @cache
    def check(name: str) -> bool:
        for requirement in schema[name].requires:
            prerequisite = schema.name_of(requirement.source)
            if not check(prerequisite):
                return False
            value = read_value(prerequisite)
            if value is UNAVAILABLE or not requirement.matches(value):
                return False
        return True

    return check(source)


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
    """Prepare I3D attributes in schema order without changing Blender properties.

    Skip properties with unmet requirements, unavailable values, or values matching
    their export defaults. Compare defaults and resolve callable attribute names
    before conversion (for example, while angles are still in radians). Then apply
    the converter and check that the result is a supported export value.

    on_error reports handled read or conversion errors and skips affected attributes;
    without it, errors propagate. The caller writes the results to their destinations.
    """
    if schema is None:
        schema = getattr(type(values), "i3d_schema")
    read_value = make_value_reader(values, schema, owner=owner, on_error=on_error)
    resolved: list[ResolvedAttribute] = []

    for source, definition in schema.exported():
        if not requirements_met(source, schema, read_value):
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
