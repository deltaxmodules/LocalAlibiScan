from __future__ import annotations

import time
from pathlib import Path

from localalibiscan.detectors import run_detectors
from localalibiscan.models import Claim
from localalibiscan.project import Project
from localalibiscan.scan import scan
from localalibiscan.storage import read_only

from .conftest import tree_hash


def claims_for(path: Path, config) -> dict[str, Claim]:
    return {c.id: c for c in run_detectors(Project(path, config))}


def write(root: Path, files: dict[str, str]) -> Path:
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    return root


# --------------------------------------------------------------- verificação do SPEC


def test_sqlite_confirmed_with_manifest_and_code(fixture_copy, config) -> None:
    db = claims_for(fixture_copy("node_sqlite_lying_readme"), config)["db.sqlite"]
    assert db.status == "confirmed"
    assert db.value == "SQLite"
    locations = [e.location() for e in db.evidence]
    assert "package.json:13" in locations
    assert "src/db/database.ts:1" in locations
    assert "src/db/database.ts:3" in locations  # new Database('app.db')
    assert db.evidence[0].kind == "dependency"


def test_redis_declared_not_used_is_inferred(fixture_copy, config) -> None:
    redis = claims_for(fixture_copy("python_dep_unused"), config)["db.redis"]
    assert redis.status == "inferred"
    assert "sem uso" in redis.note
    assert [e.location() for e in redis.evidence] == ["requirements.txt:2"]


def test_openai_confirmed_and_routes(fixture_copy, config) -> None:
    claims = claims_for(fixture_copy("python_fastapi_openai"), config)
    openai = claims["service.openai"]
    assert openai.status == "confirmed"
    locations = [e.location() for e in openai.evidence]
    assert "requirements.txt:3" in locations
    assert "services/ai.py:3" in locations
    assert ".env.example:1" in locations
    routes = {c.label: c.evidence[0].location() for c in claims.values() if c.category == "route"}
    assert routes == {
        "GET /health": "main.py:9",
        "POST /chat/": "routes/chat.py:13",
        "GET /chat/models": "routes/chat.py:18",
    }
    assert claims["framework.fastapi"].status == "confirmed"


def test_express_routes_with_mount_prefix(fixture_copy, config) -> None:
    claims = claims_for(fixture_copy("node_sqlite_lying_readme"), config)
    routes = {c.label: c.evidence[0].location() for c in claims.values() if c.category == "route"}
    assert routes == {
        "GET /health": "src/index.ts:8",
        "GET /notes/": "src/routes/notes.ts:6",
        "POST /notes/": "src/routes/notes.ts:10",
    }


def test_unknowns_when_nothing_found(fixture_copy, config) -> None:
    claims = claims_for(fixture_copy("empty_project"), config)
    for cid in ("db.engine", "framework.main", "service.external"):
        assert claims[cid].status == "unknown"
    assert not any(c.category == "route" for c in claims.values())


def test_monorepo_frameworks(fixture_copy, config) -> None:
    claims = claims_for(fixture_copy("monorepo_mixed"), config)
    assert claims["framework.react"].status == "confirmed"
    assert claims["framework.vite"].status == "confirmed"  # vite.config.js importa 'vite'
    assert claims["framework.flask"].status == "confirmed"
    routes = [c.label for c in claims.values() if c.category == "route"]
    assert routes == ["GET /api/products"]


# --------------------------------------------------------------- regra de promoção


def test_code_without_dependency_is_confirmed_with_note(tmp_path: Path, config) -> None:
    root = write(tmp_path / "p", {
        "package.json": '{\n  "name": "x"\n}\n',
        "index.js": "const Stripe = require('stripe');\nconst s = Stripe('k');\n",
    })
    stripe = claims_for(root, config)["service.stripe"]
    assert stripe.status == "confirmed"
    assert stripe.note == "usado no código sem dependência declarada"
    assert [e.location() for e in stripe.evidence] == ["index.js:1", "index.js:2"]


def test_python_stdlib_sqlite_needs_no_dependency(tmp_path: Path, config) -> None:
    root = write(tmp_path / "p", {
        "requirements.txt": "\n",
        "db.py": "import sqlite3\n\nconn = sqlite3.connect('x.db')\n",
    })
    sqlite = claims_for(root, config)["db.sqlite"]
    assert sqlite.status == "confirmed"
    assert sqlite.note is None
    assert [e.location() for e in sqlite.evidence] == ["db.py:1", "db.py:3"]


def test_env_only_is_inferred(tmp_path: Path, config) -> None:
    root = write(tmp_path / "p", {"requirements.txt": "\n", ".env.example": "ANTHROPIC_API_KEY=\n"})
    claim = claims_for(root, config)["service.anthropic"]
    assert claim.status == "inferred"
    assert claim.note == "só indícios de configuração"


def test_connection_string_and_prisma_provider(tmp_path: Path, config) -> None:
    root = write(tmp_path / "p", {
        "package.json": '{\n  "dependencies": {\n    "@prisma/client": "^5.0.0"\n  }\n}\n',
        "prisma/schema.prisma": 'datasource db {\n  provider = "postgresql"\n  url = env("DATABASE_URL")\n}\n',
        "app.py": 'engine = create_engine("postgresql+psycopg://u@h/db")\n',
    })
    claims = claims_for(root, config)
    pg = claims["db.postgresql"]
    assert pg.status == "confirmed"
    assert {e.location() for e in pg.evidence} == {"prisma/schema.prisma:2", "app.py:1"}
    assert claims["orm.prisma"].status == "inferred"  # dependência + schema, sem import no código


def test_local_module_with_package_name_is_not_the_package(tmp_path: Path, config) -> None:
    root = write(tmp_path / "p", {
        "requirements.txt": "\n",
        "redis.py": "CACHE = {}\n",
        "main.py": "import redis\n",
    })
    assert "db.redis" not in claims_for(root, config)


# --------------------------------------------------------------- rotas


def test_flask_and_nextjs_routes(tmp_path: Path, config) -> None:
    root = write(tmp_path / "p", {
        "package.json": '{\n  "dependencies": {\n    "next": "14.0.0"\n  }\n}\n',
        "app/api/users/[id]/route.ts": "export async function GET() {}\nexport async function DELETE() {}\n",
        "app/(marketing)/about/page.tsx": "export default function Page() { return null }\n",
        "app/page.tsx": "export default function Home() { return null }\n",
        "server/app.py": (
            "from flask import Flask, Blueprint\n"
            "app = Flask(__name__)\n"
            "bp = Blueprint('admin', __name__, url_prefix='/admin')\n"
            "@app.route('/login', methods=['GET', 'POST'])\n"
            "def login(): ...\n"
            "@bp.delete('/users/<id>')\n"
            "def rm(id): ...\n"
        ),
    })
    claims = claims_for(root, config)
    labels = sorted(c.label for c in claims.values() if c.category == "route")
    assert labels == [
        "DELETE /admin/users/<id>",
        "DELETE /api/users/[id]",
        "GET /api/users/[id]",
        "GET /login",
        "PAGE /",
        "PAGE /about",
        "POST /login",
    ]


def test_http_client_calls_are_not_routes(tmp_path: Path, config) -> None:
    root = write(tmp_path / "p", {
        "package.json": '{\n  "dependencies": {\n    "axios": "1.0.0"\n  }\n}\n',
        "client.js": "import axios from 'axios';\naxios.get('/api/users');\nconst m = new Map();\nm.get('/x');\n",
    })
    assert not [c for c in claims_for(root, config).values() if c.category == "route"]


# --------------------------------------------------------------- ranking


def test_important_files_ranking(fixture_copy, config) -> None:
    important = claims_for(fixture_copy("python_fastapi_openai"), config)["files.important"]
    top = {i["path"]: i["reason"] for i in important.value}
    paths = list(top)
    assert paths[0] == "main.py"
    assert top["main.py"].startswith("Ponto de entrada")
    assert "Define 2 rotas" in top["routes/chat.py"]
    assert "Usa OpenAI" in top["services/ai.py"]
    assert ".env.example" not in top
    assert len(paths) <= 10


# --------------------------------------------------------------- evidence.db e invariantes


def test_evidence_db(fixture_copy, config) -> None:
    root = fixture_copy("node_sqlite_lying_readme")
    scan(root, config)
    scan(root, config)
    with read_only(root / ".localalibi/evidence.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM scans").fetchone()[0] == 2
        rows = conn.execute(
            "SELECT file, line, kind FROM evidence WHERE claim_id = 'db.sqlite' AND scan_id = 2 ORDER BY position"
        ).fetchall()
    assert rows[0] == ("package.json", 13, "dependency")
    assert ("src/db/database.ts", 3, "code") in rows


def test_scan_does_not_touch_project_files(fixture_copy, config) -> None:
    root = fixture_copy("python_fastapi_openai")
    before = tree_hash(root)
    scan(root, config)
    assert tree_hash(root) == before
    assert sorted(p.name for p in (root / ".localalibi").iterdir()) == [".gitignore", "evidence.db", "project.json"]


def test_medium_project_under_30_seconds(tmp_path: Path, config) -> None:
    root = tmp_path / "big"
    files = {"package.json": '{\n  "dependencies": {\n    "express": "4",\n    "pg": "8"\n  }\n}\n'}
    for i in range(250):
        files[f"src/mod{i // 25}/file{i}.ts"] = (
            "import express from 'express';\nimport { Pool } from 'pg';\n"
            f"import {{ x }} from '../mod0/file0';\n"
            "const router = express.Router();\n"
            f"router.get('/r{i}', (req, res) => res.json({{}}));\n"
            "export function handler() { return new Pool(); }\n" * 3
        )
        files[f"py/pkg{i // 25}/m{i}.py"] = "import os\nfrom fastapi import APIRouter\n\ndef f():\n    return os.getcwd()\n" * 5
    write(root, files)
    start = time.perf_counter()
    result = scan(root, config)
    elapsed = time.perf_counter() - start
    assert result.profile is not None
    assert elapsed < 30, f"{elapsed:.1f}s"
