"""This module contains functionality for handling the i3d xml format such as reading and writing with correct
precision"""

from __future__ import annotations  # Enables python 4.0 annotation typehints fx. class self-referencing

import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Callable, Mapping, TextIO
from xml.sax.saxutils import quoteattr

import bpy
import mathutils
import numpy as np
from idprop.types import IDPropertyArray

logger = logging.getLogger(__name__)

# Public constants / types
XML_Element = ET.Element
FILE_EXT = ".i3d"
I3D_MAX = 3.40282e38

_ENCODING = "iso-8859-1"
_INDENT = "  "


# Parse / Element constructors
def parse(*argv, **kwargs) -> ET.ElementTree | None:
    try:
        return ET.parse(*argv, **kwargs, parser=ET.XMLParser())
    except (ET.ParseError, FileNotFoundError) as e:
        logger.error("Error while parsing xml file: %s", e)
        return None


def iter_section(root: XML_Element, section_name: str, child_tag: str) -> ET.Element | None:
    section = root.find(section_name)
    if section is None:
        return None
    for child in section:
        if child.tag == child_tag:
            yield child


def SubElement(*args, **kwargs) -> ET.Element:  # noqa: N802
    return ET.SubElement(*args, **kwargs)


def SubElementA(parent: ET.Element, tag: str, attrib: Mapping[str, Any] | None = None, **extra: Any) -> ET.Element:  # noqa: N802
    """Like ET.SubElement, but all attribute values go through fmt_attr_value()."""
    elem = ET.SubElement(parent, tag)
    if attrib:
        for k, v in attrib.items():
            write_attribute(elem, k, v)
    for k, v in extra.items():
        write_attribute(elem, k, v)
    return elem


# Root
def i3d_root_element(name: str) -> XML_Element:
    root_attributes = {'version': '1.6'}
    namespaced_attributes = {
        'xsi:noNamespaceSchemaLocation': 'http://i3d.giants.ch/schema/i3d-1.6.xsd',
        'xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
    }
    return ET.Element("i3D", attrib={"name": name, **root_attributes, **namespaced_attributes})


# Attribute formatting / writing
def _fmt_vector(values: tuple[float, ...]) -> str:
    return " ".join(f"{float(x):.6g}" for x in values)


def fmt_attr_value(value: Any) -> str:
    """
    Format a value as it should appear inside an XML attribute.

    This is the single formatting source of truth for:
    - ElementTree attribute writes (write_attribute)
    - Streaming writers (write_open_tag, ITS stream, etc.)
    """
    if isinstance(value, (bool, np.bool_)):  # order matters (bool is int subclass)
        return "true" if bool(value) else "false"
    if isinstance(value, int):
        return f"{value:d}"
    if isinstance(value, float):
        return f"{value:.6g}"
    # numpy scalar numbers (np.int64, np.float32, etc.)
    if isinstance(value, np.integer):
        return f"{int(value):d}"
    if isinstance(value, np.floating):
        return f"{float(value):.6g}"
    if isinstance(value, str):
        return value

    # Vector-ish
    if isinstance(value, np.ndarray):
        # Treat 1D arrays as vectors; higher dims fall back to str().
        if value.ndim == 0:
            return fmt_attr_value(value.item())
        if value.ndim == 1:
            return _fmt_vector(tuple(float(x) for x in value))

    if isinstance(value, (list, tuple, bpy.types.bpy_prop_array, IDPropertyArray, mathutils.Color, mathutils.Vector)):
        return _fmt_vector(tuple(value))

    # Fallback
    return str(value)


def write_attribute(element: XML_Element, attribute: str, value: Any) -> None:
    element.set(attribute, fmt_attr_value(value))


# Pretty indentation
def add_indentations(elem: ET.Element, level: int = 0) -> None:
    """Pretty-print XML by adding indentation text nodes."""
    i = "\n" + level * _INDENT
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + _INDENT

        for child in elem:
            add_indentations(child, level + 1)
            if not child.tail or not child.tail.strip():
                child.tail = i + _INDENT  # indent siblings under this parent

        # NOTE: last child tail should align the closing tag of the parent
        if not elem[-1].tail or not elem[-1].tail.strip():
            elem[-1].tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i


# Streaming writer helpers
def write_open_tag(f: TextIO, tag: str, attrib: Mapping[str, Any] | None = None, indent: str = "") -> None:
    if not attrib:
        f.write(f"{indent}<{tag}>\n")
        return
    parts = [f"{k}={quoteattr(fmt_attr_value(v))}" for k, v in attrib.items()]
    f.write(f"{indent}<{tag} " + " ".join(parts) + ">\n")


def write_close_tag(f: TextIO, tag: str, indent: str = "") -> None:
    f.write(f"{indent}</{tag}>\n")


# Export
def export_to_i3d_file(*, root: ET.Element, file_path: str | Path, shapes_writer: Callable[[TextIO], None]) -> None:
    """
    Write an I3D where all sections are ElementTree-serialized, except <Shapes> content,
    which is produced by shapes_writer(f).

    NOTE: Shapes are always streamed for performance.
    """
    if not any(child.tag == "Shapes" for child in list(root)):
        raise ValueError("Root element has no <Shapes> child. Add it before exporting.")
    # Always pretty-print the non-streamed parts. Not really any noticeable performance cost.
    add_indentations(root)

    with open(file_path, "w", encoding=_ENCODING, newline="\n") as f:
        f.write(f'<?xml version="1.0" encoding="{_ENCODING}"?>\n')

        # <i3D ...>
        write_open_tag(f, root.tag, root.attrib, indent="")
        t = root.text or ""
        if t.startswith("\n"):
            t = t[1:]
        f.write(t)

        # Children in order; stream Shapes
        for child in list(root):
            if child.tag == "Shapes":
                f.write("<Shapes>\n")  # Already at correct indent level due to root.text / previous tail
                shapes_writer(f)
                # Close Shapes at one indent level (2 spaces)
                f.write("  </Shapes>")
                # Preserve whatever indentation/newline ElementTree computed after <Shapes/>
                f.write(child.tail or "\n")
                continue

            f.write(ET.tostring(child, encoding="unicode", method="xml"))

        write_close_tag(f, root.tag, indent="")
