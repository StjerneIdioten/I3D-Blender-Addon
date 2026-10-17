"""Regenerate mesh_hierarchy.blend with Blender 4.5; no add-on or game assets needed.

From the repository root:
    blender --background --factory-startup --python-exit-code 1 --python tests/fixtures/export/build_mesh_hierarchy.py
"""

import math
from pathlib import Path

import bpy


def build():
    if bpy.app.version[:2] != (4, 5):
        raise SystemExit(
            "Regenerate this fixture with Blender 4.5 for compatibility with the minimum supported version"
        )

    bpy.ops.wm.read_homefile(use_empty=True, use_factory_startup=True)
    scene = bpy.context.scene
    scene.name = "MeshHierarchyFixture"
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 0.5

    collection = bpy.data.collections.new("FixtureAssembly")
    scene.collection.children.link(collection)
    root = bpy.data.objects.new("FixtureRoot", None)
    collection.objects.link(root)
    root.location = (2, 4, 6)
    root.rotation_euler.z = math.pi / 2
    root.empty_display_type = 'PLAIN_AXES'

    materials = {}
    for name, color in (
        ("FixtureRed", (0.8, 0.1, 0.1, 1.0)),
        ("FixtureBlue", (0.1, 0.2, 0.8, 1.0)),
        ("FixtureGreen", (0.1, 0.7, 0.2, 1.0)),
    ):
        material = bpy.data.materials.new(name)
        material.diffuse_color = color
        materials[name] = material

    panel_mesh = bpy.data.meshes.new("SharedPanelMesh")
    panel_mesh.from_pydata(
        [(0, 0, 0), (2, 0, 0), (2, 1, 0), (0, 1, 0), (4, 0, 0), (4, 1, 0)],
        [],
        [(0, 1, 2, 3), (1, 4, 5, 2)],
    )
    panel_mesh.materials.append(materials["FixtureRed"])
    panel_mesh.materials.append(materials["FixtureBlue"])
    uv_layer = panel_mesh.uv_layers.new(name="UVMap")
    for index, polygon in enumerate(panel_mesh.polygons):
        polygon.material_index = index
        for loop_index, uv in zip(polygon.loop_indices, [(0, 0), (1, 0), (1, 1), (0, 1)]):
            uv_layer.data[loop_index].uv = uv
    panel_mesh.update()

    for name, location in (("Panel", (0, 2, 0)), ("PanelInstance", (0, -2, 1))):
        obj = bpy.data.objects.new(name, panel_mesh)
        collection.objects.link(obj)
        obj.parent = root
        obj.location = location
        if name == "PanelInstance":
            obj.scale = (0.5, 1.5, 2.0)
            obj.material_slots[0].link = 'OBJECT'
            obj.material_slots[0].material = materials["FixtureGreen"]

    solid_mesh = bpy.data.meshes.new("SolidPanelMesh")
    solid_mesh.from_pydata([(0, 0, 0), (2, 0, 0), (2, 1, 0), (0, 1, 0)], [], [(0, 1, 2, 3)])
    solid_mesh.materials.append(materials["FixtureBlue"])
    solid_mesh.update()
    solid = bpy.data.objects.new("SolidPanel", solid_mesh)
    collection.objects.link(solid)
    solid.parent = root
    solid.location = (0, 0, 2)
    modifier = solid.modifiers.new("FixtureThickness", 'SOLIDIFY')
    modifier.thickness = 0.5
    modifier.offset = 1.0

    outside = bpy.data.objects.new("OutsideHierarchy", None)
    collection.objects.link(outside)
    outside.location = (10, 0, 0)
    outside.empty_display_type = 'CUBE'

    # Save a deliberate selection so subtree tests also exercise persisted state.
    root.select_set(True)
    bpy.context.view_layer.objects.active = root
    bpy.context.view_layer.update()

    # Make the saved scene easy to inspect when opened in the GUI.
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                area.spaces.active.shading.color_type = 'MATERIAL'
                area.spaces.active.region_3d.view_location = root.location
                area.spaces.active.region_3d.view_distance = 14

    output = Path(__file__).with_name("mesh_hierarchy.blend")
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(output), check_existing=False, compress=True)
    print(f"Created {output} using Blender {bpy.app.version_string}")


if __name__ == "__main__":
    build()
