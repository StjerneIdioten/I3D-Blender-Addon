# Blender scene fixtures

Use small `.blend` files for cases that exercise persisted scene data, linked
data blocks, or setups that are awkward to reproduce in each test. Prefer creating
simple, independent scenes directly in tests so their setup stays reviewable.

Create saved fixtures with the oldest supported Blender release (currently 4.5).
Tests can load them with the shared `load_blend` fixture.

Group scenes by the feature that owns them, matching the test areas. For example,
`export/selection_hierarchy.blend` would support export selection tests and be
loaded with `load_blend("export/selection_hierarchy.blend")`. Add the folder when
its first saved scene is needed. Describe each scene's purpose and how to recreate
it here, or in a feature README when that area has several scenes.

Do not embed executable test scripts or proprietary GIANTS/game data in fixtures.

## Export: mesh hierarchy

`export/mesh_hierarchy.blend` is saved with Blender 4.5 and contains a small,
self-contained assembly. It uses three plain-color materials and no game assets,
external textures, embedded scripts, or add-on-specific settings.

| Object | Persisted setup | Export behavior checked |
| --- | --- | --- |
| `FixtureRoot` | Empty at `(2, 4, 6)`, rotated 90 degrees around Blender Z; scene unit scale `0.5` | Parent hierarchy, axis conversion, unit scaling, local child transforms |
| `Panel` | Two adjacent quads with a UV seam and red/blue material slots | Quad triangulation, UV coordinates, material subsets |
| `PanelInstance` | Shares `Panel`'s mesh; local scale `(0.5, 1.5, 2)` and a green object-level material override | Shared shape references, per-instance materials, transformed instances |
| `SolidPanel` | One quad with an unapplied Solidify modifier, thickness `0.5`, offset `1` | Evaluated mesh produces 12 triangles; disabling modifiers produces 2, leaving source mesh/modifier unchanged |
| `OutsideHierarchy` | Unrelated Empty; only `FixtureRoot` is selected in the saved file | Selected subtree includes children and excludes unrelated objects; root-only selection exports no mesh |

`tests/blender/export/test_saved_scene.py` loads the committed file and checks
the actual exported XML on every supported CI Blender version. It checks numeric
values with tolerances and follows shape/material IDs instead of relying on
fixed IDs or whole-file snapshots. The harness also loads this file to verify
that its scene data is cleaned up between tests.

Regenerate the fixture from its reviewable source with **Blender 4.5**, from the
repository root:

```powershell
$blender45 = 'C:\Program Files\Blender Foundation\Blender 4.5\blender.exe'
& $blender45 --background --factory-startup --python-exit-code 1 --python tests/fixtures/export/build_mesh_hierarchy.py
```

The builder refuses newer Blender versions, recreates the scene, and saves the
`.blend` beside itself. It does not require the add-on to be installed. Keep its
data definitions and the test expectations explicit so changes to the fixture
are reviewable; update this description when its intended behavior changes.
