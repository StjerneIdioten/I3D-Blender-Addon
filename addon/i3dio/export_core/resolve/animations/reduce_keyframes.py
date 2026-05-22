from __future__ import annotations

from dataclasses import dataclass
from math import acos, degrees
from typing import TYPE_CHECKING

import mathutils

if TYPE_CHECKING:
    from ...ctx import ExportContext
    from ...ir import KeyframeSample


@dataclass(slots=True)
class _TRSKey:
    time_ms: float
    t: mathutils.Vector
    q: mathutils.Quaternion
    s: mathutils.Vector
    is_negative: bool


def _quat_angle_deg(a: mathutils.Quaternion, b: mathutils.Quaternion) -> float:
    # Quaternion sign is ambiguous; abs(dot) makes comparison invariant.
    d = abs(a.dot(b))
    if d > 1.0:
        d = 1.0
    return degrees(2.0 * acos(d))


def reduce_keyframe_samples_in_place(ctx: ExportContext, samples: list[KeyframeSample]) -> None:
    """
    Reduce baked per-frame samples.

    Removes samples that are redundant under *linear interpolation* (translation/scale)
    and *slerp* (rotation), within tolerances.

    Always keeps first and last sample.
    """
    if len(samples) <= 2:
        return

    # Sensible defaults; expose as settings if you want.
    pos_eps = 1e-5
    rot_eps = 0.05
    scl_eps = 1e-5

    # Precompute TRS once
    keys: list[_TRSKey] = []
    us = float(ctx.unit_scale)
    for s in samples:
        t, q, sc = s.matrix_local_export.decompose()
        keys.append(
            _TRSKey(
                time_ms=float(s.time_ms),
                t=mathutils.Vector((t.x * us, t.y * us, t.z * us)),
                q=q.copy(),
                s=sc.copy(),
                is_negative=bool(s.matrix_local_export.is_negative),
            )
        )

    def redundant(k0: _TRSKey, k1: _TRSKey, k2: _TRSKey) -> bool:
        # Don’t try to be clever if negative scale is involved (you skip scale emission anyway).
        if k0.is_negative or k1.is_negative or k2.is_negative:
            return False

        dt = k2.time_ms - k0.time_ms
        if dt <= 0.0:
            return False
        alpha = (k1.time_ms - k0.time_ms) / dt

        # Translation/scale: linear
        t_interp = k0.t.lerp(k2.t, alpha)
        s_interp = k0.s.lerp(k2.s, alpha)

        # Rotation: slerp (stable, representation-independent)
        q_interp = k0.q.slerp(k2.q, alpha)

        pos_err = (k1.t - t_interp).length
        scl_err = (k1.s - s_interp).length
        rot_err = _quat_angle_deg(k1.q, q_interp)

        return (pos_err <= pos_eps) and (scl_err <= scl_eps) and (rot_err <= rot_eps)

    kept_idx: list[int] = [0]
    for i in range(1, len(keys) - 1):
        prev_i = kept_idx[-1]
        if redundant(keys[prev_i], keys[i], keys[i + 1]):
            continue
        kept_idx.append(i)
    kept_idx.append(len(keys) - 1)

    if len(kept_idx) == len(samples):
        return  # nothing to do

    samples[:] = [samples[i] for i in kept_idx]
