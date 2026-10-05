"""Detetores registados, pela ordem em que correm.

Para adicionar um detetor: criar o módulo com uma classe decorada com
`@register` e importá-lo aqui.
"""

from __future__ import annotations

from ..models import Claim
from ..project import Project
from .base import REGISTRY, Detector, register

# A ordem de importação é a ordem de execução.
from . import languages  # noqa: E402,F401
from . import manifests  # noqa: E402,F401
from . import project_type  # noqa: E402,F401
from . import entry_points  # noqa: E402,F401
from . import structure  # noqa: E402,F401
from . import docs  # noqa: E402,F401


def run_detectors(project: Project) -> list[Claim]:
    claims: list[Claim] = []
    seen: set[str] = set()
    for cls in REGISTRY:
        for claim in cls().detect(project):
            if claim.id in seen:
                raise ValueError(f"Claim duplicado: {claim.id} ({cls.name})")
            seen.add(claim.id)
            claims.append(claim)
    return claims


__all__ = ["Detector", "REGISTRY", "register", "run_detectors"]
