"""Detetor `structure`: pastas principais (1.º e 2.º nível com mais código)."""

from __future__ import annotations

from collections import Counter
from pathlib import PurePosixPath

from ..knowledge import is_code
from ..models import Claim, Evidence
from ..project import Project
from .base import Detector, register

MAX_DIRS = 8


@register
class StructureDetector(Detector):
    name = "structure"

    def detect(self, project: Project) -> list[Claim]:
        counts: Counter[str] = Counter()
        for entry in project.files:
            if not is_code(entry.extension):
                continue
            parts = PurePosixPath(entry.path).parts[:-1]
            if not parts:
                counts["."] += 1
            for depth in (1, 2):
                if len(parts) >= depth:
                    counts["/".join(parts[:depth])] += 1

        if not counts:
            return [
                self.claim(
                    project,
                    id="structure.main_dirs",
                    category="structure",
                    label="Pastas principais",
                    value=None,
                    status="unknown",
                    note="Nenhum ficheiro de código para organizar",
                )
            ]

        top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:MAX_DIRS]
        return [
            self.claim(
                project,
                id="structure.main_dirs",
                category="structure",
                label="Pastas principais",
                value=[{"path": d, "code_files": n} for d, n in top],
                status="confirmed",
                evidence=[
                    Evidence(file=d, kind="count", snippet=f"{n} ficheiros de código") for d, n in top
                ],
            )
        ]
