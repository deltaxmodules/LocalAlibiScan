from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from localalibiscan.cli import app
from localalibiscan.config import FIXED_EXCLUDED_DIRS, ConfigError, config_template, load_config
from localalibiscan.fs import ProjectFS

runner = CliRunner()


def test_defaults_without_file(tmp_path: Path) -> None:
    cfg = load_config(tmp_path / "missing.toml")
    assert cfg.excluded_dirs == FIXED_EXCLUDED_DIRS
    assert cfg.ollama_model == "qwen2.5-coder:7b"


def test_template_is_valid_and_matches_defaults(tmp_path: Path) -> None:
    f = tmp_path / "config.toml"
    f.write_text(config_template())
    cfg = load_config(f)
    assert cfg.max_file_size == 1024 * 1024
    assert cfg.root_max_depth == 2
    assert cfg.ollama_url == "http://localhost:11434"


def test_file_overrides_and_env_wins(tmp_path: Path, monkeypatch) -> None:
    f = tmp_path / "config.toml"
    f.write_text('[scan]\nignore = ["vendor"]\nmax_file_size = 10\n[ollama]\nmodel = "qwen3:8b"\n[dashboard]\ndepth = 3\n')
    cfg = load_config(f)
    assert "vendor" in cfg.excluded_dirs and "node_modules" in cfg.excluded_dirs
    assert (cfg.max_file_size, cfg.ollama_model, cfg.root_max_depth) == (10, "qwen3:8b", 3)
    monkeypatch.setenv("LOCALALIBI_OLLAMA_MODEL", "other:1b")
    assert load_config(f).ollama_model == "other:1b"


def test_ignore_is_applied_when_walking(tmp_path: Path) -> None:
    f = tmp_path / "config.toml"
    f.write_text('[scan]\nignore = ["vendor"]\n')
    proj = tmp_path / "p"
    (proj / "vendor").mkdir(parents=True)
    (proj / "vendor" / "lib.py").write_text("x")
    (proj / "main.py").write_text("x")
    assert [e.path for e in ProjectFS(proj, load_config(f)).walk()] == ["main.py"]


def test_invalid_file_is_reported(tmp_path: Path) -> None:
    f = tmp_path / "config.toml"
    f.write_text("[scan\n")
    with pytest.raises(ConfigError):
        load_config(f)
    f.write_text('[scan]\nignore = "vendor"\n')
    with pytest.raises(ConfigError):
        load_config(f)


def test_cli_config_init(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "home" / ".localalibi" / "config.toml"
    monkeypatch.setenv("LOCALALIBI_CONFIG", str(target))
    import localalibiscan.cli as cli
    from dataclasses import replace

    monkeypatch.setattr(cli, "load_config", lambda: replace(load_config(target), user_config_dir=target.parent))
    result = runner.invoke(app, ["config", "--init"])
    assert result.exit_code == 0, result.output
    assert target.read_text() == config_template()
    assert runner.invoke(app, ["config", "--init"]).exit_code == 1  # nunca sobrescreve
    shown = runner.invoke(app, ["config"], env={"COLUMNS": "200"}).output
    assert "qwen2.5-coder:7b" in shown and "(exists)" in shown
