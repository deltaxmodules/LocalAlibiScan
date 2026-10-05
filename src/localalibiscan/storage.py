"""Armazenamento SQLite em `.localalibi/`.

`evidence.db` guarda os Claims e as evidências de cada análise (as últimas
`KEEP_SCANS`). Os caminhos passam sempre por `ProjectFS.writable_path`.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path

from .fs import ProjectFS
from .models import ProjectProfile

KEEP_SCANS = 20

EVIDENCE_SCHEMA = """
CREATE TABLE IF NOT EXISTS scans (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    scanned_at  TEXT NOT NULL,
    root        TEXT NOT NULL,
    verdict     TEXT NOT NULL,
    version     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS claims (
    scan_id     INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    id          TEXT NOT NULL,
    category    TEXT NOT NULL,
    label       TEXT NOT NULL,
    value       TEXT,
    status      TEXT NOT NULL,
    source      TEXT NOT NULL,
    detected_at TEXT NOT NULL,
    note        TEXT,
    PRIMARY KEY (scan_id, id)
);
CREATE TABLE IF NOT EXISTS evidence (
    scan_id     INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    claim_id    TEXT NOT NULL,
    position    INTEGER NOT NULL,
    file        TEXT NOT NULL,
    line        INTEGER,
    snippet     TEXT NOT NULL,
    kind        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS evidence_by_file ON evidence(scan_id, file);
"""


def connect(fs: ProjectFS, name: str, schema: str) -> sqlite3.Connection:
    fs.ensure_output_dir()
    conn = sqlite3.connect(fs.writable_path(fs.output_dir / name))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(schema)
    return conn


def save_evidence(fs: ProjectFS, profile: ProjectProfile) -> int:
    with closing(connect(fs, "evidence.db", EVIDENCE_SCHEMA)) as conn, conn:
        cur = conn.execute(
            "INSERT INTO scans (scanned_at, root, verdict, version) VALUES (?, ?, ?, ?)",
            (profile.scanned_at.isoformat(), profile.root, profile.verdict, profile.version),
        )
        scan_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO claims VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (scan_id, c.id, c.category, c.label, json.dumps(c.value, ensure_ascii=False),
                 c.status, c.source, c.detected_at.isoformat(), c.note)
                for c in profile.claims
            ],
        )
        conn.executemany(
            "INSERT INTO evidence VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (scan_id, c.id, i, e.file, e.line, e.snippet, e.kind)
                for c in profile.claims
                for i, e in enumerate(c.evidence)
            ],
        )
        conn.execute(
            "DELETE FROM scans WHERE id NOT IN (SELECT id FROM scans ORDER BY id DESC LIMIT ?)",
            (KEEP_SCANS,),
        )
        return scan_id


def read_only(path: Path) -> sqlite3.Connection:
    """Ligação só de leitura (para testes e consultas)."""
    # as_uri() trata espaços e letras de unidade (Windows).
    return sqlite3.connect(f"{Path(path).resolve().as_uri()}?mode=ro", uri=True)
