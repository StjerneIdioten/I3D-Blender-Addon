"""Geometry and material references in raw I3D mesh exports."""

import bpy


def test_mesh_raw_i3d_export(empty_scene, export_i3d):
    mesh = bpy.data.meshes.new("Triangle")
    mesh.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
    obj = bpy.data.objects.new("Triangle", mesh)
    empty_scene.collection.objects.link(obj)
    mesh.materials.append(bpy.data.materials.new("TestMaterial"))

    result = export_i3d()
    shape_node = result.root.find("Scene/Shape[@name='Triangle']")
    assert shape_node is not None
    shape = result.root.find(f"Shapes/IndexedTriangleSet[@shapeId='{shape_node.get('shapeId')}']")
    assert shape is not None

    vertices = shape.find("Vertices")
    triangles = shape.find("Triangles")
    assert int(vertices.get("count")) == len(vertices) == 3
    assert int(triangles.get("count")) == len(triangles) == 1
    indices = [int(value) for value in triangles[0].get("vi").split()]
    assert sorted(indices) == [0, 1, 2]
    material_ids = shape_node.get("materialIds").split()
    assert len(material_ids) == 1
    for material_id in material_ids:
        assert result.root.find(f"Materials/Material[@materialId='{material_id}']") is not None
