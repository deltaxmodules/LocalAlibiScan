"""Detetor `important_files`: ranking dos 10 ficheiros mais importantes.

Pontuação simples e determinista, a partir dos Claims já produzidos (pontos de
entrada, rotas, BD, serviços, manifestos, README) e do grafo de imports.
"""

from __future__ import annotations

from collections import defaultdict

from ..code import code_index
from ..knowledge import in_non_product_dir
from ..i18n import DEFAULT_LANG, msg, t
from ..models import Claim
from ..project import Project
from .base import Detector, gen_evidence, register
from .routes import route_files

TOP = 10


@register
class ImportantFilesDetector(Detector):
    name = "important_files"

    def detect(self, project: Project) -> list[Claim]:
        score: dict[str, int] = defaultdict(int)
        reasons: dict[str, list[tuple[int, dict]]] = defaultdict(list)

        def add(path: str, points: int, key: str, **params) -> None:
            reason = msg(key, **params)
            if path in project.paths and reason not in (r for _, r in reasons[path]):
                score[path] += points
                reasons[path].append((points, reason))

        for claim in project.claims:
            code_files = {e.file for e in claim.evidence if e.kind == "code"}
            if claim.category == "entry_point":
                for ev in claim.evidence:
                    if ev.kind in ("code", "file"):
                        add(ev.file, 5, "reason.entry")
            elif claim.category in ("database", "orm") and claim.status != "unknown":
                for f in code_files:
                    add(f, 3, "reason.database", tech=claim.value)
            elif claim.category == "service" and claim.status != "unknown":
                for f in code_files:
                    add(f, 3, "reason.service", tech=claim.value)
            elif claim.id == "manifest.files":
                for ev in claim.evidence:
                    add(ev.file, 2, "reason.manifest", ecosystem=ev.snippet)
            elif claim.id == "docs.readme" and claim.value:
                add(claim.value, 2, "reason.readme")

        for path, n in route_files(project).items():
            add(path, 2 + n, "reason.routes.one" if n == 1 else "reason.routes.other", n=n)
        for path, n in code_index(project).inbound.items():
            add(path, min(n, 5), "reason.imported.one" if n == 1 else "reason.imported.other", n=n)

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
                    label_key="claim.important",
                    status="unknown",
                    note_key="note.important.none",
                )
            ]

        items = []
        evidence = []
        for path in ranked:
            top = [r for _, r in sorted(reasons[path], key=lambda x: -x[0])[:2]]
            phrase = t("reasons", lang=DEFAULT_LANG, reasons=top)
            # "reason" em inglês (compatível); "reasons" traduz-se ao mostrar.
            items.append({"path": path, "score": score[path], "reason": phrase, "reasons": top})
            evidence.append(gen_evidence(path, "file", "reasons", reasons=top))
        return [
            self.claim(
                project,
                id="files.important",
                category="important_files",
                label_key="claim.important",
                value=items,
                status="confirmed",
                evidence=evidence,
            )
        ]
