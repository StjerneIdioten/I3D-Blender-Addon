from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass
from typing import Any

from .errors import ExportUserError
from .messages import ExportMessage, Severity


@dataclass(slots=True)
class Reporter:
    ctx: Any
    log: logging.LoggerAdapter
    operator: Any | None = None

    def _default_object_name(self) -> str | None:
        extra = getattr(self.log, "extra", None)
        return extra.get("object_name") if isinstance(extra, dict) else None

    @staticmethod
    def _msg_text(msg: str, args: tuple[object, ...]) -> str:
        return (msg % args) if args else msg

    def info(self, msg: str, *args, stacklevel: int = 2) -> None:
        self.log.info(msg, *args, stacklevel=stacklevel)

    def debug(self, msg: str, *args, stacklevel: int = 2) -> None:
        self.log.debug(msg, *args, stacklevel=stacklevel)

    def _log_and_record(
        self,
        level: str,
        msg: str,
        args: tuple,
        *,
        object_name: str | None,
        code: str | None,
        report: bool,
        stacklevel: int,
    ) -> str:
        """Common logic for warning/error: log, record message, optionally report to operator."""
        getattr(self.log, level)(msg, *args, stacklevel=stacklevel + 1)
        text = self._msg_text(msg, args)
        obj = object_name or self._default_object_name()
        getattr(self.ctx.messages, level)(text, object_name=obj, code=code)
        if report and self.operator:
            self.operator.report({level.upper()}, text)
        return text

    def warning(
        self,
        msg: str,
        *args,
        object_name: str | None = None,
        code: str | None = None,
        report: bool = False,
        stacklevel: int = 2,
    ) -> None:
        self._log_and_record(
            "warning", msg, args, object_name=object_name, code=code, report=report, stacklevel=stacklevel
        )

    def error(
        self,
        msg: str,
        *args,
        object_name: str | None = None,
        code: str | None = None,
        report: bool = False,
        stacklevel: int = 2,
    ) -> None:
        self._log_and_record(
            "error", msg, args, object_name=object_name, code=code, report=report, stacklevel=stacklevel
        )

    def exception(
        self,
        msg: str,
        *args,
        object_name: str | None = None,
        code: str | None = None,
        severity: Severity = Severity.WARNING,
        stacklevel: int = 2,
    ) -> None:
        self.log.exception(msg, *args, stacklevel=stacklevel)
        text = self._msg_text(msg, args)
        obj = object_name or self._default_object_name()
        record = self.ctx.messages.error if severity is Severity.ERROR else self.ctx.messages.warning
        record(text, object_name=obj, code=code)

    def abort(
        self, msg: str, *args, object_name: str | None = None, code: str | None = None, report: bool = True
    ) -> None:
        """Log error, record message, optionally report to operator, and raise ExportUserError."""
        text = self._log_and_record("error", msg, args, object_name=object_name, code=code, report=report, stacklevel=2)
        raise ExportUserError(text)


def _fmt_message(m: ExportMessage) -> str:
    return f"[{m.object_name}] {m.text}" if m.object_name else m.text


def report_messages_to_operator(ctx: Any, *, limit: int = 10, code_summary_limit: int = 5) -> None:
    if not (operator := getattr(ctx, "operator", None)) or limit <= 0 or not ctx.messages.items:
        return

    by_severity = {s: [m for m in ctx.messages.items if m.severity is s] for s in Severity}

    # Show errors first, then warnings, up to limit
    shown: list[ExportMessage] = []
    for sev in (Severity.ERROR, Severity.WARNING):
        for m in by_severity[sev]:
            if len(shown) >= limit:
                break
            operator.report({sev.name}, _fmt_message(m))
            shown.append(m)

    # Summarize remaining by code
    remaining = [m for m in by_severity[Severity.ERROR] + by_severity[Severity.WARNING] if m not in shown]
    if not remaining:
        return

    counts = Counter(m.code for m in remaining if m.code)
    accounted = 0
    for code, n in counts.most_common(code_summary_limit):
        operator.report({"WARNING"}, f"...and {n} more: {code} (see export log)")
        accounted += n

    if (hidden := len(remaining) - accounted) > 0:
        operator.report({"WARNING"}, f"...and {hidden} more messages (see export log).")
