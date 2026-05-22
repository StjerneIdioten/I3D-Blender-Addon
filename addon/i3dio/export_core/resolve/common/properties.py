from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import bpy

from .... import utility
from ...ir import EmitAttrs, NodeKind, SceneNode, set_kind

if TYPE_CHECKING:
    from ...ctx import ExportContext
    from ...resources.materials import MaterialEntry


@dataclass(frozen=True, slots=True)
class TrackingSpec:
    member_path: str
    value_gate: Any | None
    value_gate_set: bool  # must preserve '"value" in tracking' semantics
    mapping: dict[Any, Any] | None


@dataclass(frozen=True, slots=True)
class DependsSpec:
    name: str
    value: Any


@dataclass(frozen=True, slots=True)
class PropSpec:
    key: str
    placement: str  # "Node" or child tag name or "IndexedTriangleSet", etc.
    name: str | None
    default: Any
    field_type: str | None
    override: Any | None
    depends: tuple[DependsSpec, ...]
    tracking: TrackingSpec | None


@dataclass(frozen=True, slots=True)
class SpecBundle:
    export: tuple[PropSpec, ...]  # only props with placement != None
    tracking_by_key: dict[str, TrackingSpec | None]  # all props (incl UI-only)


_BUNDLE_CACHE: dict[type, SpecBundle] = {}
_SKIP = object()


# Compilation
def _compile_bundle(pg: Any) -> SpecBundle:
    cls = type(pg)
    if (cached := _BUNDLE_CACHE.get(cls)) is not None:
        return cached
    i3d_map: dict[str, dict[str, Any]] = getattr(pg, "i3d_map", {})
    annotations: dict[str, Any] = getattr(pg, "__annotations__", {})

    def _parse_depends(info: dict[str, Any]) -> tuple[DependsSpec, ...]:
        return tuple(DependsSpec(d["name"], d["value"]) for d in info.get("depends", []) or [])

    def _parse_tracking(info: dict[str, Any]) -> TrackingSpec | None:
        if not (tr := info.get("tracking")):
            return None
        return TrackingSpec(
            member_path=tr["member_path"],
            value_gate=tr.get("value"),
            value_gate_set="value" in tr,
            mapping=tr.get("mapping"),
        )

    tracking_by_key: dict[str, TrackingSpec | None] = {}
    export_specs: list[PropSpec] = []

    # iterate annotations to ensure only declared properties
    for key in annotations.keys():
        if not (info := i3d_map.get(key)):
            continue
        placement = info.get("placement", "Node")
        tr = _parse_tracking(info)
        tracking_by_key[key] = tr
        if placement is None:
            continue  # UI-only

        export_specs.append(
            PropSpec(
                key=key,
                placement=placement,
                name=info.get("name"),
                default=info.get("default"),
                field_type=info.get("type"),
                override=info.get("override"),
                depends=_parse_depends(info),
                tracking=tr,
            )
        )
    bundle = SpecBundle(export=tuple(export_specs), tracking_by_key=tracking_by_key)
    _BUNDLE_CACHE[cls] = bundle
    return bundle


# Public API (two entry points)
def resolve_properties(ctx: "ExportContext", node: SceneNode) -> None:
    ref = node.blender_ref
    if not isinstance(ref, bpy.types.Object):
        return
    if (pg := getattr(ref, "i3d_attributes", None)) is not None:
        _collect_pg(ref, pg, node.attrs)

    data = getattr(ref, "data", None)
    if data is not None and node.kind in {NodeKind.SHAPE, NodeKind.LIGHT}:
        if (pg := getattr(data, "i3d_attributes", None)) is not None:
            _collect_pg(data, pg, node.attrs, ctx=ctx, scene_node=node)
    _resolve_reference_path(ctx, node)

    if node.kind == NodeKind.CAMERA and isinstance(data, bpy.types.Camera):
        _collect_camera_builtin(data, node.attrs.node)


def resolve_material_properties(ctx: "ExportContext", entry: "MaterialEntry") -> None:
    mat = entry.blender_material
    if not isinstance(mat, bpy.types.Material):
        return
    if (pg := getattr(mat, "i3d_attributes", None)) is not None:
        _collect_pg(mat, pg, entry.attrs)


# Builtins / special cases
def _collect_camera_builtin(cam: bpy.types.Camera, out: dict[str, Any]) -> None:
    out.setdefault("fov", cam.lens)
    out.setdefault("nearClip", cam.clip_start)
    out.setdefault("farClip", cam.clip_end)
    if cam.type == "ORTHO":
        out.setdefault("orthographic", True)
        out.setdefault("orthographicHeight", cam.ortho_scale)


def _resolve_reference_path(ctx: "ExportContext", node: SceneNode) -> None:
    # Only TransformGroups should carry reference info
    if node.source_object_type != "EMPTY":
        return
    obj = node.obj
    if not (reference_path := obj.i3d_reference.path):
        return  # no reference set

    if not reference_path.lower().endswith(".i3d"):
        ctx.node_reporter(node, "properties").warning("Reference path does not end with '.i3d': %r", reference_path)
        return
    set_kind(node, NodeKind.REFERENCE_NODE)
    node.ref.reference_id = ctx.files.add_reference(reference_path)
    if not obj.i3d_reference.runtime_loaded:
        node.ref.runtime_loaded = False  # default is True, only write when False

    if child_path := obj.i3d_reference.child_path.strip():
        node.ref.child_path = child_path


# Collection / routing
def _collect_pg(
    owner: Any,
    pg: Any,
    out: EmitAttrs,
    *,
    ctx: "ExportContext" | None = None,
    scene_node: "SceneNode" | None = None,
) -> None:
    bundle = _compile_bundle(pg)

    # Pre-compute the optional "shape definition sink" once
    shape_sink: dict[str, Any] | None = None
    if (
        ctx is not None
        and scene_node is not None
        and scene_node.kind is NodeKind.SHAPE
        and "IndexedTriangleSet" in {spec.placement for spec in bundle.export}
        and (sid := scene_node.shape.shape_id) is not None
    ):
        shape_sink = ctx.shapes.get_entry(sid).attrs.node

    for spec in bundle.export:
        if not _deps_ok(owner, pg, spec, bundle):
            continue

        val = _effective_value_key(owner=owner, pg=pg, key=spec.key, tr=spec.tracking)
        if val is _SKIP:
            continue

        if utility.isclose_value(val, spec.default):
            continue

        i3d_name, value_to_write = _convert_for_export(val, spec)
        if value_to_write is _SKIP:
            continue

        _write_prop(out, spec, i3d_name, value_to_write, shape_sink)


def _write_prop(out: EmitAttrs, spec: PropSpec, name: str, value: Any, shape_sink: dict[str, Any] | None) -> None:
    placement = spec.placement
    if placement == "Node":
        out.node[name] = value
        return
    if placement == "IndexedTriangleSet" and shape_sink is not None:
        shape_sink[name] = value
        return
    # Default: treat placement as a child tag under the current node/element
    out.child(placement)[name] = value


# Depends / effective values
def _deps_ok(owner: Any, pg: Any, spec: PropSpec, bundle: SpecBundle) -> bool:
    for dep in spec.depends:
        dep_val = _effective_value_key(owner=owner, pg=pg, key=dep.name, tr=bundle.tracking_by_key.get(dep.name))
        if dep_val is _SKIP or dep_val != dep.value:
            return False
    return True


def _effective_value_key(*, owner: Any, pg: Any, key: str, tr: TrackingSpec | None) -> Any:
    """
    Unified value resolution used for:
    - normal property export (PropSpec.key + PropSpec.tracking)
    - dependency checks by name (DependsSpec.name + bundle.tracking_by_key)

    Preserves semantics:
    - missing pg prop -> _SKIP
    - tracking enabled flag: f"{key}_tracking"
    - 'value' gate checked by presence (value_gate_set), not by None-ness
    """
    val = getattr(pg, key, _SKIP)
    if val is _SKIP:
        return _SKIP
    if not tr or not bool(getattr(pg, f"{key}_tracking", False)):
        return val
    raw = getattr(owner, tr.member_path, None)
    if tr.value_gate_set and raw != tr.value_gate:
        return _SKIP

    return tr.mapping.get(raw, raw) if tr.mapping else raw


# Export conversions (as minimal as possible, serializer will handle rest)
def _convert_for_export(val: Any, spec: PropSpec) -> tuple[str, Any]:
    # name=None => "enum-name-is-value" special case
    i3d_name = spec.name
    value_to_write: Any = val

    if i3d_name is None:
        i3d_name = str(val)
        value_to_write = 1

    ft = spec.field_type
    if ft == "HEX":
        s = _hex_to_prefixed_str(val)
        if s is None:
            return i3d_name, _SKIP
        value_to_write = s
    elif ft == "OVERRIDE":
        value_to_write = spec.override
    elif ft == "ANGLE":
        value_to_write = math.degrees(float(val))

    return i3d_name, value_to_write


def _hex_to_prefixed_str(val: object) -> str | None:
    """
    Accepts:
      - "ff", "0xff", "FF", "10004"
      - 255
    Returns:
      - "0xff", "0x10004" (lowercase, no leading zeros)
    """
    if isinstance(val, int):
        n = val
    else:
        s = str(val).strip().lower()
        if not s:
            return None
        if s.startswith("0x"):
            s = s[2:]
        try:
            n = int(s, 16)
        except ValueError:
            return None

    # Bound check
    if not (0 <= n <= 2**32 - 1):
        return None

    return f"0x{n:x}"
