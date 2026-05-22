from __future__ import annotations

from dataclasses import dataclass, field

from mathutils import Matrix


@dataclass(slots=True)
class KeyframeSample:
    time_ms: float
    matrix_local_export: Matrix


@dataclass(slots=True)
class KeyframesTrack:
    node_id: int
    samples: list[KeyframeSample] = field(default_factory=list)


@dataclass(slots=True)
class ClipIR:
    name: str
    duration_ms: float
    tracks: list[KeyframesTrack] = field(default_factory=list)


@dataclass(slots=True)
class AnimationSetIR:
    name: str
    clips: list[ClipIR] = field(default_factory=list)


@dataclass(slots=True)
class AnimationIR:
    sets: list[AnimationSetIR] = field(default_factory=list)
