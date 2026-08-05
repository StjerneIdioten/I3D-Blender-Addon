from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import Enum, auto
from itertools import count


class IdKind(Enum):
    NODE = auto()
    SHAPE = auto()
    MATERIAL = auto()
    FILE = auto()


@dataclass(slots=True)
class IdAllocator:
    """Allocates stable 1-based IDs per exported I3D resource kind."""

    start: int = 1
    _iters: dict[IdKind, Iterator[int]] = field(init=False)

    def __post_init__(self) -> None:
        self._iters = {k: count(self.start) for k in IdKind}

    def alloc(self, kind: IdKind) -> int:
        """Allocate a new ID for the given resource kind."""
        return next(self._iters[kind])
