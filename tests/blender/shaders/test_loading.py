"""Load original synthetic shader metadata through the real game-data reader."""

import pytest


def test_game_shader_metadata_loads_from_synthetic_installation(addon, game_data, game_file, monkeypatch):
    shader_path = game_file(
        "data/shaders/foundationShader.xml",
        """<CustomShader>
  <Parameters>
    <Parameter name="testGain" type="float" defaultValue="0.25" />
  </Parameters>
</CustomShader>
""",
    )
    parser = addon.ui.shader_parser
    # Isolate mutable cache storage while running the real loader and parser.
    monkeypatch.setattr(parser, "SHADERS_GAME", {})
    parser.populate_game_shaders()

    assert shader_path == game_data / "shaders" / "foundationShader.xml"
    assert addon.utility.fs_builtin_to_disk_path("$data/shaders/foundationShader.xml") == shader_path
    assert set(parser.SHADERS_GAME) == {"foundationShader"}
    shader = parser.SHADERS_GAME["foundationShader"]
    assert shader.path == shader_path
    assert shader.param_lookup["testGain"].default_value == pytest.approx([0.25])
