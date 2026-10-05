"""Detetor `important_files`: ranking dos 10 ficheiros mais importantes.

Pontuação simples e determinista, a partir dos Claims já produzidos (pontos de
entrada, rotas, BD, serviços, manifestos, README) e do grafo de imports.
"""

from __future__ import annotations

from collections import defaultdict

from ..code import code_index
from ..knowledge import in_non_product_dir
from ..models import Claim, Evidence
from ..project import Project
from .base import Detector, register
from .routes import route_files

TOP = 10


@register
class ImportantFilesDetector(Detector):
    name = "important_files"

    def detect(self, project: Project) -> list[Claim]:
        score: dict[str, int] = defaultdict(int)
        reasons: dict[str, list[tuple[int, str]]] = defaultdict(list)

        def add(path: str, points: int, reason: str) -> None:
            if path in project.paths and reason not in (r for _, r in reasons[path]):
                score[path] += points
                reasons[path].append((points, reason))

        for claim in project.claims:
            code_files = {e.file for e in claim.evidence if e.kind == "code"}
            if claim.category == "entry_point":
                for ev in claim.evidence:
                    if ev.kind in ("code", "file"):
                        add(ev.file, 5, "Ponto de entrada")
            elif claim.category in ("database", "orm") and claim.status != "unknown":
                for f in code_files:
                    add(f, 3, f"Acesso à base de dados ({claim.value})")
            elif claim.category == "service" and claim.status != "unknown":
                for f in code_files:
                    add(f, 3, f"Usa {claim.value}")
            elif claim.id == "manifest.files":
                for ev in claim.evidence:
                    add(ev.file, 2, f"Manifesto ({ev.snippet})")
            elif claim.id == "docs.readme" and claim.value:
                add(claim.value, 2, "Documentação principal")

        for path, n in route_files(project).items():
            add(path, 2 + n, f"Define {n} rota{'s' if n != 1 else ''}")
        for path, n in code_index(project).inbound.items():
            add(path, min(n, 5), f"Importado por {n} ficheiro{'s' if n != 1 else ''}")

        ranked = sorted(
            (p for p in score if not in_non_product_dir(p)),
            key=lambda p: (-score[p], p),
        )[:TOP]
        if not ranked:
            return [
                self.claim(
                    project,
                    id="files.important",
                    category="important_files",
                    label="Ficheiros importantes",
                    value=None,
                    status="unknown",
                    note="Sem sinais suficientes para ordenar ficheiros",
                )
            ]

        items = []
        evidence = []
        for path in ranked:
            phrase = "; ".join(r for _, r in sorted(reasons[path], key=lambda x: -x[0])[:2])
            items.append({"path": path, "score": score[path], "reason": phrase})
            evidence.append(Evidence(file=path, kind="file", snippet=phrase))
        return [
            self.claim(
                project,
                id="files.important",
                category="important_files",
                label="Ficheiros importantes",
                value=items,
                status="confirmed",
                evidence=evidence,
            )
        ]
