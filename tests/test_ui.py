"""Fase 10: interface gráfica local (Streamlit, opcional)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from localalibiscan import cli
from localalibiscan.cli import UI_FLAGS, app, ui_command

from .conftest import FIXTURES, tree_hash

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from localalibiscan import ui  # noqa: E402
from localalibiscan.models import Evidence  # noqa: E402
from localalibiscan.project import Project  # noqa: E402

runner = CliRunner()
UI_SCRIPT = Path(ui.__file__)


def run_app(folder: Path, **state) -> AppTest:
    at = AppTest.from_file(str(UI_SCRIPT), default_timeout=120)
    at.session_state["folder"] = str(folder)
    for key, value in state.items():
        at.session_state[key] = value
    at.run()
    assert not at.exception, at.exception
    return at


# ---------------------------------------------------------------------- comando `las ui`


def test_ui_command_pins_network_rules() -> None:
    cmd = ui_command(Path("/x"), 9000)
    assert cmd[:4] == [sys.executable, "-m", "streamlit", "run"]
    assert Path(cmd[4]) == UI_SCRIPT
    assert "--server.address=127.0.0.1" in cmd
    assert "--browser.gatherUsageStats=false" in cmd
    assert "--server.headless=true" in cmd
    assert "--server.port=9000" in cmd
    assert cmd[-2:] == ["--", str(Path("/x"))]
    assert dict(UI_FLAGS)["server.address"] == "127.0.0.1"


def test_las_ui_runs_streamlit_outside_the_project(monkeypatch, tmp_path) -> None:
    calls = []
    monkeypatch.setattr("subprocess.run", lambda cmd, **kw: calls.append((cmd, kw)))
    monkeypatch.setattr(cli, "load_config", lambda: _cfg(tmp_path))
    folder = FIXTURES / "python_fastapi_openai"
    result = runner.invoke(app, ["ui", str(folder), "--no-browser", "--port", "8600"])
    assert result.exit_code == 0, result.output
    assert "127.0.0.1:8600" in result.output
    (cmd, kw), = calls
    assert cmd[-1] == str(folder.resolve())
    assert kw["cwd"] == tmp_path / "user_cfg"  # nunca a pasta do projeto analisado
    assert kw["env"]["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] == "false"


def _cfg(tmp_path: Path):
    from dataclasses import replace

    from localalibiscan.config import load_config

    return replace(load_config(), user_config_dir=tmp_path / "user_cfg")


def test_las_ui_without_streamlit_explains_the_extra(monkeypatch) -> None:
    import importlib.util

    real = importlib.util.find_spec
    monkeypatch.setattr(importlib.util, "find_spec", lambda name, *a: None if name == "streamlit" else real(name, *a))
    result = runner.invoke(app, ["ui", str(FIXTURES / "python_fastapi_openai")])
    assert result.exit_code == 2
    assert "localalibiscan[ui]" in result.output


def test_no_raw_html_in_the_interface() -> None:
    source = UI_SCRIPT.read_text(encoding="utf-8")
    assert "unsafe_allow_html" not in source
    assert "st.html" not in source


# ---------------------------------------------------------------------- ajudas puras


def test_markdown_from_the_project_is_escaped() -> None:
    hostile = "![x](http://example.com/a.png) <img src=x> :red[hi] $x$ **b**"
    out = ui.md(hostile)
    # Cada carácter com significado vem escapado; sem as barras, o texto é o original.
    assert re.search(r"(?<!\\)[!\[\]()<>:$*]", out) is None
    assert out.replace("\\", "") == hostile
    assert ui.md("a\nb") == "a b"


def test_excerpt_marks_the_cited_line() -> None:
    project = Project(FIXTURES / "python_fastapi_openai")
    text = ui.excerpt(project, Evidence(file="services/ai.py", line=1, kind="code"))
    assert text is not None and text.splitlines()[0].startswith("→    1 │")
    assert ui.excerpt(project, Evidence(file="services/ai.py", line=None, kind="file")) is None
    assert ui.excerpt(project, Evidence(file="services/ai.py", line=99999, kind="code")) is None


# ---------------------------------------------------------------------- a app


def test_dashboard_lists_projects_and_opens_one(fixture_copy) -> None:
    root = fixture_copy("projects_root")
    before = tree_hash(root)
    at = run_app(root)
    names = list(at.dataframe[0].value.iloc[:, 0])
    assert sorted(names) == ["alpha_api", "beta_web", "delta_tool", "gamma_cli"]

    at.selectbox(key="project").select("alpha_api").run()
    assert not at.exception
    assert any("alpha_api" in h.value.replace("\\", "") for h in at.header)
    assert [t.label for t in at.tabs] == ["Profile", "What changed", "Explain", "Ask"]
    assert tree_hash(root) == before


def test_project_profile_ask_and_explain_without_llm(fixture_copy) -> None:
    root = fixture_copy("python_fastapi_openai")
    before = tree_hash(root)
    at = run_app(root, use_llm=False)
    text = " ".join(m.value for m in at.markdown)
    assert "OpenAI" in text

    at.text_input(key=f"q:ask:{root.resolve()}").input("Where do we use OpenAI?")
    at.button[-1].click().run()  # o botão do formulário de perguntas é o último
    assert not at.exception
    captions = " ".join(c.value for c in at.caption)
    assert "services/ai.py" in captions.replace("\\", "")
    assert any("services" in c.value for c in at.code)

    at.button(key=f"btn:explain:{root.resolve()}:en").click().run()
    assert not at.exception
    assert any("What is this project" in m.value or "What" in m.value for m in at.markdown)
    assert tree_hash(root) == before


def test_interface_in_portuguese(fixture_copy) -> None:
    root = fixture_copy("projects_root")
    at = run_app(root, lang="pt")
    assert at.title[0].value == "Projetos"
    assert "board.col" not in " ".join(at.dataframe[0].value.columns)


def test_not_a_project_shows_the_verdict() -> None:
    at = run_app(FIXTURES / "not_a_project")
    assert any("not a software project" in s.value for s in at.subheader)
