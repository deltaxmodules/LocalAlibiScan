"""Histórico de análises e comparação em linguagem de arquitetura (Fase 5).

`history.db` guarda, por análise: data, HEAD do git (se houver), os Claims e a
lista de ficheiros com hash. Funciona sem git (só por hash de ficheiros).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path, PurePosixPath

from .fs import FileNotReadable, ProjectFS
from .models import Claim, ProjectProfile
from .project import Project
from .storage import connect, read_only

KEEP_SNAPSHOTS = 50

HISTORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    scanned_at  TEXT NOT NULL,
    git_head    TEXT,
    verdict     TEXT NOT NULL,
    version     TEXT NOT NULL,
    claims      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS files (
    snapshot_id INTEGER NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
    path        TEXT NOT NULL,
    digest      TEXT NOT NULL,
    size        INTEGER NOT NULL,
    PRIMARY KEY (snapshot_id, path)
);
"""

# Categorias cujos Claims aparecem como "+"/"-" no refresh.
RELEVANT = ("service", "database", "orm", "framework", "route", "dependency", "entry_point")
# Ordem de preferência para atribuir um ficheiro alterado a um componente.
COMPONENT_PRIORITY = ("database", "orm", "service", "route", "framework", "entry_point")
STATUS_PT = {"confirmed": "confirmado", "inferred": "inferido", "contradiction": "contradição", "unknown": "desconhecido"}
CATEGORY_NOUN = {
    "service": "Serviço",
    "database": "Base de dados",
    "orm": "ORM",
    "framework": "Framework",
    "route": "Rota",
    "dependency": "Dependência",
    "entry_point": "Ponto de entrada",
}


# --------------------------------------------------------------------- snapshots


def file_digests(project: Project) -> dict[str, tuple[str, int]]:
    """Caminho -> (hash, tamanho). Ficheiros não lidos entram por tamanho+mtime."""
    out = {}
    for entry in project.files:
        if entry.readable:
            try:
                digest = hashlib.sha256(project.fs.read_bytes(entry.path)).hexdigest()
            except (FileNotReadable, OSError):
                continue
        else:
            try:
                mtime = (project.root / entry.path).lstat().st_mtime_ns
            except OSError:
                continue
            digest = f"{entry.skipped}:{entry.size}:{mtime}"
        out[entry.path] = (digest, entry.size)
    return out


def save_snapshot(fs: ProjectFS, profile: ProjectProfile, files: dict[str, tuple[str, int]]) -> int:
    with closing(connect(fs, "history.db", HISTORY_SCHEMA)) as conn, conn:
        cur = conn.execute(
            "INSERT INTO snapshots (scanned_at, git_head, verdict, version, claims) VALUES (?, ?, ?, ?, ?)",
            (
                profile.scanned_at.isoformat(),
                profile.git_head,
                profile.verdict,
                profile.version,
                json.dumps([c.model_dump(mode="json") for c in profile.claims], ensure_ascii=False),
            ),
        )
        snapshot_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO files VALUES (?, ?, ?, ?)",
            [(snapshot_id, path, digest, size) for path, (digest, size) in files.items()],
        )
        conn.execute(
            "DELETE FROM snapshots WHERE id NOT IN (SELECT id FROM snapshots ORDER BY id DESC LIMIT ?)",
            (KEEP_SNAPSHOTS,),
        )
        return snapshot_id


@dataclass
class Snapshot:
    id: int
    scanned_at: datetime
    git_head: str | None
    claims: list[Claim]
    files: dict[str, str]  # caminho -> hash

    def claim_map(self) -> dict[str, Claim]:
        return {c.id: c for c in self.claims}


def _db(root: Path) -> Path:
    return Path(root) / ".localalibi" / "history.db"


def list_snapshots(root: Path, limit: int | None = None) -> list[Snapshot]:
    """Snapshots do mais antigo para o mais recente (só os `limit` últimos, se dado)."""
    path = _db(root)
    if not path.is_file():
        return []
    with closing(read_only(path)) as conn:
        query = "SELECT id, scanned_at, git_head, claims FROM snapshots ORDER BY id DESC"
        rows = conn.execute(query + (" LIMIT ?" if limit else ""), (limit,) if limit else ()).fetchall()
        rows.reverse()
        ids = [r[0] for r in rows]
        files: dict[int, dict[str, str]] = {}
        if ids:
            marks = ",".join("?" * len(ids))
            for sid, fpath, digest in conn.execute(
                f"SELECT snapshot_id, path, digest FROM files WHERE snapshot_id IN ({marks})", ids
            ):
                files.setdefault(sid, {})[fpath] = digest
    return [
        Snapshot(
            id=sid,
            scanned_at=datetime.fromisoformat(at),
            git_head=head,
            claims=[Claim.model_validate(c) for c in json.loads(claims)],
            files=files.get(sid, {}),
        )
        for sid, at, head, claims in rows
    ]


def last_two(root: Path) -> tuple[Snapshot | None, Snapshot | None]:
    snaps = list_snapshots(root, limit=2)
    if not snaps:
        return None, None
    return (snaps[-2] if len(snaps) > 1 else None), snaps[-1]


# --------------------------------------------------------------------- diferenças


@dataclass
class Change:
    sign: str  # "+", "-", "~", "⚠"
    text: str
    location: str | None = None


@dataclass
class Diff:
    added: list[Change] = field(default_factory=list)
    removed: list[Change] = field(default_factory=list)
    changed: list[Change] = field(default_factory=list)
    alerts: list[Change] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not (self.added or self.removed or self.changed or self.alerts)

    def all(self) -> list[Change]:
        return self.added + self.removed + self.changed + self.alerts

    def summary(self) -> str:
        if self.empty:
            return "sem alterações"
        parts = []
        for sign, items in (("+", self.added), ("-", self.removed), ("~", self.changed), ("⚠", self.alerts)):
            if items:
                parts.append(f"{sign}{len(items)}")
        return " ".join(parts)


def _best_location(claim: Claim) -> str | None:
    for kinds in (("code",), ("config", "dependency", "manifest", "file")):
        for ev in claim.evidence:
            if ev.kind in kinds:
                return ev.location()
    return claim.evidence[0].location() if claim.evidence else None


def _describe(claim: Claim, added: bool) -> str:
    if claim.category == "route":
        return f"{'Nova rota' if added else 'Rota removida'} {claim.label}"
    if claim.category == "dependency" and isinstance(claim.value, dict):
        spec = claim.value.get("spec") or ""
        return f"Dependência {claim.label} {spec}".rstrip()
    if claim.category == "entry_point":
        return f"Pontos de entrada: {', '.join(claim.value) if isinstance(claim.value, list) else claim.value}"
    return f"{CATEGORY_NOUN.get(claim.category, claim.label)} {claim.value}"


def _component_of(path: str, claims: list[Claim]) -> str:
    best: tuple[int, str] | None = None
    for claim in claims:
        if claim.category not in COMPONENT_PRIORITY or claim.status == "unknown":
            continue
        if any(ev.file == path for ev in claim.evidence):
            rank = COMPONENT_PRIORITY.index(claim.category)
            name = "Rotas" if claim.category == "route" else _describe(claim, True)
            if claim.category == "entry_point":
                name = "Arranque"
            if best is None or rank < best[0]:
                best = (rank, name)
    if best:
        return best[1]
    parent = PurePosixPath(path).parent.as_posix()
    return f"Outros ({parent})" if parent != "." else "Outros (raiz)"


def diff_snapshots(prev: Snapshot, cur: Snapshot) -> Diff:
    diff = Diff()
    before, after = prev.claim_map(), cur.claim_map()

    def relevant(c: Claim) -> bool:
        return c.category in RELEVANT and c.status != "unknown"

    for cid, claim in after.items():
        if not relevant(claim):
            continue
        old = before.get(cid)
        if old is None or old.status == "unknown":
            if claim.category == "entry_point":
                continue
            diff.added.append(Change("+", _describe(claim, True), _best_location(claim)))
        elif old.status != claim.status:
            diff.changed.append(
                Change(
                    "~",
                    f"{_describe(claim, True)}: {old.symbol} {STATUS_PT[old.status]} → {claim.symbol} {STATUS_PT[claim.status]}",
                    _best_location(claim),
                )
            )
    for cid, claim in before.items():
        if relevant(claim) and claim.category != "entry_point":
            new = after.get(cid)
            if new is None or new.status == "unknown":
                diff.removed.append(Change("-", _describe(claim, False), _best_location(claim)))

    # Ficheiros importantes que desapareceram.
    important = before.get("files.important")
    if important and isinstance(important.value, list):
        for item in important.value:
            if item["path"] not in cur.files:
                diff.removed.append(Change("-", f"Ficheiro importante removido ({item['reason']})", item["path"]))

    # Componentes alterados: ficheiros novos/modificados/removidos agrupados.
    groups: dict[str, dict[str, list[str]]] = {}
    for path in sorted(set(prev.files) | set(cur.files)):
        if path not in prev.files:
            how = "novo"
        elif path not in cur.files:
            how = "removido"
        elif prev.files[path] != cur.files[path]:
            how = "alterado"
        else:
            continue
        claims = cur.claims if path in cur.files else prev.claims
        groups.setdefault(_component_of(path, claims), {}).setdefault(how, []).append(path)
    for name, by_how in sorted(groups.items(), key=lambda kv: (kv[0].startswith("Outros"), kv[0])):
        parts = []
        for how in ("novo", "alterado", "removido"):
            n = len(by_how.get(how, []))
            if n:
                parts.append(f"{n} ficheiro{'s' if n > 1 else ''} {how}{'s' if n > 1 else ''}")
        paths = [p for how in ("novo", "alterado", "removido") for p in by_how.get(how, [])]
        sample = ", ".join(paths[:3]) + ("…" if len(paths) > 3 else "")
        diff.changed.append(Change("~", f"{name}: {', '.join(parts)}", sample))

    # Novas contradições e novidades por documentar.
    for cid, claim in after.items():
        if cid in before:
            continue
        if claim.status == "contradiction":
            diff.alerts.append(Change("⚠", str(claim.value), _best_location(claim)))
        elif cid.startswith("docs.undocumented."):
            diff.alerts.append(Change("⚠", f"README ainda não menciona {claim.value}", _best_location(claim)))
    return diff
