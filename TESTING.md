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

To select one test:

```powershell
& $blender --background --python-exit-code 1 --python tests/run_blender.py -- -q tests/blender/test_export.py
```

To check the test code's style in the activated venv:

```powershell
python -m ruff check tests
python -m ruff format --check tests
```

## Test layout

Blender-dependent tests live in `tests/blender/`, including their `conftest.py`
fixtures. The test runner defaults to this folder so later pure-Python tests
can be run separately without importing `bpy`. Keep `.blend` scenes in
`tests/fixtures/`; add `tests/unit/` when we have Blender-independent tests.

## Writing tests

- Use Python-created Blender scenes for straightforward cases.
- Put intricate `.blend` fixtures in `tests/fixtures/`, saved in Blender 4.5.
- Use `load_blend("example.blend")` for a saved scene.
- Use `empty_scene` and `game_data` fixtures to avoid leaking scene state or
  depending on proprietary game resources.
- Never require the proprietary converter in cross-platform/raw-export tests.

GitHub Actions builds the extension and tests it on Windows using Blender 4.5
and the latest stable release. Each Blender job sets `BLENDER_USER_RESOURCES`
to `<workspace>/.blender/tests/<matrix.version>` for all steps, matching the local
profile layout (`4.5` or `latest` in CI). Linux/macOS installed-extension jobs can
be added after those platforms are declared and verified in the add-on manifest.
