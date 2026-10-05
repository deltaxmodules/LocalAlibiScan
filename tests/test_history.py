from __future__ import annotations

import os
from pathlib import Path

from typer.testing import CliRunner

from localalibiscan.cli import app
from localalibiscan.dashboard import build_dashboard
from localalibiscan.history import list_snapshots
from localalibiscan.scan import scan

runner = CliRunner()

OPENAI_TS = """import OpenAI from 'openai';

const client = new OpenAI();

export async function summarize(text: string) {
  return client.chat.completions.create({ model: 'gpt-4o-mini', messages: [{ role: 'user', content: text }] });
}
"""
NEW_ROUTE = """
notesRouter.delete('/:id', (req, res) => {
  res.status(204).end();
});
"""


def texts(diff) -> list[str]:
    return [f"{c.sign} {c.text} @ {c.location}" for c in diff.all()]


def test_refresh_shows_new_service_and_route(fixture_copy, config) -> None:
    root = fixture_copy("node_sqlite_lying_readme")
    first = scan(root, config)
    assert first.first_scan and first.diff is None

    (root / "services").mkdir()
    (root / "services" / "openai.ts").write_text(OPENAI_TS)
    with (root / "src" / "routes" / "notes.ts").open("a") as fh:
        fh.write(NEW_ROUTE)

    result = scan(root, config)
    lines = texts(result.diff)
    assert "+ Service: OpenAI @ services/openai.ts:1" in lines
    assert "+ New route DELETE /notes/:id @ src/routes/notes.ts:16" in lines
    assert "⚠ README does not mention OpenAI yet @ services/openai.ts:1" in lines
    assert any(l.startswith("~ Service OpenAI: 1 new file") for l in lines)
    assert any(l.startswith("~ Routes: 1 file changed") for l in lines)


def test_removed_important_file(fixture_copy, config) -> None:
    root = fixture_copy("node_sqlite_lying_readme")
    scan(root, config)
    (root / "src" / "db" / "database.ts").unlink()
    lines = texts(scan(root, config).diff)
    assert any(l.startswith("- Important file removed") and l.endswith("@ src/db/database.ts") for l in lines)
    assert any(l.startswith("~ Database: SQLite: ✓ confirmed → ≈ inferred") for l in lines)


def test_removed_service_and_dependency(fixture_copy, config) -> None:
    root = fixture_copy("python_fastapi_openai")
    scan(root, config)
    (root / "services" / "ai.py").write_text("def ask(text: str) -> str:\n    return text\n")
    (root / "requirements.txt").write_text("fastapi==0.110.0\nuvicorn[standard]==0.29.0\npydantic==2.7.0\n")
    (root / ".env.example").unlink()
    lines = texts(scan(root, config).diff)
    assert "- Service: OpenAI @ services/ai.py:3" in lines  # onde estava o código
    assert "- Dependency openai ==1.23.0 @ requirements.txt:3" in lines


def test_works_without_git_and_counts_modified_files(fixture_copy, config) -> None:
    root = fixture_copy("loose_scripts")  # sem .git nem manifesto
    scan(root, config)
    (root / "plot_results.py").write_text("print('changed')\n")
    result = scan(root, config)
    assert result.profile.git_head is None
    lines = texts(result.diff)
    assert any("1 file changed" in l and "plot_results.py" in l for l in lines)


def test_no_changes(fixture_copy, config) -> None:
    root = fixture_copy("python_dep_unused")
    scan(root, config)
    assert scan(root, config).diff.empty


def test_snapshot_contents(fixture_copy, config) -> None:
    root = fixture_copy("projects_root") / "alpha_api"
    scan(root, config)
    (snap,) = list_snapshots(root)
    assert snap.git_head and len(snap.git_head) == 40
    assert set(snap.files) == {"pyproject.toml", "alpha_api/__init__.py", "alpha_api/app.py"}
    assert any(c.id == "framework.flask" for c in snap.claims)


def test_cli_refresh_and_history(fixture_copy) -> None:
    root = fixture_copy("node_sqlite_lying_readme")
    env = {"COLUMNS": "200"}
    out = runner.invoke(app, ["refresh", str(root)], env=env).output
    assert "First analysis" in out
    (root / "services").mkdir()
    (root / "services" / "openai.ts").write_text(OPENAI_TS)
    out = runner.invoke(app, ["refresh", str(root)], env=env).output
    assert "+ Service: OpenAI" in out and "services/openai.ts:1" in out
    out = runner.invoke(app, ["history", str(root)], env=env).output
    assert "first analysis" in out
    assert "+1" in out


def test_history_without_snapshots(fixture_copy) -> None:
    result = runner.invoke(app, ["history", str(fixture_copy("python_dep_unused"))])
    assert result.exit_code == 2


def test_dashboard_changed_column(fixture_copy, config) -> None:
    root = fixture_copy("projects_root")
    first = {r.name: r.changes for r in build_dashboard(root, config).rows}
    assert set(first.values()) == {"new"}
    target = root / "beta_web" / "server.js"
    target.write_text(target.read_text() + "fastify.post('/items', async () => ({}));\n")
    os.utime(target, None)
    second = {r.name: r.changes for r in build_dashboard(root, config).rows}
    assert second["alpha_api"] == "—"
    assert second["beta_web"].startswith("+1")
