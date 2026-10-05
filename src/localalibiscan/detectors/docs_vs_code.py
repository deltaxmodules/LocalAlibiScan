"""Detetor `docs_vs_code`: a documentação contradiz o código? (Fase 4)

- Documentação menciona X, código confirma Y do mesmo grupo exclusivo e X não
  tem qualquer sinal no código           -> `contradiction` (as duas evidências).
- Código confirma X (BD, framework, serviço) e a documentação não o menciona
                                          -> aviso "não documentado".
- Documentação menciona X e o código não tem qualquer sinal
                                          -> `inferred` "mencionado só na documentação".

Nunca edita a documentação.
"""

from __future__ import annotations

from ..doc_mentions import DocMention, doc_mentions
from ..models import Claim, Evidence
from ..project import Project
from ..tech import EXCLUSIVE_GROUPS, TECHS, Tech
from .base import Detector, gen_evidence, register
from .docs import readme_paths
from .technologies import Signals, tech_signals

UNDOCUMENTED_CATEGORIES = ("database", "framework", "service")
MAX_DOC_EVIDENCE = 5


def _has_signal(sig: Signals) -> bool:
    return bool(sig.deps or sig.code or sig.weak)


def _strongest_code_evidence(sig: Signals) -> list[Evidence]:
    """A melhor prova do código: uma linha de código e, se houver, a dependência."""
    out = sig.code[:1] + sig.deps[:1]
    return out or sig.weak[:1]


def _doc_evidence(mentions: list[DocMention]) -> list[Evidence]:
    seen = set()
    out = []
    for m in mentions:
        if (m.file, m.line) in seen:
            continue
        seen.add((m.file, m.line))
        out.append(Evidence(file=m.file, line=m.line, snippet=m.text[:160], kind="doc"))
    return out[:MAX_DOC_EVIDENCE]


@register
class DocsVsCodeDetector(Detector):
    name = "docs_vs_code"

    def detect(self, project: Project) -> list[Claim]:
        signals = tech_signals(project)
        mentions = doc_mentions(project)
        by_tech: dict[str, list[DocMention]] = {}
        for m in mentions:
            by_tech.setdefault(m.tech.id, []).append(m)
        by_line: dict[tuple[str, int], list[DocMention]] = {}
        for m in mentions:
            by_line.setdefault((m.file, m.line), []).append(m)
        confirmed = {t.id: t for t in TECHS if signals[t.id].code}
        claims: list[Claim] = []

        for tech_id, tech_mentions in by_tech.items():
            tech = tech_mentions[0].tech
            if _has_signal(signals[tech_id]):
                continue  # mencionado e com sinais no código: coerente
            group = EXCLUSIVE_GROUPS.get(tech_id)
            rivals = [
                t for t in confirmed.values()
                if group and EXCLUSIVE_GROUPS.get(t.id) == group and t.id != tech_id
            ]
            rival_ids = {t.id for t in rivals}
            # Só frases claras do README provam uma contradição. Uma linha que
            # também nomeia o rival é uma comparação ("X em vez de Y", tabelas).
            clear = [
                m for m in tech_mentions
                if not m.ambiguous
                and m.in_readme
                and not any(o.tech.id in rival_ids for o in by_line.get((m.file, m.line), []))
            ]
            if clear and rivals:
                rival = rivals[0]
                claims.append(
                    self.claim(
                        project,
                        id=f"docs.contradiction.{tech_id}",
                        category="docs_vs_code",
                        label_key="claim.docs_vs_code",
                        value_key="value.docs_contradiction",
                        status="contradiction",
                        evidence=_doc_evidence(clear) + _strongest_code_evidence(signals[rival.id]),
                        note_key="note.docs_contradiction",
                        params={"doc": tech.name, "code": rival.name},
                    )
                )
            else:
                claims.append(
                    self.claim(
                        project,
                        id=f"docs.only.{tech_id}",
                        category="docs_vs_code",
                        label_key="claim.docs_only",
                        value=tech.name,
                        status="inferred",
                        evidence=_doc_evidence(tech_mentions),
                        note_key=(
                            "note.docs_only"
                            if any(not m.ambiguous for m in tech_mentions)
                            else "note.docs_only.ambiguous"
                        ),
                    )
                )

        readmes = readme_paths(project)
        if readmes:
            for tech in confirmed.values():
                if not _is_reportable(tech) or tech.id in by_tech:
                    continue
                claims.append(
                    self.claim(
                        project,
                        id=f"docs.undocumented.{tech.id}",
                        category="docs_vs_code",
                        label_key="claim.undocumented",
                        value=tech.name,
                        status="confirmed",
                        evidence=_strongest_code_evidence(signals[tech.id])
                        + [gen_evidence(readmes[0], "doc", "ev.not_mentioned", tech=tech.name)],
                        note_key="note.undocumented",
                    )
                )
        return claims


def _is_reportable(tech: Tech) -> bool:
    return tech.category in UNDOCUMENTED_CATEGORIES or any(c in UNDOCUMENTED_CATEGORIES for c in tech.also)
