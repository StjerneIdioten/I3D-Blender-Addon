from __future__ import annotations

import math
from typing import TYPE_CHECKING

from ...xml_i3d import SubElementA, write_attribute

if TYPE_CHECKING:
    from mathutils import Euler, Matrix

    from ..ctx import ExportContext
    from ..ir import AnimationSetIR


def _write_keyframe_transform(
    ctx: ExportContext, elem, matrix_local_export: Matrix, prev_euler: Euler | None = None
) -> Euler | None:
    """
    Write TRS for a keyframe.
    Returns the Euler used, so the caller can feed it back as prev_euler for continuity.
    """
    t, q, s = matrix_local_export.decompose()

    # Translation (apply unit scale)
    t_scaled = (t.x * ctx.unit_scale, t.y * ctx.unit_scale, t.z * ctx.unit_scale)
    write_attribute(elem, "translation", t_scaled)

    # Rotation (Euler continuity)
    # Passing prev_euler makes Blender choose the nearest equivalent Euler representation
    # to avoid 180-degree flips between frames.
    if prev_euler is not None:
        r = q.to_euler("XYZ", prev_euler)
    else:
        r = q.to_euler("XYZ")
    write_attribute(elem, "rotation", (math.degrees(r.x), math.degrees(r.y), math.degrees(r.z)))

    # Scale (skip negative scale as GIANTS Engine doesn't support it)
    if matrix_local_export.is_negative:
        return r
    write_attribute(elem, "scale", (s.x, s.y, s.z))
    return r


def _emit_animation_set(ctx: ExportContext, parent_elem, anim_set: AnimationSetIR) -> None:
    aset_elem = SubElementA(parent_elem, "AnimationSet", {"name": anim_set.name})

    for clip in anim_set.clips:
        clip_elem = SubElementA(aset_elem, "Clip", {"name": clip.name, "duration": clip.duration_ms})

        for track in clip.tracks:
            keyframes_elem = SubElementA(clip_elem, "Keyframes", {"nodeId": track.node_id})
            prev_euler: Euler | None = None
            for sample in track.samples:
                kf_elem = SubElementA(keyframes_elem, "Keyframe", {"time": sample.time_ms})
                prev_euler = _write_keyframe_transform(ctx, kf_elem, sample.matrix_local_export, prev_euler)


def emit_animation(ctx: ExportContext, animation_elem) -> None:
    """Emit AnimationSets/AnimationSet/Clip/Keyframes/Keyframe.
    Skips visibility keyframes by design (target engine behavior).
    """
    sets = getattr(ctx.ir.animations, "sets", [])
    if not sets:
        return

    sets_elem = SubElementA(animation_elem, "AnimationSets")
    for anim_set in sets:
        _emit_animation_set(ctx, sets_elem, anim_set)
