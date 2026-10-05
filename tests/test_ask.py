from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from localalibiscan.ask import ask, terms_of
from localalibiscan.cli import app
from localalibiscan.project import Project
from localalibiscan.scan import scan

runner = CliRunner()


class FakeModel:
    name = "fake"

    def __init__(self, sentences: list[dict]) -> None:
        self.sentences = sentences
        self.calls = 0
        self.prompt = ""

    def generate(self, prompt: str, **kw) -> str:
        self.calls += 1
        self.prompt = prompt
        return json.dumps({"sentences": self.sentences})


def run(root: Path, config, question: str, model=None):
    profile = scan(root, config).profile
    return ask(Project(root, config), profile, question, model)


def test_terms_and_synonyms() -> None:
    terms = terms_of("Onde é feita a autenticação?")
    assert terms[0] == "autenticacao"
    assert {"login", "jwt", "auth"} <= set(terms)
    assert "onde" not in terms and "feita" not in terms


def test_openai_question_cites_services_ai(fixture_copy, config) -> None:
    result = run(fixture_copy("python_fastapi_openai"), config, "Onde usamos OpenAI?")
    assert result.found
    top = result.excerpts[0]
    assert top.file == "services/ai.py"
    assert top.start <= 3 <= top.end
    assert "services/ai.py:3" in top.citations()


def test_llm_answer_is_validated_against_excerpts(fixture_copy, config) -> None:
    model = FakeModel([
        {"text": "O cliente OpenAI é criado em services/ai.py.", "ids": ["services/ai.py:5"]},
        {"text": "O pacote é importado no topo.", "ids": ["services/ai.py:3-4"]},
        {"text": "A função ask chama o modelo.", "ids": ["services/ai.py:9"]},  # fora dos excertos
        {"text": "Também há chamadas em billing.py.", "ids": ["billing.py:3"]},  # inventado
        {"text": "Usa GPT-4.", "ids": []},  # sem citação
    ])
    result = run(fixture_copy("python_fastapi_openai"), config, "Onde usamos OpenAI?", model)
    assert [s.render() for s in result.answer.sentences] == [
        "O cliente OpenAI é criado em services/ai.py [services/ai.py:5].",
        "O pacote é importado no topo [services/ai.py:3].",
    ]
    assert len(result.answer.removed) == 3
    # a LLM recebeu os excertos numerados
    assert "3: from openai import OpenAI" in model.prompt


def test_nonexistent_topic_does_not_call_llm(fixture_copy, config) -> None:
    model = FakeModel([{"text": "O Stripe está em payments.py.", "ids": ["payments.py:1"]}])
    result = run(fixture_copy("python_fastapi_openai"), config, "Onde está o pagamento Stripe?", model)
    assert not result.found
    assert model.calls == 0
    assert result.answer is None
    assert "OpenAI" in result.suggestions


def test_finds_functions_imports_and_routes(fixture_copy, config) -> None:
    root = fixture_copy("node_sqlite_lying_readme")
    result = run(root, config, "onde ficam os dados?")
    files = [e.file for e in result.excerpts]
    assert files[0] == "src/db/database.ts"
    routes = run(root, config, "Que endpoints existem para notes?")
    assert any(e.file == "src/routes/notes.ts" for e in routes.excerpts)


def test_auth_example(tmp_path: Path, config) -> None:
    root = tmp_path / "p"
    (root / "src" / "auth").mkdir(parents=True)
    (root / "package.json").write_text('{\n  "dependencies": {\n    "express": "4",\n    "jsonwebtoken": "9"\n  }\n}\n')
    (root / "src" / "auth" / "middleware.js").write_text(
        "const jwt = require('jsonwebtoken');\n\nfunction requireLogin(req, res, next) {\n"
        "  jwt.verify(req.headers.authorization, 'k');\n  next();\n}\n\nmodule.exports = { requireLogin };\n"
    )
    (root / "src" / "server.js").write_text("const express = require('express');\nconst app = express();\n")
    result = run(root, config, "Onde é feita a autenticação?")
    assert result.excerpts[0].file == "src/auth/middleware.js"
    assert any("requireLogin" in r for r in result.excerpts[0].reasons)


def test_cli_ask_without_llm(fixture_copy) -> None:
    root = fixture_copy("python_fastapi_openai")
    env = {"COLUMNS": "200", "LOCALALIBI_OLLAMA_URL": "http://127.0.0.1:9"}
    ok = runner.invoke(app, ["ask", str(root), "Onde usamos OpenAI?"], env=env)
    assert ok.exit_code == 0, ok.output
    assert "AI drafting off" in ok.output
    assert "services/ai.py:1-7" in ok.output
    brief = runner.invoke(app, ["ask", str(root), "Onde usamos OpenAI?", "--brief"], env=env)
    assert "services/ai.py:1-7" in brief.output and "from openai import OpenAI" not in brief.output
    missing = runner.invoke(app, ["ask", str(root), "Onde está o pagamento Stripe?"], env=env)
    assert missing.exit_code == 1
    assert "No evidence found about this" in missing.output
