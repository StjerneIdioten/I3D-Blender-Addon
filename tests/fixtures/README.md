# Blender scene fixtures

Add small `.blend` files here only when a test case is difficult to build in Python.
Prefer creating simple scenes directly in the test, so their setup stays reviewable.

Create saved fixtures with the oldest supported Blender release (currently 4.5).
Tests can load them with the shared `load_blend` fixture.

Do not embed executable test scripts or proprietary GIANTS/game data in fixtures.

## Initial smoke fixture

`basic_scene.blend` is a small scene saved in Blender 4.5, containing one Empty
named `FixtureRoot` at location `(1, 2, 3)`. `test_fixture.py` checks that the
file loads correctly, including in newer Blender releases.

To recreate it, open Blender 4.5, start with an empty scene, add an Empty, set
its name and location as above, and save the file in this directory.
