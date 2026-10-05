"""Arquitetura de detetores.

Cada detetor é uma classe com `detect(project) -> list[Claim]`, registada com
`@register`. Um detetor nunca depende de outro diretamente: o que for partilhado
(por ex. manifestos já lidos) vive em funções com cache em `project.cache`.
"""

from __future__ import annotations

from typing import Any, ClassVar

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
        label: str,
        value: Any,
        status: str,
        evidence: list[Evidence] | None = None,
        note: str | None = None,
    ) -> Claim:
        return Claim(
            id=id,
            category=category,
            label=label,
            value=value,
            status=status,
            evidence=evidence or [],
            source=f"detector:{self.name}",
            detected_at=project.now,
            note=note,
        )


def register(cls: type[Detector]) -> type[Detector]:
    REGISTRY.append(cls)
    return cls
