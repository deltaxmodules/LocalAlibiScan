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
from ..i18n import DEFAULT_LANG, t
from ..models import Claim, Evidence, utcnow
from .base import gen_evidence

Verdict = Literal["project", "root", "subfolder", "probable_project", "not_a_project"]

VERDICTS: tuple[str, ...] = ("project", "root", "subfolder", "probable_project", "not_a_project")


def verdict_label(verdict: str, lang: str | None = None) -> str:
    return t(f"verdict.{verdict}", lang=lang) if verdict in VERDICTS else verdict


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


def is_probable_project(folder: Path, config: Config) -> bool:
    """Sem .git nem manifesto, mas com código suficiente para ser um projeto."""
    entries = islice(ProjectFS(folder, config).stat_files(), config.kind_max_files)
    count = 0
    for rel, _mtime, _size in entries:
        if is_code(Path(rel).suffix.lower()):
            count += 1
            if count >= config.probable_min_code_files:
                return True
    return False


def discover_projects(
    folder: Path,
    config: Config,
    max_depth: int | None = None,
    *,
    include_probable: bool = False,
) -> list[tuple[Path, Verdict]]:
    """Subpastas que são projetos, sem descer dentro de um projeto já encontrado.

    Uma pasta que não é projeto mas contém projetos é só um contentor. Se não
    contém nenhum, pode ser um provável projeto (`include_probable`).
    """
    max_depth = config.root_max_depth if max_depth is None else max_depth
    found: list[tuple[Path, Verdict]] = []

    def visit(current: Path, depth: int) -> None:
        try:
            children = sorted(p for p in current.iterdir() if p.is_dir() and not p.is_symlink())
        except OSError:
            return
        for child in children:
            if child.name.startswith(".") or child.name in config.excluded_dirs:
                continue
            if project_markers(child):
                found.append((child, "project"))
                continue
            if any((child / m).exists() for m in config.excluded_dir_markers):
                continue
            before = len(found)
            if depth < max_depth:
                visit(child, depth + 1)
            if not include_probable or len(found) > before:
                continue
            # Nada encontrado abaixo: o próprio veredito decide (mesma lógica de `las check`).
            kind = classify(child, config)
            if kind.verdict == "probable_project":
                found.append((child, "probable_project"))
            elif kind.verdict == "root":
                found.extend((sub, "project") for sub in kind.subprojects)

    visit(folder, 1)
    return sorted(found, key=lambda item: item[0])


def find_subprojects(folder: Path, config: Config, max_depth: int | None = None) -> list[Path]:
    """Subpastas que são projetos (`.git` ou manifesto)."""
    return [p for p, _ in discover_projects(folder, config, max_depth)]


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
        raise NotADirectoryError(t("error.not_a_folder", path=folder))

    def make(
        verdict: Verdict, status: str, evidence: list[Evidence], note_key: str | None = None, params: dict | None = None, **kw
    ) -> KindResult:
        claim = Claim(
            id="project.kind",
            category="project",
            label=t("claim.kind", lang=DEFAULT_LANG),
            value=verdict,
            status=status,
            evidence=evidence,
            source="detector:project_kind",
            detected_at=utcnow(),
            note=t(note_key, lang=DEFAULT_LANG, **(params or {})) if note_key else None,
            label_key="claim.kind",
            note_key=note_key,
            params=params,
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
            note_key="note.kind.root",
            params={"n": len(subprojects)},
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
            note_key="note.kind.subfolder",
            params={"root": str(project_root)},
            project_root=project_root,
        )

    # 4) e 5) contar ficheiros de código
    entries = list(islice(ProjectFS(folder, config).walk(), config.kind_max_files))
    code = [e for e in entries if is_code(e.extension)]
    pct = round(100 * len(code) / len(entries)) if entries else 0
    count_ev = gen_evidence(".", "count", "ev.kind.code_share", n=len(code), total=len(entries), pct=pct)
    if len(code) >= config.probable_min_code_files:
        evidence = [count_ev] + [
            gen_evidence(e.path, "file", "ev.code_file") for e in code[:5]
        ]
        return make(
            "probable_project",
            "inferred",
            evidence,
            note_key="note.kind.probable",
        )

    evidence = [
        gen_evidence(".", "count", "ev.kind.no_manifests"),
        gen_evidence(".", "git", "ev.kind.no_git"),
        count_ev,
    ]
    return make("not_a_project", "confirmed", evidence)


def _marker_evidence(marker: str, prefix: str = "") -> Evidence:
    if marker == ".git":
        return gen_evidence(f"{prefix}.git", "git", "ev.kind.git")
    return gen_evidence(f"{prefix}{marker}", "manifest", "ev.kind.manifest")
