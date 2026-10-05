"""Detetor `entry_points`: como o projeto arranca."""

from __future__ import annotations

import re
from pathlib import PurePosixPath

from ..knowledge import in_non_product_dir
from ..models import Claim, Evidence
from ..project import Project
from .base import Detector, register
from .manifests import json_key_line, parse_manifests

ENTRY_FILENAMES = frozenset({"main.py", "app.py", "manage.py", "__main__.py", "wsgi.py", "asgi.py"})
MAIN_GUARD = re.compile(r"""^if\s+__name__\s*==\s*['"]__main__['"]\s*:""")
GO_MAIN = re.compile(r"^func\s+main\s*\(\s*\)")
STRENGTH = {"code": 0, "manifest": 1, "file": 2}
RUST_MAIN = re.compile(r"^(pub\s+)?(async\s+)?fn\s+main\s*\(")


@register
class EntryPointsDetector(Detector):
    name = "entry_points"

    def detect(self, project: Project) -> list[Claim]:
        found: list[tuple[str, Evidence]] = []

        for m in parse_manifests(project):
            if m.error or not isinstance(m.data, dict):
                continue
            prefix = f"{m.directory}/" if m.directory else ""
            if m.ecosystem == "npm":
                lines = project.lines(m.path)
                if isinstance(m.data.get("main"), str):
                    found.append(
                        (f"{prefix}{m.data['main']} (main)", project.evidence(m.path, json_key_line(lines, "main"), "manifest"))
                    )
                bin_ = m.data.get("bin")
                if isinstance(bin_, str):
                    found.append((f"{prefix}{bin_} (bin)", project.evidence(m.path, json_key_line(lines, "bin"), "manifest")))
                elif isinstance(bin_, dict):
                    for name in bin_:
                        found.append((f"{name} (bin)", project.evidence(m.path, json_key_line(lines, name, "bin"), "manifest")))
                for script in m.scripts:
                    if script.name in ("start", "dev", "serve"):
                        found.append(
                            (f"npm run {script.name}" + (f" em {m.directory}" if m.directory else ""),
                             project.evidence(m.path, script.line, "manifest"))
                        )
            elif m.path.endswith("pyproject.toml"):
                for script in m.scripts:
                    found.append((f"{script.name} → {script.command}", project.evidence(m.path, script.line, "manifest")))

        for entry in project.readable():
            if in_non_product_dir(entry.path):
                continue
            path = PurePosixPath(entry.path)
            if path.name in ENTRY_FILENAMES and len(path.parts) <= 3:
                found.append((entry.path, project.evidence(entry.path, None, "file", "nome de ponto de entrada")))
            if entry.extension == ".py":
                pattern = MAIN_GUARD
            elif entry.extension == ".go":
                pattern = GO_MAIN
            elif entry.extension == ".rs":
                pattern = RUST_MAIN
            else:
                continue
            for i, line in enumerate(project.lines(entry.path), start=1):
                if pattern.match(line):
                    found.append((entry.path, project.evidence(entry.path, i, "code")))
                    break

        if not found:
            return [
                self.claim(
                    project,
                    id="entry.points",
                    category="entry_point",
                    label="Pontos de entrada",
                    value=None,
                    status="unknown",
                    note="Nenhum ponto de entrada reconhecido",
                )
            ]

        # Agrupa por valor, mantendo todas as evidências e a ordem de descoberta.
        values: dict[str, list[Evidence]] = {}
        for value, ev in found:
            values.setdefault(value, []).append(ev)
        return [
            self.claim(
                project,
                id="entry.points",
                category="entry_point",
                label="Pontos de entrada",
                value=list(values),
                status="confirmed",
                evidence=sorted(
                    (ev for evs in values.values() for ev in evs),
                    key=lambda ev: STRENGTH.get(ev.kind, 9),
                ),
            )
        ]
