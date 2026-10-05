"""Arquitetura de detetores.

Cada detetor é uma classe com `detect(project) -> list[Claim]`, registada com
`@register`. Um detetor nunca depende de outro diretamente: o que for partilhado
(por ex. manifestos já lidos) vive em funções com cache em `project.cache`.
"""

from __future__ import annotations

from typing import Any, ClassVar

from ..i18n import DEFAULT_LANG, t
from ..models import Claim, Evidence
from ..project import Project

REGISTRY: list[type[Detector]] = []


class Detector:
    name: ClassVar[str]

    def detect(self, project: Project) -> list[Claim]:  # pragma: no cover - interface
        raise NotImplementedError

    def claim(
        self,
        project: Project,
        *,
        id: str,
        category: str,
        status: str,
        value: Any = None,
        label: str | None = None,
        evidence: list[Evidence] | None = None,
        note: str | None = None,
        label_key: str | None = None,
        value_key: str | None = None,
        note_key: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> Claim:
        """Texto gerado vai por chave: grava-se em inglês e traduz-se ao mostrar."""
        p = params or {}
        if label_key:
            label = t(label_key, lang=DEFAULT_LANG, **p)
        if value_key:
            value = t(value_key, lang=DEFAULT_LANG, **p)
        if note_key:
            note = t(note_key, lang=DEFAULT_LANG, **p)
        return Claim(
            id=id,
            category=category,
            label=label or id,
            value=value,
            status=status,
            evidence=evidence or [],
            source=f"detector:{self.name}",
            detected_at=project.now,
            note=note,
            label_key=label_key,
            value_key=value_key,
            note_key=note_key,
            params=params or None,
        )


def gen_evidence(file: str, kind: str, key: str, line: int | None = None, **params: Any) -> Evidence:
    """Evidência cujo excerto é texto gerado (traduzível), não uma linha do ficheiro."""
    return Evidence(
        file=file,
        line=line,
        kind=kind,
        snippet=t(key, lang=DEFAULT_LANG, **params),
        snippet_key=key,
        params=params or None,
    )


def register(cls: type[Detector]) -> type[Detector]:
    REGISTRY.append(cls)
    return cls
