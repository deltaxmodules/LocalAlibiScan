from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from localalibiscan.detectors.project_kind import classify

from .conftest import FIXTURES


def test_not_a_project(fixture_copy, config) -> None:
    kind = classify(fixture_copy("not_a_project"), config)
    assert kind.verdict == "not_a_project"
    assert kind.claim.status == "confirmed"
    snippets = [e.snippet for e in kind.claim.evidence]
    assert "0 known manifests" in snippets
    assert "no .git folder" in snippets
    assert any("0 of 6 files (0%)" in s for s in snippets)


def test_projects_root(fixture_copy, config) -> None:
    root = fixture_copy("projects_root")
    kind = classify(root, config)
    assert kind.verdict == "root"
    assert [p.name for p in kind.subprojects] == ["alpha_api", "beta_web", "delta_tool", "gamma_cli"]
    files = [e.file for e in kind.claim.evidence]
    assert "alpha_api/.git" in files  # com git, a prova é o .git
    assert "delta_tool/Cargo.toml" in files  # sem git, a prova é o manifesto


def test_subfolder_points_to_root(fixture_copy, config) -> None:
    root = fixture_copy("node_sqlite_lying_readme")
    kind = classify(root / "src", config)
    assert kind.verdict == "subfolder"
    assert kind.project_root == root.resolve()
    assert kind.claim.evidence[0].file == "../package.json"

    deeper = classify(root / "src" / "db", config)
    assert deeper.verdict == "subfolder"
    assert deeper.claim.evidence[0].file == "../../package.json"


def test_subfolder_search_limited_to_max_up(fixture_copy, config) -> None:
    root = fixture_copy("node_sqlite_lying_readme")
    deep = root / "a" / "b" / "c"
    deep.mkdir(parents=True)
    assert classify(deep, replace(config, subfolder_max_up=2)).verdict == "not_a_project"
    assert classify(deep, replace(config, subfolder_max_up=3)).verdict == "subfolder"


def test_subfolder_search_never_reaches_home(tmp_path: Path, config) -> None:
    home = tmp_path / "home"
    (home / "docs").mkdir(parents=True)
    (home / ".git").mkdir()  # repositório de dotfiles na pasta pessoal
    kind = classify(home / "docs", replace(config, home_dir=home))
    assert kind.verdict == "not_a_project"


def test_ceiling_marker_stops_search() -> None:
    # As fixtures vivem dentro do repositório do LocalAlibiScan; o marcador
    # .localalibi-ceiling impede que sejam vistas como subpastas dele.
    assert classify(FIXTURES / "not_a_project").verdict == "not_a_project"
    assert classify(FIXTURES / "loose_scripts").verdict == "probable_project"


def test_probable_project(fixture_copy, config) -> None:
    kind = classify(fixture_copy("loose_scripts"), config)
    assert kind.verdict == "probable_project"
    assert kind.claim.status == "inferred"
    assert kind.analyzable


def test_project_by_manifest_or_git(fixture_copy, config) -> None:
    assert classify(fixture_copy("python_fastapi_openai"), config).verdict == "project"
    empty = classify(fixture_copy("empty_project"), config)
    assert empty.verdict == "project"
    assert empty.claim.evidence[0].file == ".git"


def test_monorepo_is_a_project_not_a_root(fixture_copy, config) -> None:
    assert classify(fixture_copy("monorepo_mixed"), config).verdict == "project"


def test_root_depth_limit(tmp_path: Path, config) -> None:
    base = tmp_path / "base"
    for name in ("one", "two"):
        (base / "lvl1" / "lvl2" / name).mkdir(parents=True)
        (base / "lvl1" / "lvl2" / name / "go.mod").write_text("module x\n")
    assert classify(base, config).verdict != "root"
    assert classify(base, replace(config, root_max_depth=3)).verdict == "root"


def test_thresholds_come_from_config(fixture_copy, config) -> None:
    folder = fixture_copy("loose_scripts")
    assert classify(folder, replace(config, probable_min_code_files=5)).verdict == "not_a_project"
