"""Pipeline de análise: veredito → detetores → `.localalibi/` (com cache)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from . import __version__, git
from .config import Config, load_config
from .detectors import run_detectors
from .detectors.project_kind import KindResult, classify
from .fs import ProjectFS
from .models import ProjectProfile
from .project import Project
from .storage import save_evidence


@dataclass
class ScanResult:
    kind: KindResult
    profile: ProjectProfile | None = None  # None quando a análise não correu
    output: Path | None = None
    cached: bool = False


@dataclass
class Fingerprint:
    digest: str
    git_head: str | None
    last_change: datetime | None
    last_change_source: str | None


def fingerprint(root: Path, config: Config) -> Fingerprint:
    """Impressão digital barata: caminho, mtime e tamanho de cada ficheiro + HEAD."""
    fs = ProjectFS(root, config)
    h = hashlib.sha256(__version__.encode())
    newest = 0
    for rel, mtime_ns, size in fs.stat_files():
        h.update(f"{rel}\0{mtime_ns}\0{size}\n".encode())
        newest = max(newest, mtime_ns)
    head = git.head(fs.root)
    h.update(f"HEAD={head}".encode())

    files_time = datetime.fromtimestamp(newest / 1e9, timezone.utc).replace(microsecond=0) if newest else None
    commit_time = git.last_commit_date(fs.root)
    candidates = [(t, src) for t, src in ((commit_time, "git"), (files_time, "files")) if t]
    last, source = max(candidates, key=lambda c: c[0]) if candidates else (None, None)
    return Fingerprint(h.hexdigest(), head, last, source)


def scan(
    path: str | Path,
    config: Config | None = None,
    *,
    force: bool = False,
    write: bool = True,
    use_cache: bool = False,
) -> ScanResult:
    config = config or load_config()
    kind = classify(path, config)
    if not kind.analyzable and not force:
        return ScanResult(kind=kind)

    fp = fingerprint(kind.path, config)
    if use_cache:
        previous = load_profile(kind.path)
        if previous and previous.fingerprint == fp.digest and previous.verdict == kind.verdict:
            return ScanResult(kind=kind, profile=previous, cached=True)

    project = Project(kind.path, config)
    kind.claim.detected_at = project.now
    claims = [kind.claim, *run_detectors(project)]
    profile = ProjectProfile(
        version=__version__,
        root=str(project.root),
        verdict=kind.verdict,
        forced=force and not kind.analyzable,
        scanned_at=project.now,
        claims=claims,
        fingerprint=fp.digest,
        git_head=fp.git_head,
        last_change=fp.last_change,
        last_change_source=fp.last_change_source,
    )
    output = None
    if write:
        project.fs.ensure_output_dir()
        output = project.fs.write_text(
            project.fs.output_dir / "project.json", profile.model_dump_json(indent=2) + "\n"
        )
        save_evidence(project.fs, profile)
    return ScanResult(kind=kind, profile=profile, output=output)


def load_profile(path: str | Path) -> ProjectProfile | None:
    """Lê o nosso próprio `.localalibi/project.json` (se existir e for válido)."""
    file = Path(path) / ".localalibi" / "project.json"
    if not file.is_file():
        return None
    try:
        return ProjectProfile.model_validate_json(file.read_text(encoding="utf-8"))
    except ValueError:
        return None
