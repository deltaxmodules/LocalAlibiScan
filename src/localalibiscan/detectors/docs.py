"""Detetor `docs`: README e ficheiros de documentação encontrados."""

from __future__ import annotations

from pathlib import PurePosixPath

from ..knowledge import DOC_EXTENSIONS
from ..models import Claim
from ..project import Project
from .base import Detector, gen_evidence, register

MAX_EVIDENCE = 20
# Ficheiros .txt que são manifestos ou dados, não documentação.
NOT_DOCS = frozenset({"requirements.txt", "requirements-dev.txt", "constraints.txt", "license.txt"})


def is_doc(path: str) -> bool:
    p = PurePosixPath(path)
    return p.suffix.lower() in DOC_EXTENSIONS and p.name.lower() not in NOT_DOCS and not p.name.lower().startswith("requirements")


def readme_paths(project: Project) -> list[str]:
    return sorted(
        (
            f.path
            for f in project.files
            if PurePosixPath(f.path).name.lower().startswith("readme") and f.path.count("/") <= 1
        ),
        key=lambda p: (p.count("/"), p),
    )


@register
class DocsDetector(Detector):
    name = "docs"

    def detect(self, project: Project) -> list[Claim]:
        claims: list[Claim] = []
        readmes = readme_paths(project)
        if readmes:
            main = readmes[0]
            lines = project.lines(main)
            title_line = next((i for i, l in enumerate(lines, 1) if l.strip()), None)
            claims.append(
                self.claim(
                    project,
                    id="docs.readme",
                    category="docs",
                    label_key="claim.readme",
                    value=main,
                    status="confirmed",
                    evidence=[project.evidence(main, title_line, "doc")]
                    + [gen_evidence(p, "doc", "ev.other_readme") for p in readmes[1:MAX_EVIDENCE]],
                )
            )
        else:
            claims.append(
                self.claim(
                    project,
                    id="docs.readme",
                    category="docs",
                    label_key="claim.readme",
                    status="unknown",
                    note_key="note.readme.none",
                )
            )

        docs = [f.path for f in project.files if is_doc(f.path)]
        if docs:
            claims.append(
                self.claim(
                    project,
                    id="docs.files",
                    category="docs",
                    label_key="claim.docs",
                    value=docs,
                    status="confirmed",
                    evidence=[project.evidence(p, None, "doc", "") for p in docs[:MAX_EVIDENCE]],
                    note_key="note.files_count" if len(docs) > MAX_EVIDENCE else None,
                    params={"n": len(docs)} if len(docs) > MAX_EVIDENCE else None,
                )
            )
        return claims
