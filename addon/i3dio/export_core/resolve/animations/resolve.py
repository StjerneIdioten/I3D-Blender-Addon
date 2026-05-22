from __future__ import annotations

import contextlib
from dataclasses import dataclass
from typing import TYPE_CHECKING

import bpy
from bpy_extras import anim_utils

from ...ir import AnimationSetIR, ClipIR, KeyframeSample, KeyframesTrack, SourceKind
from .reduce_keyframes import reduce_keyframe_samples_in_place
from .sampling import compute_local_matrices_for_current_frame

if TYPE_CHECKING:
    from ...ctx import ExportContext


@contextlib.contextmanager
def _restore_frame(scene: bpy.types.Scene):
    """Context manager to restore the scene frame after sampling."""
    frame = scene.frame_current
    try:
        yield
    finally:
        with contextlib.suppress(Exception):
            scene.frame_set(frame)


@contextlib.contextmanager
def _temporary_unhide_objects(objs: set[bpy.types.Object]):
    """Temporarily unhides objects so frame changes update evaluation (important for baking)."""
    original_hide_state = {obj: obj.hide_viewport for obj in objs}
    try:
        for obj in objs:
            obj.hide_viewport = False
        yield
    finally:
        for obj, state in original_hide_state.items():
            with contextlib.suppress(Exception):
                obj.hide_viewport = state


@dataclass(frozen=True, slots=True)
class _NodeSlot:
    node_id: int
    obj: bpy.types.Object
    slot: object


def _get_slot_for_object(action: bpy.types.Action, obj: bpy.types.Object):
    """Best-effort slot lookup for obj under action.

    Prefer the slot Blender assigned on the animation_data (most reliable),
    then fall back to anim_utils helpers if present, then to heuristics.
    """
    ad = obj.animation_data
    if ad is not None and ad.action_slot is not None:
        return ad.action_slot

    if not (slots := action.slots):
        return None
    # Assume single slot belongs to this object
    if len(slots) == 1:
        return slots[0]

    # Try matching by slot name (often equals ID name)
    return next((s for s in slots if s.name == obj.name), None)


def _iter_action_to_node_slots(ctx: ExportContext) -> dict[bpy.types.Action, list[_NodeSlot]]:
    """Return mapping action -> node slots for exported object nodes.

    Uses each exported object's animation_data.action assignment, but preserves per-object slots.
    This enables a single Action to drive multiple objects via multiple slots.
    """
    out: dict[bpy.types.Action, list[_NodeSlot]] = {}

    # Include non-emitted object nodes (e.g. collapsed armature objects) because
    # their bones can still be emitted and should receive animation.
    for node in ctx.ir.iter_nodes(emitted_only=False, source_kind=SourceKind.OBJECT):
        obj = node.obj
        ad = obj.animation_data
        if ad is None or ad.action is None:
            continue
        action = ad.action

        slot = _get_slot_for_object(action, obj)
        if slot is None:
            ctx.node_reporter(node, "animations").warning(
                "Object has action %r but no action slot could be resolved; skipping", action.name
            )
            continue

        out.setdefault(action, []).append(_NodeSlot(node_id=node.id, obj=obj, slot=slot))

    return out


def _bone_names_in_channelbag(channelbag: bpy.types.ActionChannelbag) -> set[str]:
    """Extract bone names referenced by pose bone FCurves in a channelbag."""
    out: set[str] = set()
    key = 'pose.bones["'
    end = '"]'
    for fc in channelbag.fcurves:
        dp = fc.data_path or ""
        # Typical pattern: pose.bones["BoneName"].location / rotation / etc
        i = dp.find(key)
        if i == -1:
            continue
        rest = dp[i + len(key) :]
        bone_name = rest.split(end, 1)[0]
        if bone_name:
            out.add(bone_name)
    return out


def resolve_animations(ctx: ExportContext) -> None:
    """Collect and bake animations into ctx.ir.animations.

    Current scope (intentionally conservative):
    - Uses each exported object's active action (obj.animation_data.action).
    - Bakes per-frame matrices (frame_range) into keyframes.
    - For armatures: exports keyframes for bones (not the armature object node itself).
    """

    rep = ctx.reporter("animations")

    if not ctx.has_feature("ANIMATIONS"):
        rep.debug("Feature ANIMATIONS disabled; skipping")
        return

    scene = ctx.scene
    fps = scene.render.fps / scene.render.fps_base

    action_to_node_slots = _iter_action_to_node_slots(ctx)
    if not action_to_node_slots:
        rep.debug("No exported objects with active actions; skipping")
        return

    ms_per_frame = 1000.0 / fps

    affected_objects = {ns.obj for node_slots in action_to_node_slots.values() for ns in node_slots}

    with _restore_frame(scene), _temporary_unhide_objects(affected_objects):
        for action, node_slots in action_to_node_slots.items():
            if not action.layers:
                rep.debug("Action %r has no layers; skipping", action.name)
                continue
            start_frame, end_frame = map(int, action.frame_range)
            if end_frame < start_frame:
                continue

            duration_ms = (end_frame - start_frame) * ms_per_frame
            anim_set = AnimationSetIR(name=action.name)

            for layer in action.layers:
                # Still not entirly sure how layers will work in the future, but currently not exposed in UI.
                # So use action name and when ever multiple layers can exist use layer name
                clip_name = action.name if len(action.layers) == 1 else layer.name

                # Build target tracks for this (action, layer)
                target_node_ids: set[int] = set()

                for ns in node_slots:
                    node = ctx.ir.scene_nodes[ns.node_id]

                    channelbag = anim_utils.action_get_channelbag_for_slot(action, ns.slot)
                    if channelbag is None or not channelbag.fcurves:
                        continue

                    # Armatures export bones, objects export themselves.
                    if node.source_object_type == 'ARMATURE':
                        bone_map = ctx.ir.index.bone_nodes_by_armature_ptr.get(node.source_ptr, {})
                        for bone_name in _bone_names_in_channelbag(channelbag):
                            if (bone_nid := bone_map.get(bone_name)) is not None:
                                target_node_ids.add(bone_nid)
                    else:
                        target_node_ids.add(node.id)

                ordered_nids = [nid for nid in ctx.ir.node_order if nid in target_node_ids]
                if not ordered_nids:
                    continue

                rep.debug(
                    "Baking action %r clip %r (%d-%d) for %d nodes",
                    action.name,
                    clip_name,
                    start_frame,
                    end_frame,
                    len(ordered_nids),
                )

                pairs = [(nid, KeyframesTrack(node_id=nid)) for nid in ordered_nids]
                clip = ClipIR(name=clip_name, duration_ms=duration_ms)

                for i, frame in enumerate(range(start_frame, end_frame + 1)):
                    scene.frame_set(frame)
                    matrices = compute_local_matrices_for_current_frame(ctx)
                    time_ms = i * ms_per_frame

                    for nid, track in pairs:
                        if (m := matrices.get(nid)) is not None:
                            track.samples.append(KeyframeSample(time_ms=time_ms, matrix_local_export=m.copy()))

                total_before = sum(len(t.samples) for _, t in pairs)
                for _, track in pairs:
                    reduce_keyframe_samples_in_place(ctx, track.samples)
                total_after = sum(len(t.samples) for _, t in pairs)

                removed = total_before - total_after
                if removed:
                    rep.debug(
                        "Reduced clip %r: removed %d samples (before %d, after %d)",
                        clip_name,
                        removed,
                        total_before,
                        total_after,
                    )

                clip.tracks.extend(track for _, track in pairs)
                anim_set.clips.append(clip)

            if anim_set.clips:
                ctx.ir.animations.sets.append(anim_set)

    rep.info("Resolved %d animation sets", len(ctx.ir.animations.sets))
