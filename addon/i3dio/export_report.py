from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ExportMessage:
    level: int
    text: str
    object_name: str | None = None
    code: str | None = None


@dataclass(slots=True)
class ExportReport:
    messages: list[ExportMessage] = field(default_factory=list)
    _dedupe: set[ExportMessage] = field(default_factory=set, repr=False)

    def add(self, level: int, text: str, *, object_name: str | None = None, code: str | None = None) -> None:
        message = ExportMessage(level=level, text=text, object_name=object_name, code=code)

        if message in self._dedupe:
            return

        self._dedupe.add(message)
        self.messages.append(message)

    @property
    def has_errors(self) -> bool:
        return any(message.level >= logging.ERROR for message in self.messages)

    @property
    def has_warnings(self) -> bool:
        return any(logging.WARNING <= message.level < logging.ERROR for message in self.messages)


class ExportReportHandler(logging.Handler):
    def __init__(self, report: ExportReport | None = None, level: int = logging.WARNING) -> None:
        super().__init__(level)
        self.report = report if report is not None else ExportReport()

    def emit(self, record: logging.LogRecord) -> None:
        """Add warning and above log records to the export report."""
        if record.levelno < logging.WARNING:
            return

        self.report.add(
            level=record.levelno,
            text=record.getMessage(),
            object_name=getattr(record, "object_name", None),
            code=getattr(record, "code", None),
        )


@contextmanager
def capture_export_report(logger: logging.Logger, report: ExportReport | None = None) -> Iterator[ExportReport]:
    """Capture warning and above log records into an ExportReport."""
    handler = ExportReportHandler(report)
    logger.addHandler(handler)

    try:
        yield handler.report
    finally:
        logger.removeHandler(handler)
        handler.close()


def report_to_operator(operator: Any, report: ExportReport, *, limit: int = 10) -> None:
    """Report export messages to a Blender operator, with errors shown before warnings."""
    if operator is None or not report.messages or limit <= 0:
        return

    ordered_messages = sorted(report.messages, key=lambda message: message.level < logging.ERROR)

    for message in ordered_messages[:limit]:
        report_type = "ERROR" if message.level >= logging.ERROR else "WARNING"
        operator.report({report_type}, message.text)

    if (hidden_count := len(ordered_messages) - limit) > 0:
        operator.report({"WARNING"}, f"...and {hidden_count} more warnings/errors. See console/log for details.")
