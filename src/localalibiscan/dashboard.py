"""Painel de todos os projetos de uma pasta raiz (Fase 3)."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .config import Config, load_config
from .detectors.project_kind import discover_projects
from .models import Claim, ProjectProfile
from .scan import scan


@dataclass
class Row:
    path: Path
    name: str
    verdict: str
    profile: ProjectProfile | None = None
    cached: bool = False
    error: str | None = None
    # "Mudou desde a última vez": resumo do diff, "—" (cache) ou "novo".
    changes: str = "—"

    def claims(self, prefix: str) -> list[Claim]:
        if not self.profile:
            return []
        return [c for c in self.profile.claims if c.id.startswith(prefix) and c.status != "unknown"]

    @staticmethod
    def _values(claims: list[Claim]) -> list[str]:
        ordered = sorted(claims, key=lambda c: c.status != "confirmed")
        return [f"{'' if c.status == 'confirmed' else c.symbol}{c.value}" for c in ordered]

    @property
    def project_type(self) -> str:
        claim = self.profile.get("project.type") if self.profile else None
        if not claim or claim.value is None:
            return "?"
        return f"{'' if claim.status == 'confirmed' else claim.symbol}{claim.value}"

    @property
    def stack(self) -> list[str]:
        frameworks = self._values(self.claims("framework."))
        if frameworks:
            return frameworks
        primary = self.profile.get("lang.primary") if self.profile else None
        return [primary.value] if primary and primary.value else []

    @property
    def databases(self) -> list[str]:
        return self._values(self.claims("db."))

    @property
    def services(self) -> list[str]:
        return self._values(self.claims("service."))

    @property
    def languages(self) -> list[str]:
        claim = self.profile.get("lang.breakdown") if self.profile else None
        return list(claim.value) if claim and isinstance(claim.value, dict) else []

    @property
    def last_change(self) -> datetime | None:
        return self.profile.last_change if self.profile else None

    @property
    def alerts(self) -> dict[str, int]:
        counts = {"contradiction": 0, "unknown": 0}
        for claim in self.profile.claims if self.profile else []:
            if claim.status in counts:
                counts[claim.status] += 1
        return counts


@dataclass
class Dashboard:
    root: Path
    rows: list[Row] = field(default_factory=list)
    elapsed: float = 0.0

    @property
    def cached_count(self) -> int:
        return sum(1 for r in self.rows if r.cached)


def build_dashboard(
    root: str | Path,
    config: Config | None = None,
    *,
    depth: int | None = None,
    language: str | None = None,
    use_cache: bool = True,
    on_project: Callable[[Path], None] | None = None,
) -> Dashboard:
    config = config or load_config()
    root = Path(root).expanduser().resolve()
    start = time.perf_counter()
    dashboard = Dashboard(root=root)

    for path, verdict in discover_projects(root, config, depth, include_probable=True):
        if on_project:
            on_project(path)
        row = Row(path=path, name=path.relative_to(root).as_posix(), verdict=verdict)
        try:
            result = scan(path, config, use_cache=use_cache)
            row.profile, row.cached = result.profile, result.cached
            if result.first_scan:
                row.changes = "novo"
            elif result.diff is not None:
                row.changes = "—" if result.diff.empty else result.diff.summary()
            row.verdict = result.kind.verdict
            if result.profile is None:
                row.error = f"não analisado: veredito «{result.kind.verdict}»"
        except Exception as exc:  # um projeto com problemas não deve parar o painel
            row.error = f"{type(exc).__name__}: {exc}"
        dashboard.rows.append(row)

    if language:
        wanted = language.lower()
        dashboard.rows = [r for r in dashboard.rows if any(wanted == lang.lower() for lang in r.languages)]

    dashboard.rows.sort(key=lambda r: (r.last_change is None, -(r.last_change.timestamp() if r.last_change else 0), r.name))
    dashboard.elapsed = time.perf_counter() - start
    return dashboard
