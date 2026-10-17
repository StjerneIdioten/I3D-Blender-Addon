# Running tests

Tests use the **installed Blender extension**, not a source-only import. The
extension is installed as `bl_ext.user_default.i3dio`. No Farming Simulator
installation or GIANTS converter is needed for the initial tests.

## Local setup (PowerShell, from repository root)

### Python development environment

Use Python 3.11 (the version bundled with the minimum supported Blender 4.5)
for the editor and development tools. Create `.venv` once if it does not exist,
then activate it and install the development requirements:

```powershell
py -3.11 -m venv .venv
. .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install --upgrade -r requirements-dev.txt
```

Select `.venv/Scripts/python.exe` as your editor's Python interpreter.
`requirements-dev.txt` includes the Blender 5.2 completion stubs from
`addon/requirements.txt`, Ruff, and pytest. When migrating an existing environment,
uninstall `fake-bpy-module-4.3` and `fake-bpy-module-latest` before installing the
requirements: different stub packages provide overlapping modules.

The [versioned 5.2 stubs](https://pypi.org/project/fake-bpy-module-5.2/) target
Blender 5.2. The unversioned/`latest` packages follow Blender's development builds.
Stubs provide editor completion; the integration tests need the real `bpy` inside
Blender. Activating `.venv` does not install Blender or put `blender.exe` on PATH.

The VS Code workspace suppresses Pylance's `reportMissingModuleSource` diagnostic:
Blender modules such as `bpy` and `mathutils` have completion stubs in `.venv`,
while their runtime implementations are supplied by Blender. Completion and
unresolved-import checks remain enabled.

### Build, install, and test in Blender

Use the full path to your installed Blender executable. PowerShell's `&` runs
the path stored in `$blender`, including paths with spaces. Change `5.2` to `4.5`
in both paths below to test the minimum supported version.

```powershell
$blender = 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
$env:BLENDER_USER_RESOURCES = "$PWD/.blender/tests/5.2"

New-Item -ItemType Directory -Force dist | Out-Null
& $blender --command extension build --source-dir addon/i3dio --output-dir dist
& $blender --command extension install-file --repo user_default --enable dist/i3dio-0.0.0.zip
python -m pip install --upgrade --target tests/.deps "pytest>=8,<10"
& $blender --background --python-exit-code 1 --python tests/run_blender.py
```

`BLENDER_USER_RESOURCES` keeps the test extension and preferences in this
repository's ignored `.blender/tests/` directory. Use the same setting for every
Blender command in the test session. Existing `BLENDER_USER_CONFIG`,
`BLENDER_USER_SCRIPTS`, or `BLENDER_USER_EXTENSIONS` environment variables override
it; unset those first if you have configured them.

`tests/.deps` contains pytest and its dependencies for Blender's own Python to
import. Keep the completion stubs in `.venv`; do not add the venv's site-packages
to Blender's Python path.

With no game-data path configured, startup can log missing collision-mask files
and shader directories. Those messages do not prevent these initial tests from
passing without Farming Simulator installed.

After editing add-on code, repeat the build and install commands before testing.
Remove the temporary profile override with
`Remove-Item Env:BLENDER_USER_RESOURCES` when finished, or close the terminal.

To run one feature area or one test:

```powershell
& $blender --background --python-exit-code 1 --python tests/run_blender.py -- -q tests/blender/export
& $blender --background --python-exit-code 1 --python tests/run_blender.py -- -q tests/blender/export/test_meshes.py::test_mesh_raw_i3d_export
```

Arguments after `--` are passed to pytest. Options alone still use the Blender
suite; explicit file paths or test node IDs select only those tests. Paths are
resolved from the repository root, including when the runner is invoked elsewhere.

```powershell
& $blender --background --python-exit-code 1 --python tests/run_blender.py -- -q -k mesh
```

To check the test code's style in the activated venv:

```powershell
python -m ruff check tests
python -m ruff format --check tests
```

## Test layout

Organize tests by runtime, then feature, then behavior:

```text
tests/
  blender/
    conftest.py                 # Fixtures shared across all Blender features
    export/
      test_meshes.py            # Geometry and material references
      test_repeated_export.py   # Multiple exports in one session
      test_saved_scene.py       # Persisted hierarchy, UVs, instances, modifiers
      test_transform_groups.py  # Empty objects / TransformGroups
    extension/
      test_registration.py      # Installation, registration, Blender operators
    harness/
      test_fixtures.py          # The test infrastructure itself
      test_game_data.py         # Synthetic installation/files and preferences
    shaders/
      test_loading.py           # Shader metadata from original test XML
    utility/
      test_comparisons.py       # Numeric/vector comparisons
      test_paths.py             # Game-data path handling
  fixtures/
    export/
      mesh_hierarchy.blend
      build_mesh_hierarchy.py   # Regenerate with Blender 4.5
    README.md
  run_blender.py
```

The Blender runner discovers every `test_*.py` file under `tests/blender/`,
including new subdirectories, without a test list or runner changes. Pytest uses
`importlib` import mode so separate feature folders can reuse filenames safely.
Add `tests/unit/` when we have Blender-independent tests.
Run those directly with `python -m pytest tests/unit` in the venv. Blender fixtures
are scoped to `tests/blender/conftest.py`, so they do not affect pure-Python tests.

To list the available tests and their full selectable paths:

```powershell
& $blender --background --python-exit-code 1 --python tests/run_blender.py -- --collect-only -q
```

### Adding cases as the suite grows

- Put new cases beside the feature they exercise. For example, selection behavior
  belongs in `export/test_selection.py`, UV export in `export/test_uvs.py`, and
  material export in `export/test_materials.py`. Create these files as cases arise.
- Keep each module focused on one behavior area. Split it when it covers several
  distinct topics, rather than making one file per test or collecting everything
  into `test_export.py` or `test_utility.py`. Add another directory level when an
  area grows into several related modules.
- Name tests after the behavior and relevant condition, for example
  `test_child_keeps_world_transform_when_parent_is_not_exported`. Keep bug
  regressions with their feature; record the issue number in a comment/docstring.
- Parametrize cases that share the same setup and assertion, giving parameters
  descriptive IDs so failures identify the variant.
- Keep a fixture in its test module while it has one consumer. Share feature-only
  fixtures through that directory's `conftest.py`; promote fixtures to
  `blender/conftest.py` when multiple areas need them. Tests inherit parent fixtures
  automatically and should not import them or import another test module.
- Put saved scenes under the matching feature in `tests/fixtures/` and load them
  by relative path, such as `load_blend("export/selection_hierarchy.blend")`.

## Shared Blender fixtures

Every test in `tests/blender/` starts and finishes with an empty factory scene.
The `blender_state` autouse fixture resets scene settings and all data blocks,
including data loaded from `.blend` files, while preserving the installed
extension and user preferences. Tests can freely modify scene data within a test.
Use pytest's `monkeypatch` fixture to restore other preferences or module globals
that a test changes.

| Fixture | Purpose |
| --- | --- |
| `addon` | Enable and import the installed extension once per session. |
| `empty_scene` | Return the fresh current scene. |
| `game_data` | Configure a temporary `game/data/` folder with sibling `game/shared/`, clear the converter path, and restore both preferences afterward. |
| `game_file(path, content)` | Write original text or bytes relative to the temporary game installation root. |
| `load_blend(name)` | Load a scene from `tests/fixtures/`; return the newly loaded scene. |
| `addon_log` | Capture the add-on's non-propagating logger through pytest's `caplog`. |
| `export_i3d(**options)` | Export the current scene, validate success, and return the output paths and parsed XML. |

`export_i3d` uses a new file for every call, so repeated exports cannot pass by
reading stale output. Defaults are raw I3D, all objects, no file copying, and a
debug log beside the output. Keyword arguments override operator settings.
The helper supplies `game_data` and `addon_log` automatically and rejects logged
exporter errors as well as missing or invalid I3D output. Use the operator directly
when testing expected failures.

```python
def test_root_name(empty_scene, export_i3d):
    import bpy

    obj = bpy.data.objects.new("Root", None)
    empty_scene.collection.objects.link(obj)
    result = export_i3d(selection="ALL")

    assert result.root.find("Scene/TransformGroup[@name='Root']") is not None
    assert result.path.is_file()
    assert result.log_path.is_file()
```

After `load_blend(...)`, use the returned scene or `bpy.context.scene`; loading a
file invalidates previously held scene/object references. Prefer focused XML
assertions and `pytest.approx` for numeric values rather than whole-file snapshots.

The committed `export/mesh_hierarchy.blend` exercises saved mesh/UV data, linked
instances with material overrides, hierarchy/transforms, modifiers, and selection.
Its generator and expected behavior are documented in
[`tests/fixtures/README.md`](tests/fixtures/README.md).

## Game-data-dependent tests

The default suite uses synthetic game files, with only the content needed for
each case. `game_data` configures an otherwise empty temporary installation:

```text
<test temporary directory>/game/
  data/       # The configured FS data folder: shaders/, shared/detailLibrary/, ...
  shared/     # Sibling folder used by the collision-data reader
```

Use `game_file` to write original XML or binary content into that layout. It
creates parent directories and keeps writes inside the temporary installation:

```python
shader_path = game_file(
    "data/shaders/testShader.xml",
    '<CustomShader><Parameters><Parameter name="testGain" type="float" '
    'defaultValue="0.25" /></Parameters></CustomShader>',
)
```

This XML exercises metadata loading; it is not intended to be a renderable game
shader. Create texture test images with Blender when a case needs actual image
decoding, and author small material/collision XML examples for their specific
parsers. Keep feature-specific builders in that feature's `conftest.py` as needed.
Do not copy game assets into the repository or download/install the game in CI.

Changing the preference or writing a file does not automatically refresh every
module cache. Tests of cached readers should call the relevant loader after
creating their files and isolate mutable cache storage with `monkeypatch`.
See `tests/blender/shaders/test_loading.py` for an example that uses the real
shader loader with a temporary cache dictionary.

The synthetic suite checks our handling of these inputs, not compatibility with
every file shipped by a game version. Tests requiring a real installation can
be added later as a separate, explicitly opted-in local suite; the normal CI
suite should continue to use synthetic data.

The preferences fixture uses `addon.__package__`: `addon` is the imported root
extension package, so its `__package__` and `__name__` both identify the installed
extension (currently `bl_ext.user_default.i3dio`). Bare `__package__` in a test
module identifies the tests package instead and must not be used for this lookup.

## Failure diagnostics

GitHub Actions keeps a `blender-<matrix.version>-failure` artifact when a test run
fails. It contains the Blender console log, a JUnit report, and pytest's
temporary files, including any generated I3D files and export logs. Jobs have a
20-minute timeout.

To keep the same report and temporary-file layout locally:

```powershell
New-Item -ItemType Directory -Force tests/.results | Out-Null
& $blender --background --python-exit-code 1 --python tests/run_blender.py -- --junitxml=tests/.results/junit.xml --basetemp=tests/.results/tmp
```

`tests/.results/` is ignored by Git. `--basetemp` replaces the contents of its
temporary directory on each run; copy any diagnostics you want to keep first.

## Writing tests

- Use Python-created Blender scenes for straightforward cases.
- Put intricate `.blend` fixtures in `tests/fixtures/`, saved in Blender 4.5.
- Use `load_blend("feature/example.blend")` for a saved scene.
- Use `empty_scene` and `export_i3d` for scene/export tests, or request `game_data`
  when a test needs only the temporary game-data path.
- Never require the proprietary converter in cross-platform/raw-export tests.

GitHub Actions builds the extension and tests it on Windows using Blender 4.5
and the latest stable release. Each Blender job sets `BLENDER_USER_RESOURCES`
to `<workspace>/.blender/tests/<matrix.version>` for all steps, matching the local
profile layout (`4.5` or `latest` in CI). Linux/macOS installed-extension jobs can
be added after those platforms are declared and verified in the add-on manifest.
