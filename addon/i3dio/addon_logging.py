import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

ADDON_LOG_NAME = "i3dio"
ADDON_PACKAGE_NAME = __package__ or ADDON_LOG_NAME

EXPORT_LOG_SUFFIX = "_export_log.txt"
ADDON_CONSOLE_HANDLER_DEFAULT_LEVEL = logging.WARNING

_LOG_FORMAT = "%(shortname)s:%(funcName)s:%(levelname)s: %(prefix)s%(message)s"


def _short_logger_name(name: str) -> str:
    if name == ADDON_PACKAGE_NAME:
        return ADDON_LOG_NAME

    package_prefix = f"{ADDON_PACKAGE_NAME}."
    if name.startswith(package_prefix):
        return f"{ADDON_LOG_NAME}.{name.removeprefix(package_prefix)}"

    return name


class SafeExtraFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        if not hasattr(record, "prefix"):
            record.prefix = ""
        record.shortname = _short_logger_name(record.name)
        return super().format(record)


def _format_prefix(prefix: object = None) -> str:
    if not prefix:
        return ""
    prefix = str(prefix)
    return prefix if prefix.endswith(": ") else f"{prefix}: "


def _make_label(*, object_name: object = None, node_kind: object = None, node_id: object = None) -> str:
    label = ": ".join([str(part) for part in (node_kind, object_name) if part])
    if node_id is not None:
        return f"{label} | id={node_id}" if label else f"id={node_id}"

    return label


# A top level logger with the module name
addon_logger = logging.getLogger(ADDON_PACKAGE_NAME)
addon_logger.setLevel(logging.DEBUG)
addon_logger.handlers.clear()  # Reset upon reload, since reloading the addon does not reload the logging module

# Top-level handler for outputting to blender console
addon_console_handler = logging.StreamHandler()
addon_console_handler.setFormatter(SafeExtraFormatter(_LOG_FORMAT))
addon_console_handler.setLevel(ADDON_CONSOLE_HANDLER_DEFAULT_LEVEL)
addon_logger.addHandler(addon_console_handler)
addon_logger.propagate = False  # Don't propagate to root logger, which would cause duplicate messages in console

addon_export_log_formatter = SafeExtraFormatter(_LOG_FORMAT)

addon_logger.info("Initialized logging for %s addon", ADDON_LOG_NAME)


def get_logger(name: str) -> logging.Logger:
    """Return an addon logger from either a relative or absolute module name."""
    if name == ADDON_PACKAGE_NAME or name.startswith(f"{ADDON_PACKAGE_NAME}."):
        return logging.getLogger(name)
    return addon_logger.getChild(name)


@contextmanager
def export_log_file(filepath: str) -> Iterator[logging.FileHandler]:
    handler = logging.FileHandler(filepath, mode="w", encoding="utf-8")
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(addon_export_log_formatter)
    addon_logger.addHandler(handler)
    try:
        yield handler
    finally:
        addon_logger.removeHandler(handler)
        handler.close()


class ExportLogAdapter(logging.LoggerAdapter):
    """Inject export context such as object name, node kind, node id, and prefix."""

    def process(self, msg: str, kwargs: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        extra = dict(kwargs.get("extra") or {})

        object_name = extra.pop("object_name", self.extra.get("object_name"))
        node_kind = extra.pop("node_kind", self.extra.get("node_kind"))
        node_id = extra.pop("node_id", self.extra.get("node_id"))
        prefix = extra.pop("prefix", self.extra.get("prefix", ""))

        label = _make_label(object_name=object_name, node_kind=node_kind, node_id=node_id)
        head = f"[{label}] " if label else ""

        extra["prefix"] = _format_prefix(prefix)
        kwargs["extra"] = extra
        return f"{head}{msg}", kwargs


def get_export_logger(name: str, **extra: Any) -> ExportLogAdapter:
    return ExportLogAdapter(get_logger(name), extra)


def get_export_logger_for(obj: object, **extra: Any) -> ExportLogAdapter:
    return get_export_logger(f"{type(obj).__module__}.{type(obj).__name__}", **extra)
