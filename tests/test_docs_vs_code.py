from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from localalibiscan.cli import app
from localalibiscan.detectors import run_detectors
from localalibiscan.models import Claim
from localalibiscan.project import Project

from .conftest import tree_hash

runner = CliRunner()


def docs_claims(path: Path, config) -> dict[str, Claim]:
    return {c.id: c for c in run_detectors(Project(path, config)) if c.category == "docs_vs_code"}


def make(root: Path, readme: str, files: dict[str, str] | None = None) -> Path:
    root.mkdir(parents=True)
    (root / "README.md").write_text(readme)
    (root / "package.json").write_text('{\n  "dependencies": {\n    "better-sqlite3": "9"\n  }\n}\n')
    (root / "db.js").write_text("const Database = require('better-sqlite3');\nconst db = new Database('a.db');\n")
    for rel, content in (files or {}).items():
        (root / rel).write_text(content)
    return root


def test_lying_readme_contradiction(fixture_copy, config) -> None:
    root = fixture_copy("node_sqlite_lying_readme")
    before = tree_hash(root)
    claims = docs_claims(root, config)
    c = claims["docs.contradiction.postgresql"]
    assert c.status == "contradiction"
    assert c.value == "Documentação diz PostgreSQL, código usa SQLite"
    locations = [e.location() for e in c.evidence]
    assert "README.md:8" in locations
    assert "src/db/database.ts:1" in locations
    assert {e.kind for e in c.evidence} >= {"doc", "code"}
    assert claims["docs.undocumented.sqlite"].value == "SQLite"
    assert tree_hash(root) == before  # nunca edita a documentação


def test_no_false_positives_fastapi(fixture_copy, config) -> None:
    claims = docs_claims(fixture_copy("python_fastapi_openai"), config)
    assert not [c for c in claims.values() if c.status == "contradiction"]
    assert not [c for c in claims.values() if c.id.startswith("docs.only.")]


def test_no_false_positives_monorepo(fixture_copy, config) -> None:
    claims = docs_claims(fixture_copy("monorepo_mixed"), config)
    assert not [c for c in claims.values() if c.status == "contradiction"]


def test_mentioned_only_in_docs(tmp_path: Path, config) -> None:
    root = make(tmp_path / "p", "# App\n\nUses SQLite. Payments with Stripe.\n")
    claims = docs_claims(root, config)
    only = claims["docs.only.stripe"]
    assert only.status == "inferred"
    assert only.evidence[0].location() == "README.md:3"
    assert "docs.undocumented.sqlite" not in claims


def test_services_never_contradict_each_other(tmp_path: Path, config) -> None:
    root = make(
        tmp_path / "p",
        "# App\n\nUses SQLite and Anthropic.\n",
        {"ai.js": "import OpenAI from 'openai';\n"},
    )
    claims = docs_claims(root, config)
    assert not [c for c in claims.values() if c.status == "contradiction"]
    assert claims["docs.only.anthropic"].status == "inferred"
    assert claims["docs.undocumented.openai"].status == "confirmed"


def test_redis_is_not_a_rival_database(tmp_path: Path, config) -> None:
    root = make(tmp_path / "p", "# App\n\nSQLite for data, Redis for cache.\n")
    claims = docs_claims(root, config)
    assert "docs.contradiction.redis" not in claims
    assert claims["docs.only.redis"].status == "inferred"


def test_ambiguous_migration_sentence_pt(tmp_path: Path, config) -> None:
    root = make(tmp_path / "p", "# App\n\nMigrámos de PostgreSQL para SQLite em 2025.\n")
    claims = docs_claims(root, config)
    assert "docs.contradiction.postgresql" not in claims
    only = claims["docs.only.postgresql"]
    assert only.status == "inferred"
    assert "ambígua" in only.note


def test_ambiguous_migration_sentence_en(tmp_path: Path, config) -> None:
    root = make(tmp_path / "p", "# App\n\nWe moved from MongoDB to SQLite.\n")
    assert "docs.contradiction.mongodb" not in docs_claims(root, config)


def test_clear_mention_still_contradicts_when_another_line_is_ambiguous(tmp_path: Path, config) -> None:
    root = make(tmp_path / "p", "# App\n\nData lives in MySQL.\n\nPreviously we used MySQL too.\n")
    c = docs_claims(root, config)["docs.contradiction.mysql"]
    # só as frases claras servem de prova da contradição
    assert [e.location() for e in c.evidence if e.kind == "doc"] == ["README.md:3"]


def test_common_words_are_not_tech_mentions(tmp_path: Path, config) -> None:
    root = make(tmp_path / "p", "# App\n\nWe express our thanks. Click the button; react quickly.\n")
    claims = docs_claims(root, config)
    assert not [c for c in claims.values() if c.id.startswith("docs.only.")]


def test_changelog_and_fixtures_are_ignored(tmp_path: Path, config) -> None:
    root = make(tmp_path / "p", "# App\n\nUses SQLite.\n", {"CHANGELOG.md": "- Dropped PostgreSQL\n"})
    (root / "tests" / "fixtures").mkdir(parents=True)
    (root / "tests" / "fixtures" / "README.md").write_text("MongoDB\n")
    claims = docs_claims(root, config)
    assert not [c for c in claims.values() if c.id.startswith(("docs.only.", "docs.contradiction."))]


def test_ambiguous_names_count_in_lists_and_headings(tmp_path: Path, config) -> None:
    root = make(tmp_path / "p", "# App\n\n## Stack\n\n- Express + SQLite\n")
    assert docs_claims(root, config)["docs.only.express"].evidence[0].location() == "README.md:5"


def test_scan_shows_section(fixture_copy) -> None:
    result = runner.invoke(app, ["scan", str(fixture_copy("node_sqlite_lying_readme"))], env={"COLUMNS": "200"})
    assert "Documentação vs código" in result.output
    assert "⚠ Documentação vs código: Documentação diz PostgreSQL, código usa SQLite" in result.output
    assert "README.md:8" in result.output


def test_negation_is_not_a_claim(tmp_path: Path, config) -> None:
    root = make(tmp_path / "p", "# App\n\nUses SQLite (no PostgreSQL needed).\n")
    claims = docs_claims(root, config)
    assert "docs.contradiction.postgresql" not in claims
    assert "ambígua" in claims["docs.only.postgresql"].note


def test_comparison_table_is_not_a_contradiction(tmp_path: Path, config) -> None:
    root = make(tmp_path / "p", "# App\n\n| Chosen | Alternative |\n|---|---|\n| SQLite | PostgreSQL |\n")
    assert "docs.contradiction.postgresql" not in docs_claims(root, config)


def test_only_readme_proves_contradictions(tmp_path: Path, config) -> None:
    root = make(tmp_path / "p", "# App\n", {"NOTES.md": "Data in MongoDB.\n"})
    claims = docs_claims(root, config)
    assert "docs.contradiction.mongodb" not in claims
    assert claims["docs.only.mongodb"].evidence[0].location() == "NOTES.md:1"


def test_hidden_dirs_and_agent_files_are_not_docs(tmp_path: Path, config) -> None:
    root = make(tmp_path / "p", "# App\n\nUses SQLite.\n", {"CLAUDE.md": "| FastAPI | Flask |\n"})
    (root / ".claude" / "agents").mkdir(parents=True)
    (root / ".claude" / "agents" / "x.md").write_text("Stripe, Supabase, AWS\n")
    (root / "notes").mkdir()
    (root / "notes" / "ideas.md").write_text("MongoDB?\n")
    (root / "docs").mkdir()
    (root / "docs" / "deploy.md").write_text("Deploy on AWS.\n")
    claims = docs_claims(root, config)
    only = sorted(c.value for c in claims.values() if c.id.startswith("docs.only."))
    assert only == ["AWS"]


def test_urls_are_not_mentions(tmp_path: Path, config) -> None:
    root = make(tmp_path / "p", "# App\n\nSee https://example.com/openai/v1 for SQLite notes.\n")
    assert "docs.only.openai" not in docs_claims(root, config)
