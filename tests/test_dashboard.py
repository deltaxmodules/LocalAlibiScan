from __future__ import annotations

import os
import re
import shutil
import time
from pathlib import Path

from typer.testing import CliRunner

from localalibiscan.cli import app
from localalibiscan.dashboard import build_dashboard
from localalibiscan.html_report import render_html

from .conftest import FIXTURES, tree_hash

runner = CliRunner()


def test_finds_four_projects_including_one_without_git(fixture_copy, config) -> None:
    root = fixture_copy("projects_root")
    board = build_dashboard(root, config)
    assert [r.name for r in sorted(board.rows, key=lambda r: r.name)] == [
        "alpha_api", "beta_web", "delta_tool", "gamma_cli",
    ]
    rows = {r.name: r for r in board.rows}
    assert rows["alpha_api"].profile.last_change_source == "git"
    assert rows["alpha_api"].profile.git_head
    assert rows["delta_tool"].profile.git_head is None
    assert rows["delta_tool"].project_type == "Rust"
    assert rows["beta_web"].stack == ["Fastify"]
    assert rows["alpha_api"].stack == ["Flask"]


def test_whole_fixtures_folder(tmp_path: Path, config) -> None:
    root = tmp_path / "fx"
    shutil.copytree(FIXTURES, root, ignore=shutil.ignore_patterns(".localalibi"))
    board = build_dashboard(root, config, depth=2)
    rows = {r.name: r for r in board.rows}
    # monorepo conta como um só; não desce dentro de projetos; empty_project e
    # not_a_project não são projetos (sem git na cópia)
    assert "monorepo_mixed" in rows and "monorepo_mixed/frontend" not in rows
    assert rows["loose_scripts"].verdict == "probable_project"
    assert "not_a_project" not in rows and "empty_project" not in rows
    assert "projects_root/alpha_api" in rows
    assert "node_sqlite_lying_readme/src" not in rows
    assert rows["node_sqlite_lying_readme"].databases == ["SQLite"]
    assert rows["python_dep_unused"].databases == ["≈Redis"]
    assert rows["python_fastapi_openai"].services == ["OpenAI"]


def test_sorted_by_last_change(tmp_path: Path, config) -> None:
    for i, name in enumerate(["old", "new", "mid"]):
        p = tmp_path / "root" / name
        p.mkdir(parents=True)
        (p / "go.mod").write_text("module x\n")
        stamp = 1_700_000_000 + {"old": 0, "mid": 1000, "new": 2000}[name]
        os.utime(p / "go.mod", (stamp, stamp))
    board = build_dashboard(tmp_path / "root", config)
    assert [r.name for r in board.rows] == ["new", "mid", "old"]


def test_language_filter(tmp_path: Path, config) -> None:
    root = tmp_path / "fx"
    shutil.copytree(FIXTURES / "projects_root", root)
    names = [r.name for r in build_dashboard(root, config, language="go").rows]
    assert names == ["gamma_cli"]


def test_cache_reuse_and_invalidation(tmp_path: Path, config) -> None:
    root = tmp_path / "root"
    for p in range(4):
        for i in range(120):
            f = root / f"proj{p}" / "src" / f"m{i}.ts"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(
                "import express from 'express';\nconst router = express.Router();\n"
                + "".join(f"router.get('/r{i}_{k}', (req, res) => res.json({{ ok: true }}));\n" for k in range(15))
            )
        (root / f"proj{p}" / "package.json").write_text('{\n  "dependencies": {\n    "express": "4"\n  }\n}\n')

    t0 = time.perf_counter()
    first = build_dashboard(root, config)
    t1 = time.perf_counter()
    second = build_dashboard(root, config)
    t2 = time.perf_counter()
    assert first.cached_count == 0
    assert second.cached_count == 4
    assert (t1 - t0) >= 5 * (t2 - t1), f"1.ª {t1 - t0:.3f}s, 2.ª {t2 - t1:.3f}s"

    # alterar um ficheiro invalida só esse projeto
    (root / "proj2" / "src" / "m0.ts").write_text("export const x = 1;\n")
    third = build_dashboard(root, config)
    assert third.cached_count == 3
    assert not next(r for r in third.rows if r.name == "proj2").cached


def test_dashboard_is_read_only(fixture_copy, config) -> None:
    root = fixture_copy("projects_root")
    before = tree_hash(root)
    build_dashboard(root, config)
    assert tree_hash(root) == before


def test_html_is_self_contained(fixture_copy, config) -> None:
    board = build_dashboard(fixture_copy("projects_root"), config)
    page = render_html(board)
    assert page.startswith("<!doctype html>")
    assert not re.search(r"<(script|link|img|iframe)[^>]+(src|href)=\"(?!data:)", page)
    assert "@import" not in page and "url(" not in page
    for name in ("alpha_api", "beta_web", "gamma_cli", "delta_tool"):
        assert name in page
    assert "pyproject.toml:5" in page  # evidência de cada afirmação no detalhe


def test_html_escapes_content(tmp_path: Path, config) -> None:
    root = tmp_path / "root"
    for name in ("one", "two"):
        (root / name).mkdir(parents=True)
        (root / name / "package.json").write_text('{\n  "dependencies": {\n    "express": "4"\n  }\n}\n')
    (root / "one" / "server.js").write_text(
        "const express = require('express');\nconst app = express();\n"
        "app.get('/<script>alert(1)</script>', (req, res) => res.end());\n"
    )
    page = render_html(build_dashboard(root, config))
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page


def test_cli_dashboard_html(fixture_copy, tmp_path: Path, monkeypatch) -> None:
    import localalibiscan.cli as cli
    from dataclasses import replace

    from localalibiscan.config import load_config

    cfg = replace(load_config(), user_config_dir=tmp_path / "cfg", home_dir=tmp_path)
    monkeypatch.setattr(cli, "load_config", lambda: cfg)
    root = fixture_copy("projects_root")
    result = runner.invoke(app, ["dashboard", str(root), "--html"], env={"COLUMNS": "200"})
    assert result.exit_code == 0, result.output
    for name in ("alpha_api", "beta_web", "gamma_cli", "delta_tool"):
        assert name in result.output
    assert (tmp_path / "cfg" / "dashboard.html").is_file()


def test_cli_dashboard_on_a_project_shows_profile(fixture_copy) -> None:
    root = fixture_copy("python_fastapi_openai")
    result = runner.invoke(app, ["dashboard", str(root)], env={"COLUMNS": "200"})
    assert result.exit_code == 0
    assert "External service: OpenAI" in result.output
    assert "las scan" in result.output


def test_cli_dashboard_nothing_found(fixture_copy) -> None:
    result = runner.invoke(app, ["dashboard", str(fixture_copy("not_a_project"))], env={"COLUMNS": "200"})
    assert result.exit_code == 2
    assert "No projects found" in result.output


def test_deep_root_inside_dashboard_is_expanded(tmp_path: Path, config) -> None:
    # raiz/a/b é um contentor de projetos mais fundo do que --depth
    root = tmp_path / "root"
    for name in ("p1", "p2"):
        (root / "a" / "b" / "mods" / name).mkdir(parents=True)
        (root / "a" / "b" / "mods" / name / "go.mod").write_text("module x\n")
    (root / "other").mkdir()
    (root / "other" / "go.mod").write_text("module y\n")
    board = build_dashboard(root, config, depth=2)
    assert sorted(r.name for r in board.rows) == ["a/b/mods/p1", "a/b/mods/p2", "other"]
    assert all(r.profile for r in board.rows)
