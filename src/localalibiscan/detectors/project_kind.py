"""Detetor `project_kind`: que tipo de pasta foi recebida. Corre sempre primeiro.

Não está no REGISTRY porque decide *se* os outros detetores correm. A mesma
função `classify` é reutilizada pelo painel (Fase 3) para descobrir projetos.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from itertools import islice
from pathlib import Path
from typing import Literal

from ..config import CEILING_MARKER, Config, load_config
from ..fs import ProjectFS
from ..knowledge import MANIFEST_NAMES, is_code
from ..models import Claim, Evidence, utcnow

Verdict = Literal["project", "root", "subfolder", "probable_project", "not_a_project"]

VERDICT_LABEL: dict[str, str] = {
    "project": "projeto de software",
    "root": "pasta com vários projetos",
    "subfolder": "subpasta de um projeto",
    "probable_project": "provável projeto",
    "not_a_project": "não é um projeto de software",
}
VERDICT_SYMBOL: dict[str, str] = {
    "project": "✓",
    "root": "▦",
    "subfolder": "↑",
    "probable_project": "≈",
    "not_a_project": "✗",
}
ANALYZABLE: frozenset[str] = frozenset({"project", "probable_project"})


@dataclass
class KindResult:
    path: Path
    verdict: Verdict
    claim: Claim
    project_root: Path | None = None  # caso "subfolder"
    subprojects: list[Path] = field(default_factory=list)  # caso "root"

    @property
    def analyzable(self) -> bool:
        return self.verdict in ANALYZABLE


def project_markers(folder: Path) -> list[str]:
    """`.git` e manifestos conhecidos presentes na própria pasta."""
    markers = []
    if (folder / ".git").exists():
        markers.append(".git")
    try:
        names = sorted(p.name for p in folder.iterdir() if p.is_file())
    except OSError:
        return markers
    markers.extend(n for n in names if n in MANIFEST_NAMES)
    return markers


def find_subprojects(folder: Path, config: Config, max_depth: int | None = None) -> list[Path]:
    """Subpastas que são projetos (`.git` ou manifesto), sem descer dentro delas."""
    max_depth = config.root_max_depth if max_depth is None else max_depth
    found: list[Path] = []

    def visit(current: Path, depth: int) -> None:
        try:
            children = sorted(p for p in current.iterdir() if p.is_dir() and not p.is_symlink())
        except OSError:
            return
        for child in children:
            if child.name.startswith(".") or child.name in config.excluded_dirs:
                continue
            if project_markers(child):
                found.append(child)
            elif depth < max_depth:
                visit(child, depth + 1)

    visit(folder, 1)
    return found


def find_project_root(folder: Path, config: Config) -> Path | None:
    """Sobe no máximo `subfolder_max_up` níveis, nunca acima da pasta pessoal."""
    home = config.home_dir.resolve()
    under_home = folder.is_relative_to(home) and folder != home
    current = folder
    for _ in range(config.subfolder_max_up):
        if (current / CEILING_MARKER).exists():
            return None
        parent = current.parent
        if parent == current:
            return None
        if under_home and (parent == home or not parent.is_relative_to(home)):
            return None
        if project_markers(parent):
            return parent
        current = parent
    return None


def classify(path: str | Path, config: Config | None = None) -> KindResult:
    config = config or load_config()
    folder = Path(path).expanduser().resolve()
    if not folder.is_dir():
        raise NotADirectoryError(f"Não é uma pasta: {folder}")

    def make(verdict: Verdict, status: str, evidence: list[Evidence], note: str | None = None, **kw) -> KindResult:
        claim = Claim(
            id="project.kind",
            category="project",
            label="Tipo de pasta",
            value=verdict,
            status=status,
            evidence=evidence,
            source="detector:project_kind",
            detected_at=utcnow(),
            note=note,
        )
        return KindResult(path=folder, verdict=verdict, claim=claim, **kw)

    # 1) projeto
    markers = project_markers(folder)
    if markers:
        evidence = [_marker_evidence(m) for m in markers]
        return make("project", "confirmed", evidence)

    # 2) raiz com vários projetos
    subprojects = find_subprojects(folder, config)
    if len(subprojects) >= config.root_min_subprojects:
        evidence = []
        for sub in subprojects:
            rel = sub.relative_to(folder).as_posix()
            evidence.append(_marker_evidence(project_markers(sub)[0], prefix=f"{rel}/"))
        return make(
            "root",
            "confirmed",
            evidence,
            note=f"{len(subprojects)} projetos encontrados",
            subprojects=subprojects,
        )

    # 3) subpasta de um projeto
    project_root = find_project_root(folder, config)
    if project_root is not None:
        rel = Path(os.path.relpath(project_root, folder)).as_posix()
        evidence = [_marker_evidence(m, prefix=f"{rel}/") for m in project_markers(project_root)]
        return make(
            "subfolder",
            "confirmed",
            evidence,
            note=f"Raiz do projeto: {project_root}",
            project_root=project_root,
        )

    # 4) e 5) contar ficheiros de código
    entries = list(islice(ProjectFS(folder, config).walk(), config.kind_max_files))
    code = [e for e in entries if is_code(e.extension)]
    pct = round(100 * len(code) / len(entries)) if entries else 0
    count_ev = Evidence(
        file=".",
        snippet=f"{len(code)} de {len(entries)} ficheiros ({pct}%) são código ou notebooks",
        kind="count",
    )
    if len(code) >= config.probable_min_code_files:
        evidence = [count_ev] + [
            Evidence(file=e.path, kind="file", snippet="ficheiro de código") for e in code[:5]
        ]
        return make(
            "probable_project",
            "inferred",
            evidence,
            note="Sem .git nem manifesto: análise feita por indícios",
        )

    evidence = [
        Evidence(file=".", snippet="0 manifestos conhecidos", kind="count"),
        Evidence(file=".", snippet="sem pasta .git", kind="git"),
        count_ev,
    ]
    return make("not_a_project", "confirmed", evidence)


def _marker_evidence(marker: str, prefix: str = "") -> Evidence:
    if marker == ".git":
        return Evidence(file=f"{prefix}.git", kind="git", snippet="repositório git")
    return Evidence(file=f"{prefix}{marker}", kind="manifest", snippet="manifesto")
