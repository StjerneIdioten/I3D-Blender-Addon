from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


class Severity(Enum):
    WARNING = auto()
    ERROR = auto()


@dataclass(slots=True)
class ExportMessage:
    severity: Severity
    text: str
    object_name: str | None = None
    code: str | None = None  # optional stable identifier


@dataclass(slots=True)
class ExportMessages:
    items: list[ExportMessage] = field(default_factory=list)
    _dedupe: set[tuple[Severity, str, str | None]] = field(default_factory=set)

    def add(
        self,
        severity: Severity,
        text: str,
        *,
        object_name: str | None = None,
        dedupe: bool = True,
        code: str | None = None,
    ):
        key = (severity, text, object_name)
        if dedupe and key in self._dedupe:
            return
        if dedupe:
            self._dedupe.add(key)
        self.items.append(ExportMessage(severity, text, object_name, code))

    def warning(self, text: str, *, object_name: str | None = None, **kw):
        self.add(Severity.WARNING, text, object_name=object_name, **kw)

    def error(self, text: str, *, object_name: str | None = None, **kw):
        self.add(Severity.ERROR, text, object_name=object_name, **kw)
