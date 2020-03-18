"""Debug module which primarily contains the loggers used in the code and any helpful functions for debugging"""
import logging

# A top level logger with the module name
addon_name = 'i3dio'
addon_logger = logging.getLogger(addon_name)
addon_logger.setLevel(logging.DEBUG)
addon_logger.handlers = []  # Reset upon reload, since reloading the addon does not reload the logging module

# Top-level handler for outputting to blender console
addon_console_handler = logging.StreamHandler()
addon_console_formatter = logging.Formatter('%(name)s:%(funcName)s:%(levelname)s: %(message)s')
addon_console_handler.setFormatter(addon_console_formatter)
addon_console_handler_default_level = logging.INFO
addon_console_handler.setLevel(addon_console_handler_default_level)
addon_logger.addHandler(addon_console_handler)

# Formatting for writing to a log file
addon_export_log_formatter = logging.Formatter('%(name)s:%(funcName)s:%(levelname)s: %(message)s')

# Write a little message to indicate that initialization is done
addon_logger.info(f"Initialized logging for {addon_name} addon")

export_log_file_ending = '_export_log.txt'


class ObjectNameAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        object_name = kwargs.pop('object_name', self.extra['object_name'])
        return f"[{object_name}] {msg}", kwargs
