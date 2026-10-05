from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from localalibiscan.cli import app
from localalibiscan.scan import load_profile, scan

from .conftest import ALL_FIXTURES, FIXTURES, tree_hash

runner = CliRunner()


def invoke(*args: str):
    return runner.invoke(app, list(args), env={"COLUMNS": "200"})


def test_help_lists_phase1_commands() -> None:
    out = invoke("--help").output
    for cmd in ("files", "check", "scan"):
        assert cmd in out


def test_check_not_a_project() -> None:
    result = invoke("check", str(FIXTURES / "not_a_project"))
    assert result.exit_code == 0
    assert "✗ not a software project" in result.output
    assert "0 known manifests" in result.output


def test_scan_not_a_project_stops(fixture_copy) -> None:
    root = fixture_copy("not_a_project")
    result = invoke("scan", str(root))
    assert result.exit_code == 2
    assert "Not analysed" in result.output
    assert not (root / ".localalibi").exists()


def test_check_projects_root() -> None:
    result = invoke("check", str(FIXTURES / "projects_root"))
    assert "folder with several projects" in result.output
    for name in ("alpha_api", "beta_web", "gamma_cli", "delta_tool"):
        assert name in result.output
    assert "las dashboard" in result.output
    assert "notes" not in result.output.replace("projects_root", "")


def test_check_subfolder() -> None:
    result = invoke("check", str(FIXTURES / "node_sqlite_lying_readme" / "src"))
    assert "subfolder of a project" in result.output
    assert "../package.json" in result.output
    assert "las scan" in result.output and "node_sqlite_lying_readme" in result.output


def test_check_and_scan_loose_scripts(fixture_copy) -> None:
    assert "≈ probable project" in invoke("check", str(FIXTURES / "loose_scripts")).output
    result = invoke("scan", str(fixture_copy("loose_scripts")))
    assert result.exit_code == 0
    assert result.output.lstrip().startswith("≈ Probable project")


def test_scan_fastapi(fixture_copy) -> None:
    result = invoke("scan", str(fixture_copy("python_fastapi_openai")))
    assert result.exit_code == 0, result.output
    assert "Main language: Python" in result.output
    assert "openai ==1.23.0  ← requirements.txt:3" in result.output
    assert "Entry points: main.py" in result.output
    assert "main.py:14" in result.output


def test_scan_empty_project_shows_unknowns(fixture_copy) -> None:
    result = invoke("scan", str(fixture_copy("empty_project")))
    assert result.exit_code == 0, result.output
    assert "? Main language: not determined" in result.output
    assert "? Entry points: not determined" in result.output


def test_scan_force(fixture_copy) -> None:
    result = invoke("scan", "--force", str(fixture_copy("not_a_project")))
    assert result.exit_code == 0
    assert "Forced analysis" in result.output


def test_scan_evidence_flag(fixture_copy) -> None:
    root = fixture_copy("python_fastapi_openai")
    short = invoke("scan", str(root)).output
    full = invoke("scan", "--evidence", str(root)).output
    assert "main.py  entry point name" not in short
    assert "main.py  entry point name" in full


def test_project_json_written(fixture_copy, config) -> None:
    root = fixture_copy("python_fastapi_openai")
    result = scan(root, config)
    data = json.loads((root / ".localalibi/project.json").read_text())
    assert data["verdict"] == "project"
    assert (root / ".localalibi/.gitignore").read_text() == "*\n"
    for claim in data["claims"]:
        assert claim["status"] in ("confirmed", "inferred", "contradiction", "unknown")
        if claim["status"] != "unknown":
            assert claim["evidence"]
    assert load_profile(root) == result.profile


@pytest.mark.parametrize("name", ALL_FIXTURES)
def test_scan_is_read_only(fixture_copy, config, name: str) -> None:
    root = fixture_copy(name)
    before = tree_hash(root)
    scan(root, config, force=True)
    assert tree_hash(root) == before


def test_scan_only_sections(fixture_copy) -> None:
    root = fixture_copy("node_sqlite_lying_readme")
    out = invoke("scan", str(root), "--only", "db,docs-vs-code", "--evidence").output
    assert "Database" in out and "Documentation vs code" in out
    assert "src/db/database.ts:3" in out
    assert "Dependencies" not in out and "Languages" not in out
