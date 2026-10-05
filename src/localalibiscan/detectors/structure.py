"""Detetor `structure`: pastas principais (1.º e 2.º nível com mais código)."""

from __future__ import annotations

from collections import Counter
from pathlib import PurePosixPath

from ..knowledge import is_code
from ..models import Claim
from ..project import Project
from .base import Detector, gen_evidence, register

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
                    label_key="claim.structure",
                    status="unknown",
                    note_key="note.structure.none",
                )
            ]

        top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:MAX_DIRS]
        return [
            self.claim(
                project,
                id="structure.main_dirs",
                category="structure",
                label_key="claim.structure",
                value=[{"path": d, "code_files": n} for d, n in top],
                status="confirmed",
                evidence=[gen_evidence(d, "count", "ev.code_files", n=n) for d, n in top],
            )
        ]
