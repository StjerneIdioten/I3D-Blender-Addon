from .assemble import finalize_shape_material_ids, resolve_shape_links, resolve_shapes_build
from .bounding_volume import resolve_bounding_volumes
from .curve_shapes import resolve_curve_shapes
from .merge_children import resolve_merge_children
from .merge_group import resolve_merge_groups
from .skinned_mesh import resolve_skinned_meshes
from .vertex_requirements import resolve_shape_vertex_requirements

__all__ = [
    "finalize_shape_material_ids",
    "resolve_bounding_volumes",
    "resolve_curve_shapes",
    "resolve_font_shapes",
    "resolve_merge_children",
    "resolve_merge_groups",
    "resolve_shape_links",
    "resolve_shape_vertex_requirements",
    "resolve_shapes_build",
    "resolve_skinned_meshes",
]
