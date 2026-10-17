"""Run the test suite inside Blender's Python interpreter.

Example:
    blender --background --python-exit-code 1 --python tests/run_blender.py
"""

import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS / ".deps"))

import pytest  # noqa: E402

if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [str(TESTS / "blender")]
    raise SystemExit(pytest.main(args))
