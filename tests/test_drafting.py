from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from localalibiscan.cli import app
from localalibiscan.drafting import (
    explain,
    generate_overview,
    overview_markdown,
    structured_to_text,
    validate,
)
from localalibiscan.llm import LLMUnavailable, NotLocal, OllamaClient
from localalibiscan.scan import scan

runner = CliRunner()


class FakeModel:
    """Modelo falso: devolve respostas fixas (com ids inventados de propósito)."""

    name = "fake"

    def __init__(self, overview: object, answers: dict | None = None) -> None:
        self.overview = overview
        self.answers = answers or {}
        self.prompts: list[str] = []

    def generate(self, prompt: str, *, system: str | None = None, json_mode: bool = False) -> str:
        self.prompts.append(prompt)
        if "exatamente estas chaves" in prompt:
            return json.dumps(self.answers)
        return self.overview if isinstance(self.overview, str) else json.dumps(self.overview)


class BrokenModel:
    name = "broken"

    def generate(self, prompt: str, **kw) -> str:
        raise LLMUnavailable("connection refused")


# ------------------------------------------------------------------ validador


def test_validator_keeps_only_valid_citations() -> None:
    text = (
        "Usa SQLite para guardar dados [db.sqlite]. "
        "Também usa Stripe para pagamentos [service.stripe]. "
        "É um projeto excelente. "
        "Arranca com main.py. [entry.points]\n"
        "- Tem rotas [route.GET /health, db.sqlite]\n"
        "# Título que não é frase\n"
        "[db.sqlite]"
    )
    v = validate(text, {"db.sqlite", "entry.points", "route.GET /health"})
    assert [s.render() for s in v.sentences] == [
        "Usa SQLite para guardar dados [db.sqlite].",
        "Arranca com main.py [entry.points].",
        "Tem rotas [route.GET /health, db.sqlite].",
    ]
    reasons = dict(v.removed)
    assert reasons["Também usa Stripe para pagamentos [service.stripe]."] == "id inexistente: service.stripe"
    assert reasons["É um projeto excelente."] == "sem citação"


def test_structured_output_normalizes_bracketed_ids() -> None:
    text = structured_to_text({"sentences": [{"text": "É Python.", "ids": ["[lang.primary]", "`project.type`"]}]})
    v = validate(text, {"lang.primary", "project.type"})
    assert [s.ids for s in v.sentences] == [["lang.primary", "project.type"]]


# ------------------------------------------------------------------ overview com LLM falsa


def test_overview_removes_invented_ids(fixture_copy, config) -> None:
    profile = scan(fixture_copy("python_fastapi_openai"), config).profile
    model = FakeModel({
        "sentences": [
            {"text": "É uma API FastAPI.", "ids": ["framework.fastapi"]},
            {"text": "Guarda dados em PostgreSQL.", "ids": ["db.postgresql"]},  # inventado
            {"text": "Usa Redis como cache.", "ids": []},  # sem citação
            {"text": "Chama a OpenAI.", "ids": ["service.openai", "service.inventado"]},
        ]
    })
    overview = generate_overview(profile, model)
    assert [s.render() for s in overview.summary.sentences] == ["É uma API FastAPI [framework.fastapi]."]
    assert len(overview.summary.removed) == 3
    # a LLM recebeu só factos, nunca código
    assert "def ask" not in model.prompts[0] and "client.chat" not in model.prompts[0]


def test_every_sentence_in_overview_md_has_valid_citations(fixture_copy, config) -> None:
    root = fixture_copy("node_sqlite_lying_readme")
    profile = scan(root, config).profile
    ids = {c.id for c in profile.claims}
    model = FakeModel(
        "Usa SQLite [db.sqlite]. Usa MongoDB [db.mongodb]. Tem rotas Express [framework.express].",
        {"data": [{"text": "Os dados ficam em SQLite.", "ids": ["db.sqlite"]},
                  {"text": "E em Mongo.", "ids": ["db.mongodb"]}]},
    )
    exp = explain(profile, model, root=root, read=lambda r: (root / r).read_text())
    md = overview_markdown(exp, generate_overview(profile, model), "2026-10-05 12:00")
    ai_lines = [l for l in md.splitlines() if "[" in l and ("≈ IA" in l or l.startswith("Usa") or l.startswith("Tem"))]
    assert ai_lines
    for line in ai_lines:
        for group in re.findall(r"\[([^\[\]]+)\]", line):
            for cited in group.split(","):
                assert cited.strip() in ids, line
    assert "MongoDB" not in md and "Mongo." not in md
    assert "≈ redigido pela IA a partir de factos" in md


# ------------------------------------------------------------------ sem Ollama


def test_explain_without_llm_shows_only_facts(fixture_copy, config) -> None:
    root = fixture_copy("python_fastapi_openai")
    profile = scan(root, config).profile
    exp = explain(profile, None, root=root, read=lambda r: (root / r).read_text())
    assert all(a.drafted is None for a in exp.answers)
    by_key = {a.question.key: a for a in exp.answers}
    assert by_key["apis"].facts[0].id == "service.openai"
    assert by_key["data"].unknown
    assert by_key["what"].lines[0].startswith("Fonte: README.md:3")


def test_llm_failure_keeps_facts(fixture_copy, config) -> None:
    root = fixture_copy("python_fastapi_openai")
    profile = scan(root, config).profile
    exp = explain(profile, BrokenModel(), root=root, read=lambda r: (root / r).read_text())
    assert exp.llm_error == "connection refused"
    assert any(a.facts for a in exp.answers)
    assert generate_overview(profile, BrokenModel()).summary is None


def test_cli_explain_without_ollama(fixture_copy) -> None:
    root = fixture_copy("python_fastapi_openai")
    result = runner.invoke(
        app, ["explain", str(root)], env={"COLUMNS": "200", "LOCALALIBI_OLLAMA_URL": "http://127.0.0.1:9"}
    )
    assert result.exit_code == 0, result.output
    assert "Redação por IA desligada" in result.output
    assert "Serviço externo: OpenAI" in result.output
    md = (root / ".localalibi" / "overview.md").read_text()
    assert "Redação por IA indisponível" in md
    assert "`[service.openai]`" in md


def test_empty_project_is_mostly_unknown(fixture_copy, config) -> None:
    root = fixture_copy("empty_project")
    profile = scan(root, config).profile
    exp = explain(profile, FakeModel("Faz muita coisa [inventado]."), root=root, read=lambda r: (root / r).read_text())
    unknown = [a for a in exp.answers if a.unknown]
    assert len(unknown) >= 6
    for a in unknown:
        assert a.drafted is None  # sem factos: nem se pergunta à LLM


def test_client_refuses_non_local_servers() -> None:
    with pytest.raises(NotLocal):
        OllamaClient(url="http://192.168.1.10:11434")
    with pytest.raises(NotLocal):
        OllamaClient(url="https://api.example.com")
    assert OllamaClient(url="http://127.0.0.1:9").available() is False
