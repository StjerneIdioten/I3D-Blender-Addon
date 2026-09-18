"""Share property definitions and requirement checks between the UI and export.

resolve_attributes returns export-ready values with I3D names and destination
labels such as Node and IndexedTriangleSet. The exporter supplies the corresponding
XML elements and writes the values; this package reads properties and checks their
requirements without creating XML elements or changing stored values.
"""

from . import light, mesh

__all__ = ["light", "mesh"]
