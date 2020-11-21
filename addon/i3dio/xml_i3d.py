"""This module contains functionality for handling the i3d xml format such as reading and writing with correct
precision """
from __future__ import annotations  # Enables python 4.0 annotation typehints fx. class self-referencing
from typing import (Union, Dict)
import math
import logging

# Load in the xml modules
xml_libraries = {'element_tree'}
xml_current_library = 'element_tree'
import xml.etree.ElementTree as ET  # Technically not following pep8, but this is the naming suggestion from the module
XML_Element = ET.Element
xml_parsing_exceptions = [ET.ParseError, FileNotFoundError]
try:
    from lxml import etree
    xml_libraries.add('lxml')
    print("xml_i3d has access to lxml")
    XML_Element = Union[ET.Element, etree.Element]
    xml_parsing_exceptions.append(etree.ParseError)
    xml_current_library = 'lxml'
except ImportError as e:
    etree = e
    print("xml_i3d does not have access to lxml")


print("xml_i3d just got reloaded")

logger = logging.getLogger(__name__)

file_ending = '.i3d'

merge_group_prefix = 'MergedMesh_'
skinned_mesh_prefix = 'SkinnedMesh_'


def _generic_library_switcher(function: str, *argv, **kwargs):
    """
    Very generic way of calling functions that have the same signature between the two libraries

    Args:
        function:
        *argv:
        **kwargs:

    Returns:

    """
    if xml_current_library == 'lxml':
        return getattr(etree, function)(*argv, **kwargs)
    else:
        return getattr(ET, function)(*argv, **kwargs)


class CommentedTreeBuilder(ET.TreeBuilder):
    """
    This class is used to enable elemtree to NOT delete comments of parsed trees...
    """
    def comment(self, data):
        self.start(ET.Comment, {})
        self.data(data)
        self.end(ET.Comment)


def parse(*argv, **kwargs):
    tree = None
    try:
        if xml_current_library == 'lxml':
            tree = etree.parse(*argv, **kwargs, parser=etree.XMLParser(remove_blank_text=True))
        else:
            tree = ET.parse(*argv, **kwargs, parser=ET.XMLParser(target=CommentedTreeBuilder()))
    except tuple(xml_parsing_exceptions) as e:
        print(f"Error while parsing xml file: {e}")
    return tree


def SubElement(*argv, **kwargs):
    return _generic_library_switcher('SubElement', *argv, **kwargs)


def Element(*argv, **kwargs):
    return _generic_library_switcher('Element', *argv, **kwargs)


def ElementTree(*argv, **kwargs):
    return _generic_library_switcher('ElementTree', *argv, **kwargs)


def write_tree_to_file(tree, file_path: str, *argv, **kwargs):
    if xml_current_library == 'lxml':
        f = open(file_path, 'w')
        i3d_string = etree.tostring(tree, *argv, pretty_print=True, **kwargs).decode(kwargs['encoding'])
        i3d_string = i3d_string.replace("&gt;", ">")
        f.write(i3d_string)
        f.close()
    else:
        add_indentations(tree.getroot())
        tree.write(file_path, *argv, **kwargs)


def export_to_i3d_file(source: XML_Element, file_path: str, *argv, **kwargs):
    settings = {
        'xml_declaration': True,
        'encoding': 'iso-8859-1',
        'method': 'xml'
    }

    write_tree_to_file(ElementTree(source), file_path, *argv, **settings, **kwargs)


def i3d_root_element(name: str):

    root_attributes = {
        'version': '1.6',
    }

    namespaced_attributes = {
        'xsi:noNamespaceSchemaLocation': 'http://i3d.giants.ch/schema/i3d-1.6.xsd',
        'xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance'
    }

    if xml_current_library == 'lxml':
        nsmap = {
            'xsi': 'http://www.w3.org/2001/XMLSchema-instance'
        }
        attr_qname = etree.QName("http://www.w3.org/2001/XMLSchema-instance", 'noNamespaceSchemaLocation')
        return Element('i3D', attrib={'name': name, **root_attributes,
                                      attr_qname: 'http://i3d.giants.ch/schema/i3d-1.6.xsd'}, nsmap=nsmap)
    else:
        return Element('i3D', attrib={'name': name, **root_attributes, **namespaced_attributes})


def write_int(element: XML_Element, attribute: str, value: int) -> None:
    """Write the attribute into the element with formatting for ints"""
    element.set(attribute, f"{value:d}")


def write_float(element: XML_Element, attribute: str, value: float) -> None:
    """Write the attribute into the element with formatting for floats"""
    element.set(attribute, f"{value:.7f}")


def write_bool(element: XML_Element, attribute: str, value: bool) -> None:
    """Write the attribute into the element with formatting for booleans"""
    element.set(attribute, f"{value!s}".lower())


def write_string(element: XML_Element, attribute: str, value: str) -> None:
    """Write the attribute into the element with formatting for strings"""
    element.set(attribute, value)


def write_attribute(element: XML_Element, attribute: str, value) -> None:
    if isinstance(value, float):
        write_float(element, attribute, value)
    elif isinstance(value, bool):  # Order matters, since bool is an int subclass!
        write_bool(element, attribute, value)
    elif isinstance(value, int):
        write_int(element, attribute, value)
    elif isinstance(value, str):
        write_string(element, attribute, value)


def write_property_group(property_group, elements: Dict[str, Union[XML_Element, None]]) -> None:
    logger.info(f"Writing non-default properties from propertygroup: '{type(property_group).__name__}'")
    # Since blender properties are basically abusing the annotation system, we can also abuse this to create
    # a generic property export function by accessing the annotation dictionary
    properties_written = 0
    for prop_key in property_group.__annotations__.keys():
        prop_name = prop_key
        value = getattr(property_group, prop_key)
        value_to_write = value
        default = property_group.i3d_map[prop_key].get('default')
        i3d_name = property_group.i3d_map[prop_key].get('name')
        field_type = property_group.i3d_map[prop_key].get('type')
        i3d_placement = property_group.i3d_map[prop_key].get('placement', 'Node')

        # Special case of checking floats, since these can be not equal due to floating point errors
        if isinstance(value, float):
            if math.isclose(value, default, abs_tol=0.0000001):
                continue
        # In the case that the value is default, then just ignore it
        elif value == default:
            continue
        # In some cases of enums the i3d_name is actually the enum value itself. It is signaled by not having a name
        elif i3d_name is None:
            i3d_name = value
            value_to_write = 1
        # String field is used for unique types, that then get converted fx. HEX values. This is signaled by
        # having an extra type field in the i3d_map dictionary entry for the propertygroup
        elif field_type is not None:
            if field_type == 'HEX':
                try:
                    value_decimal = int(value, 16)
                except ValueError:
                    logger.error(f"Supplied value '{value}' for '{prop_name}' is not a hex value!")
                    continue
                else:
                    if 0 <= value_decimal <= 2**32-1:  # Check that it is actually a 32-bit unsigned int
                        value_to_write = value_decimal
                    else:
                        logger.warning(f"Supplied value '{value}' for '{prop_name}' is out of bounds."
                                       f" It should be within range [0, ffffffff] (32-bit unsigned)")
                        continue
            elif field_type == 'OVERRIDE':
                value_to_write = property_group.i3d_map[prop_key].get('override')

        logger.debug(f"Property '{prop_name}' with value '{value}'. Default is '{default}'")
        write_attribute(elements[i3d_placement], i3d_name, value_to_write)
        properties_written += 1

    logger.info(f"Wrote '{properties_written}' properties")


def add_indentations(element: XML_Element, level: int = 0) -> None:
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


def escape_attrib_element_tree(text):
    # escape attribute value
    try:
        if "&" in text:
            text = text.replace("&", "&amp;")
        if "<" in text:
            text = text.replace("<", "&lt;")
        if ">" in text:
            # Needed for the i3d format
            pass
            #text = text.replace(">", "&gt;")
        if "\"" in text:
            text = text.replace("\"", "&quot;")
        # The following business with carriage returns is to satisfy
        # Section 2.11 of the XML specification, stating that
        # CR or CR LN should be replaced with just LN
        # http://www.w3.org/TR/REC-xml/#sec-line-ends
        if "\r\n" in text:
            text = text.replace("\r\n", "\n")
        if "\r" in text:
            text = text.replace("\r", "\n")
        #The following four lines are issue 17582
        if "\n" in text:
            text = text.replace("\n", "&#10;")
        if "\t" in text:
            text = text.replace("\t", "&#09;")
        return text
    except (TypeError, AttributeError):
        ET._raise_serialization_error(text)


# Assign the escape attribute function to replace the default implementation
ET._escape_attrib = escape_attrib_element_tree


