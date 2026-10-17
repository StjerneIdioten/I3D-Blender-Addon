"""Run the test suite inside Blender's Python interpreter.

Example:
    blender --background --python-exit-code 1 --python tests/run_blender.py
"""

import os
import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS / ".deps"))

try:
    import bpy
except ImportError:
    raise SystemExit(
        "Run with Blender: blender --background --python-exit-code 1 --python tests/run_blender.py"
    ) from None

import pytest  # noqa: E402

if __name__ == "__main__":
    os.chdir(TESTS.parent)
    print(f"Blender {bpy.app.version_string}; Python {sys.version.split()[0]}", flush=True)
    args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    # Keep the default suite even with options such as -q/-k, while letting pytest
    # handle explicit file paths and node IDs without also collecting the full suite.
    raise SystemExit(pytest.main(["-o", "testpaths=tests/blender", *args]))
