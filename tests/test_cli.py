from __future__ import annotations

import pytest
from typer.testing import CliRunner

from localalibiscan.cli import app

from .conftest import ALL_FIXTURES, FIXTURES, tree_hash

runner = CliRunner()


def test_help_lists_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "files" in result.output


def test_files_lists_without_node_modules() -> None:
    result = runner.invoke(app, ["files", str(FIXTURES / "node_sqlite_lying_readme")])
    assert result.exit_code == 0, result.output
    assert "database.ts" in result.output
    assert "package.json" in result.output
    assert "node_modules" not in result.output


def test_files_rejects_missing_folder(tmp_path) -> None:
    result = runner.invoke(app, ["files", str(tmp_path / "nope")])
    assert result.exit_code != 0


@pytest.mark.parametrize("name", ALL_FIXTURES)
def test_files_is_read_only(fixture_copy, name: str) -> None:
    root = fixture_copy(name)
    before = tree_hash(root)
    result = runner.invoke(app, ["files", str(root)])
    assert result.exit_code == 0, result.output
    assert tree_hash(root) == before
    assert not (root / ".localalibi").exists()


@pytest.mark.parametrize("name", ALL_FIXTURES)
def test_fixture_exists(name: str) -> None:
    assert (FIXTURES / name).is_dir()
    assert any((FIXTURES / name).iterdir())


def test_projects_root_git_setup(fixture_copy) -> None:
    root = fixture_copy("projects_root")
    with_git = sorted(p.parent.name for p in root.glob("*/.git"))
    assert with_git == ["alpha_api", "beta_web", "gamma_cli"]
    assert (root / "delta_tool/Cargo.toml").exists()
