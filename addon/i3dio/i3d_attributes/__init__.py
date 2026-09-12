"""Schemas own property rules; UI and export consumers share their evaluation.

resolve_attributes captures a tuple of detached values for immediate XML writing
or later IR assignment. Consumers supply destinations: Node is their primary
element, IndexedTriangleSet is a separate shape resource, and material children
must be created by the material exporter. This package does not allocate resources
or infer XML hierarchy from destination labels.
"""

from . import light, mesh

__all__ = ["light", "mesh"]
