"""Export a Blender 4.5 file with persisted hierarchy, mesh, UV, and modifier data."""

import bpy
import pytest


@pytest.fixture
def saved_scene(load_blend):
    scene = load_blend("export/mesh_hierarchy.blend")
    assert bpy.data.version[:2] == (4, 5), "Keep the saved fixture compatible with Blender 4.5"
    return scene


def _shape(result, name):
    node = result.root.find(f"Scene/TransformGroup[@name='FixtureRoot']/Shape[@name='{name}']")
    assert node is not None, f"Missing mesh node {name}"
    geometry = result.root.find(f"Shapes/IndexedTriangleSet[@shapeId='{node.get('shapeId')}']")
    assert geometry is not None, f"Missing geometry referenced by {name}"
    return node, geometry


def _vector(element, attribute, default="0 0 0"):
    return tuple(float(value) for value in element.get(attribute, default).split())


def test_saved_hierarchy_preserves_local_transforms(saved_scene, export_i3d):
    result = export_i3d(keep_collections_as_transformgroups=False)
    root = result.root.find("Scene/TransformGroup[@name='FixtureRoot']")
    assert root is not None
    assert {child.get("name") for child in root} == {"Panel", "PanelInstance", "SolidPanel"}

    # Blender (x, y, z) becomes I3D (x, z, -y), with scene units scaled by 0.5.
    assert _vector(root, "translation") == pytest.approx((1, 3, -2), abs=1e-6)
    assert _vector(root, "rotation") == pytest.approx((0, 90, 0), abs=1e-4)
    panel, _ = _shape(result, "Panel")
    instance, _ = _shape(result, "PanelInstance")
    solid, _ = _shape(result, "SolidPanel")
    assert _vector(panel, "translation") == pytest.approx((0, 0, -1), abs=1e-6)
    assert _vector(instance, "translation") == pytest.approx((0, 0.5, 1), abs=1e-6)
    assert _vector(instance, "scale", "1 1 1") == pytest.approx((0.5, 2, 1.5))
    assert _vector(solid, "translation") == pytest.approx((0, 1, 0), abs=1e-6)
    assert result.root.find("Scene/TransformGroup[@name='OutsideHierarchy']") is not None


def test_saved_linked_mesh_preserves_uvs_and_material_assignments(saved_scene, export_i3d):
    assert saved_scene.objects["Panel"].data == saved_scene.objects["PanelInstance"].data
    result = export_i3d(keep_collections_as_transformgroups=False)
    panel, geometry = _shape(result, "Panel")
    instance, _ = _shape(result, "PanelInstance")
    assert panel.get("shapeId") == instance.get("shapeId")
    assert len(result.root.findall("Shapes/IndexedTriangleSet")) == 2

    vertices = geometry.find("Vertices")
    triangles = geometry.find("Triangles")
    subsets = geometry.find("Subsets")
    assert int(vertices.get("count")) == len(vertices) == 8
    assert vertices.get("uv0") == "true"
    assert int(triangles.get("count")) == len(triangles) == 4
    assert int(subsets.get("count")) == len(subsets) == 2
    assert [int(subset.get("numIndices")) for subset in subsets] == [6, 6]
    for triangle in triangles:
        indices = [int(index) for index in triangle.get("vi").split()]
        assert len(indices) == 3
        assert all(0 <= index < len(vertices) for index in indices)

    # Check seam coordinates as vertex/UV pairs without relying on buffer ordering.
    actual = sorted((*_vector(vertex, "p"), *_vector(vertex, "t0")) for vertex in vertices)
    expected = sorted(
        [
            (0, 0, 0, 0, 0),
            (1, 0, 0, 1, 0),
            (1, 0, -0.5, 1, 1),
            (0, 0, -0.5, 0, 1),
            (1, 0, 0, 0, 0),
            (2, 0, 0, 1, 0),
            (2, 0, -0.5, 1, 1),
            (1, 0, -0.5, 0, 1),
        ]
    )
    for actual_vertex, expected_vertex in zip(actual, expected):
        assert actual_vertex == pytest.approx(expected_vertex)

    materials = {
        material.get("materialId"): material.get("name") for material in result.root.findall("Materials/Material")
    }
    assert [materials[identifier] for identifier in panel.get("materialIds").split()] == ["FixtureRed", "FixtureBlue"]
    assert [materials[identifier] for identifier in instance.get("materialIds").split()] == [
        "FixtureGreen",
        "FixtureBlue",
    ]


@pytest.mark.parametrize(
    ("apply_modifiers", "triangle_count", "height"),
    [(True, 12, 0.25), (False, 2, 0.0)],
    ids=["evaluated-solidify", "original-quad"],
)
def test_saved_modifier_is_optional_and_non_destructive(
    saved_scene, export_i3d, apply_modifiers, triangle_count, height
):
    result = export_i3d(keep_collections_as_transformgroups=False, apply_modifiers=apply_modifiers)
    _, geometry = _shape(result, "SolidPanel")
    triangles = geometry.find("Triangles")
    assert int(triangles.get("count")) == len(triangles) == triangle_count
    y_values = [_vector(vertex, "p")[1] for vertex in geometry.find("Vertices")]
    assert min(y_values) == pytest.approx(0)
    assert max(y_values) == pytest.approx(height)
    assert len(saved_scene.objects["SolidPanel"].data.polygons) == 1
    assert saved_scene.objects["SolidPanel"].modifiers["FixtureThickness"].type == 'SOLIDIFY'


@pytest.mark.parametrize("include_children", [True, False], ids=["subtree", "root-only"])
def test_saved_selection_controls_child_export(saved_scene, export_i3d, include_children):
    assert {obj.name for obj in bpy.context.selected_objects} == {"FixtureRoot"}
    result = export_i3d(selection="SELECTED_OBJECTS", selection_traverse_children=include_children)
    nodes = result.root.find("Scene")
    names = {node.get("name") for node in nodes.iter() if node.get("nodeId") is not None}
    expected = {"FixtureRoot", "Panel", "PanelInstance", "SolidPanel"} if include_children else {"FixtureRoot"}
    assert names == expected
