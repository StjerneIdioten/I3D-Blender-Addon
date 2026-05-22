"""Debug module which primarily contains the loggers used in the code and any helpful functions for debugging"""

import logging
from contextlib import contextmanager


class SafeExtraFormatter(logging.Formatter):
    def format(self, record):
        if not hasattr(record, "prefix"):
            record.prefix = ""
        return super().format(record)


# A top level logger with the module name
addon_name = __package__
addon_logger = logging.getLogger(addon_name)
addon_logger.setLevel(logging.DEBUG)
addon_logger.handlers = []  # Reset upon reload, since reloading the addon does not reload the logging module

# Top-level handler for outputting to blender console
addon_console_handler = logging.StreamHandler()
addon_console_formatter = SafeExtraFormatter("%(name)s:%(funcName)s:%(levelname)s: %(prefix)s%(message)s")
addon_console_handler.setFormatter(addon_console_formatter)
addon_console_handler_default_level = logging.WARNING
addon_console_handler.setLevel(addon_console_handler_default_level)
addon_logger.addHandler(addon_console_handler)
addon_logger.propagate = False  # Prevent double logging if root logger is used

# Formatting for writing to a log file
addon_export_log_formatter = SafeExtraFormatter("%(name)s:%(funcName)s:%(levelname)s: %(prefix)s%(message)s")

# Write a little message to indicate that initialization is done
addon_logger.info(f"Initialized logging for {addon_name} addon")

export_log_file_ending = "_export_log.txt"


def get_logger(name: str) -> logging.Logger:
    # keeps everything under the addon root for consistent filtering
    return addon_logger.getChild(name)


@contextmanager
def export_log_file(filepath: str):
    handler = logging.FileHandler(filepath, mode="w", encoding="utf-8")
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(addon_export_log_formatter)
    addon_logger.addHandler(handler)
    try:
        yield handler
    finally:
        addon_logger.removeHandler(handler)
        handler.close()


class ContextAdapter(logging.LoggerAdapter):
    """
    Adapter that can inject a node/object label and/or a textual prefix.

    Supported fields (can be provided in adapter extra, or per-call via extra={}):
      - object_name: str
      - node_kind: str (optional)
      - node_id: int (optional)
      - prefix: str (optional)  e.g. "i3dMappings: "
    """

    def process(self, msg, kwargs):
        extra = kwargs.get("extra") or {}

        # allow per-call overrides (and prevent leaking them further down)
        object_name = extra.pop("object_name", None) or self.extra.get("object_name")
        node_kind = extra.pop("node_kind", None) or self.extra.get("node_kind")
        node_id = extra.pop("node_id", None) or self.extra.get("node_id")
        prefix = extra.pop("prefix", None) or self.extra.get("prefix", "")

        kwargs["extra"] = extra  # keep any other extra keys intact

        # Build label like: "SHAPE: MyRock | id=123"
        label_parts = []
        if node_kind:
            label_parts.append(str(node_kind))
        if object_name:
            # if you prefer kind/name formatting differently, tweak here
            label_parts.append(str(object_name))
        label = ": ".join(label_parts) if label_parts else ""
        if node_id is not None and label:
            label = f"{label} | id={node_id}"
        elif node_id is not None and not label:
            label = f"| id={node_id}"

        head = f"[{label}] " if label else ""

        if prefix:
            prefix = prefix if prefix.endswith(": ") else prefix + ": "

        extra["prefix"] = prefix
        kwargs["extra"] = extra
        return f"{head}{msg}", kwargs
