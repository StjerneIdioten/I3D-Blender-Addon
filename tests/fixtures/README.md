# Blender scene fixtures

Add small `.blend` files here only when a test case is difficult to build in Python.
Prefer creating simple scenes directly in the test, so their setup stays reviewable.

Create saved fixtures with the oldest supported Blender release (currently 4.5).
Tests can load them with the shared `load_blend` fixture.

Do not embed executable test scripts or proprietary GIANTS/game data in fixtures.
