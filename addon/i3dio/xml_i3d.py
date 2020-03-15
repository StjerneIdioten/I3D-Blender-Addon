"""This module contains functionality for handling the i3d xml format such as reading and writing with correct
precision """

import xml.etree.ElementTree as ET  # Technically not following pep8, but this is the naming suggestion from the module


def write_int(element: ET.Element, attribute: str, value: int) -> None:
    """Write the attribute into the element with formatting for ints"""
    element.set(attribute, f"{value:d}")


def write_float(element: ET.Element, attribute: str, value: float) -> None:
    """Write the attribute into the element with formatting for floats"""
    element.set(attribute, f"{value:.7f}")


def write_bool(element: ET.Element, attribute: str, value: bool) -> None:
    """Write the attribute into the element with formatting for booleans"""
    element.set(attribute, f"{value!s}".lower())


def write_string(element: ET.Element, attribute: str, value: str) -> None:
    """Write the attribute into the element with formatting for strings"""
    element.set(attribute, value)


def write_attribute(element: ET.Element, attribute: str, value) -> None:
    if isinstance(value, float):
        write_float(element, attribute, value)
    elif isinstance(value, bool):  # Order matters, since bool is an int subclass!
        write_bool(element, attribute, value)
    elif isinstance(value, int):
        write_int(element, attribute, value)
    elif isinstance(value, str):
        write_string(element, attribute, value)


def add_indentations(element: ET.Element, level: int = 0) -> None:
    """
    Used for pretty printing the xml since etree does not indent elements and keeps everything in one continues
    string and since i3d files are supposed to be human readable, we need indentation. There is a patch for
    pretty printing on its way in the standard library, but it is not available until python 3.9 comes around.

    The module 'lxml' could also be used since it has pretty-printing, but that would introduce an external
    library dependency for the addon.

    The source code from this solution is taken from http://effbot.org/zone/element-lib.htm#prettyprint

    It recursively checks every element and adds a newline + space indents to the element to make it pretty and
    easily readable. This technically changes the xml, but the giants engine does not seem to mind the linebreaks
    and spaces, when parsing the i3d file.
    """
    indents = '\n' + level * '  '
    if len(element):
        if not element.text or not element.text.strip():
            element.text = indents + '  '
        if not element.tail or not element.tail.strip():
            element.tail = indents
        for element in element:
            add_indentations(element, level + 1)
        if not element.tail or not element.tail.strip():
            element.tail = indents
    else:
        if level and (not element.tail or not element.tail.strip()):
            element.tail = indents
