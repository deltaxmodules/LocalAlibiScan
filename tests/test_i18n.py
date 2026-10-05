"""Fase 9: interface em inglês (por omissão) e português, com os mesmos factos."""

from __future__ import annotations

import json
import re
import sqlite3
import warnings
from pathlib import Path

import pytest
from typer.testing import CliRunner

from localalibiscan import i18n
from localalibiscan.ask import ask
from localalibiscan.cli import app
from localalibiscan.dashboard import build_dashboard
from localalibiscan.detectors.project_kind import VERDICTS
from localalibiscan.drafting import QUESTIONS, generate_overview
from localalibiscan.history import diff_snapshots, list_snapshots
from localalibiscan.html_report import render_html
from localalibiscan.locales import en, pt
from localalibiscan.models import ProjectProfile
from localalibiscan.project import Project
from localalibiscan.render import SECTION_ORDER
from localalibiscan.scan import load_profile, scan

from .conftest import FIXTURES, tree_hash

runner = CliRunner()
SRC = Path(__file__).resolve().parents[1] / "src" / "localalibiscan"


def facts(profile: ProjectProfile) -> list[dict]:
    """O que não pode depender da língua: id, estado, valor e evidências."""
    return [
        {"id": c.id, "status": c.status, "value": c.value, "evidence": [e.model_dump() for e in c.evidence]}
        for c in profile.claims
    ]


# ---------------------------------------------------------------------- escolha da língua


def test_default_is_english() -> None:
    assert i18n.current() == "en"
    assert i18n.t("verdict.not_a_project") == "not a software project"


def test_precedence_option_env_config(tmp_path: Path, monkeypatch) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text('[ui]\nlanguage = "pt"\n', encoding="utf-8")
    monkeypatch.setenv("LOCALALIBI_CONFIG", str(cfg))
    assert i18n.current() == "pt"  # configuração
    monkeypatch.setenv("LOCALALIBI_LANG", "en_US.UTF-8")
    assert i18n.current() == "en"  # o ambiente ganha à configuração
    i18n.set_language("pt")
    assert i18n.current() == "pt"  # a opção ganha a tudo
    i18n.set_language(None)
    assert i18n.current() == "en"


def test_missing_keys_never_crash(monkeypatch) -> None:
    monkeypatch.setitem(i18n.catalog("en"), "only.in.english", "fallback {n}")
    assert i18n.t("only.in.english", lang="pt", n=1) == "fallback 1"
    assert i18n.t("no.such.key") == "no.such.key"
    assert i18n.t("verdict.project", lang="xx") == "software project"  # língua sem catálogo
    assert i18n.t("value.docs_contradiction", doc="X") == "Documentation says {doc}, code uses {code}"
    assert i18n.tn("diff.files.new", 1, lang="pt") == "1 ficheiro novo"
    assert i18n.tn("diff.files.new", 3) == "3 new files"


def test_lang_ui_option_and_bad_value(fixture_copy) -> None:
    folder = str(FIXTURES / "not_a_project")
    out = runner.invoke(app, ["--lang-ui", "pt", "check", folder]).output
    assert "✗ não é um projeto de software" in out and "0 manifestos conhecidos" in out
    # A opção não fica "colada" para a invocação seguinte.
    assert "✗ not a software project" in runner.invoke(app, ["check", folder]).output
    bad = runner.invoke(app, ["--lang-ui", "fr", "check", folder])
    assert bad.exit_code != 0


# ---------------------------------------------------------------------- verificação da Fase 9


def test_scan_in_both_languages_has_same_facts(fixture_copy, config, monkeypatch) -> None:
    root = fixture_copy("python_fastapi_openai")
    before = tree_hash(root)

    en_out = runner.invoke(app, ["scan", str(root)], env={"COLUMNS": "200"}).output
    en_profile = load_profile(root)
    assert "Main language: Python" in en_out and "External service: OpenAI" in en_out
    assert "Linguagem principal" not in en_out

    pt_out = runner.invoke(app, ["scan", str(root)], env={"COLUMNS": "200", "LOCALALIBI_LANG": "pt"}).output
    pt_profile = load_profile(root)
    assert "Linguagem principal: Python" in pt_out and "Serviço externo: OpenAI" in pt_out
    assert "Main language" not in pt_out

    # Mesmos estados, valores e evidências; o que se grava não depende da língua.
    assert facts(en_profile) == facts(pt_profile)
    for line in ("openai ==1.23.0  ← requirements.txt:3", "main.py:14"):
        assert line in en_out and line in pt_out
    assert tree_hash(root) == before


def test_check_not_a_project_in_english() -> None:
    result = runner.invoke(app, ["check", str(FIXTURES / "not_a_project")])
    assert "✗ not a software project" in result.output
    assert "0 known manifests" in result.output and "no .git folder" in result.output


def test_contradiction_in_both_languages(fixture_copy) -> None:
    root = fixture_copy("node_sqlite_lying_readme")
    en_out = runner.invoke(app, ["scan", str(root), "--only", "docs_vs_code"], env={"COLUMNS": "200"}).output
    pt_out = runner.invoke(
        app, ["scan", str(root), "--only", "docs_vs_code"], env={"COLUMNS": "200", "LOCALALIBI_LANG": "pt"}
    ).output
    assert "⚠ Documentation vs code: Documentation says PostgreSQL, code uses SQLite" in en_out
    assert "⚠ Documentação vs código: Documentação diz PostgreSQL, código usa SQLite" in pt_out
    assert "README.md:8" in en_out and "README.md:8" in pt_out


def _as_old_version(claims: list[dict]) -> list[dict]:
    """Claims como a 0.1.x os gravava: sem chaves e com o texto em português."""
    old = []
    for c in claims:
        c = {k: v for k, v in c.items() if k not in ("label_key", "value_key", "note_key", "params")}
        c["label"] = {"lang.primary": "Linguagem principal", "service.openai": "Serviço externo"}.get(c["id"], c["label"])
        c["evidence"] = [
            {k: v for k, v in e.items() if k not in ("snippet_key", "params")} for e in c["evidence"]
        ]
        old.append(c)
    return old


def test_old_profile_and_history_without_keys_are_shown(fixture_copy, config) -> None:
    root = fixture_copy("python_fastapi_openai")
    scan(root, config)
    project_json = root / ".localalibi" / "project.json"
    data = json.loads(project_json.read_text(encoding="utf-8"))
    data["claims"] = _as_old_version(data["claims"])
    data["version"] = "0.1.2"
    project_json.write_text(json.dumps(data), encoding="utf-8")

    old = load_profile(root)
    assert old is not None and old.get("lang.primary").label_key is None
    html = render_html(build_dashboard(root.parent, config, use_cache=True))
    assert "Linguagem principal" in html  # texto antigo, tal como foi gravado

    with sqlite3.connect(root / ".localalibi" / "history.db") as conn:
        (claims,) = conn.execute("SELECT claims FROM snapshots ORDER BY id DESC LIMIT 1").fetchone()
        conn.execute("UPDATE snapshots SET claims = ?", (json.dumps(_as_old_version(json.loads(claims))),))
    (root / "services" / "ai.py").unlink()
    result = scan(root, config)
    assert result.diff is not None
    texts = [c.text for c in result.diff.all()]
    assert "Service: OpenAI: ✓ confirmed → ≈ inferred" in texts
    assert len(list_snapshots(root)) == 2


def test_changing_language_reuses_the_cache(fixture_copy, config, monkeypatch) -> None:
    root = fixture_copy("projects_root")
    first = build_dashboard(root, config)
    assert first.cached_count == 0
    monkeypatch.setenv("LOCALALIBI_LANG", "pt")
    second = build_dashboard(root, config)
    assert second.cached_count == len(second.rows) == len(first.rows)
    html = render_html(second)
    assert '<html lang="pt">' in html and "Última alteração" in html
    monkeypatch.delenv("LOCALALIBI_LANG")
    assert '<html lang="en">' in render_html(second)


def test_ask_cites_same_line_in_both_languages(fixture_copy, config) -> None:
    root = fixture_copy("python_fastapi_openai")
    profile = scan(root, config).profile
    project = Project(root, config)
    en_ask = ask(project, profile, "Where do we use OpenAI?", None)
    pt_ask = ask(project, profile, "Onde usamos OpenAI?", None)
    cites = lambda r: {c for e in r.excerpts if e.file == "services/ai.py" for c in e.citations()}
    assert cites(en_ask) and cites(en_ask) == cites(pt_ask)


class CapturingModel:
    name = "fake"

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def generate(self, prompt: str, *, system: str | None = None, json_mode: bool = False) -> str:
        self.prompts.append(f"{system}\n{prompt}")
        return json.dumps({"sentences": [{"text": "Uses OpenAI.", "ids": ["service.openai"]}]})


def test_llm_is_asked_in_the_interface_language(fixture_copy, config, monkeypatch) -> None:
    profile = scan(fixture_copy("python_fastapi_openai"), config).profile
    model = CapturingModel()
    generate_overview(profile, model)
    assert "in English" in model.prompts[-1] and "External service: OpenAI" in model.prompts[-1]
    monkeypatch.setenv("LOCALALIBI_LANG", "pt")
    overview = generate_overview(profile, model)
    assert "in European Portuguese" in model.prompts[-1] and "Serviço externo: OpenAI" in model.prompts[-1]
    assert overview.summary is not None and overview.summary.sentences  # o validador não muda


def test_explain_questions_translated(fixture_copy) -> None:
    root = str(fixture_copy("python_fastapi_openai"))
    out = runner.invoke(app, ["explain", root, "--no-llm"]).output
    assert "What does this project do?" in out and "What could not be determined?" in out
    out = runner.invoke(app, ["explain", root, "--no-llm"], env={"LOCALALIBI_LANG": "pt"}).output
    assert "O que faz este projeto?" in out


def test_help_in_english_and_config_template(tmp_path: Path, monkeypatch) -> None:
    out = runner.invoke(app, ["--help"], env={"COLUMNS": "200"}).output
    assert "--lang-ui" in out and "List the files that would be analysed" in out
    assert 'language = "en"' in i18n.t("config.template")
    assert 'language = "pt"' in i18n.t("config.template", lang="pt")


# ---------------------------------------------------------------------- catálogos completos

KEY = r"[a-z_]+(?:\.[a-z_0-9]+)+"
# Textos com ar de chave que não o são (ficheiros e ids de Claims).
NOT_KEYS = frozenset({"config.toml", "history.db", "overview.md", "manifest.files", "files.important"})


def _keys_used_in_code() -> set[str]:
    namespaces = {k.split(".")[0] for k in en.MESSAGES}
    found: set[str] = set()
    for path in SRC.rglob("*.py"):
        if "locales" in path.parts:
            continue
        for key in re.findall(rf'"({KEY})"', path.read_text(encoding="utf-8")):
            if key.split(".")[0] in namespaces:
                found.add(key)
        for key in re.findall(r'\btn\(\s*"([\w.]+)"', path.read_text(encoding="utf-8")):
            found.discard(key)  # base de um plural: existem key.one e key.other
            found.update({f"{key}.one", f"{key}.other"})
    found -= NOT_KEYS
    # Chaves montadas dinamicamente.
    found |= {f"verdict.{v}" for v in VERDICTS}
    found |= {f"section.{s}" for s in SECTION_ORDER}
    found |= {f"question.{q.key}" for q in QUESTIONS}
    found |= {f"status.{s}" for s in ("confirmed", "inferred", "contradiction", "unknown")}
    found |= {f"category.{c}" for c in ("database", "orm", "framework", "service")}
    found |= {f"note.{c}.none" for c in ("database", "framework", "service")}
    found |= {f"noun.{c}" for c in ("service", "database", "orm", "framework")}
    found |= {f"files.skip.{r}" for r in ("too_large", "binary", "symlink", "unreadable")}
    found |= {f"diff.files.{h}.{n}" for h in ("new", "changed", "removed") for n in ("one", "other")}
    found |= {"reason.routes.one", "reason.routes.other", "reason.imported.one", "reason.imported.other"}
    return found


def test_every_key_used_exists_in_english() -> None:
    used = _keys_used_in_code()
    assert len(used) > 150
    missing = sorted(k for k in used if k not in en.MESSAGES and not k.startswith(("dep.", "script.")))
    assert not missing, f"Chaves em falta em locales/en.py: {missing}"


def test_portuguese_catalog_is_complete() -> None:
    missing = sorted(set(en.MESSAGES) - set(pt.MESSAGES))
    if missing:  # aviso, não falha: o português cai para o inglês
        warnings.warn(f"Chaves em falta em locales/pt.py: {missing}")
    assert not set(pt.MESSAGES) - set(en.MESSAGES), "chaves em pt que não existem em en"


@pytest.mark.parametrize("lang", i18n.LANGUAGES)
def test_placeholders_match_english(lang: str) -> None:
    fields = lambda s: set(re.findall(r"\{(\w+)\}", s))
    cat = i18n.catalog(lang)
    for key, text in en.MESSAGES.items():
        if key in cat and key != "config.template":
            assert fields(cat[key]) == fields(text), f"{lang}:{key}"
            # "lang" é o argumento de t() que escolhe a língua: não pode ser um marcador.
            assert "lang" not in fields(text), key
