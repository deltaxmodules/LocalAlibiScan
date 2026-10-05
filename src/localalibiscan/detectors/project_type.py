"""Detetor `project_type`: Node/TS, Python, monorepo, etc."""

from __future__ import annotations

from collections import defaultdict

from ..knowledge import ECOSYSTEM_LANGUAGE, language_of
from ..models import Claim, Evidence
from ..project import Project
from .base import Detector, gen_evidence, register
from .languages import CODE_LANGUAGE_NAMES, language_counts
from .manifests import Manifest, json_key_line, parse_manifests


def _dir_contains(directory: str, path: str) -> bool:
    return directory == "" or path.startswith(directory + "/")


def describe_stack(project: Project, directory: str, manifests: list[Manifest]) -> str:
    """Ex.: "Node.js (TypeScript)", "Python", "Node.js + Python"."""
    parts: list[str] = []
    for eco in dict.fromkeys(m.ecosystem for m in manifests):
        name = ECOSYSTEM_LANGUAGE[eco]
        if eco == "npm":
            has_ts = any(
                language_of(f.extension) == "TypeScript"
                for f in project.files
                if _dir_contains(directory, f.path)
            ) or any(d.name == "typescript" for m in manifests for d in m.dependencies)
            name = "Node.js/TypeScript" if has_ts else "Node.js/JavaScript"
        parts.append(name)
    return " + ".join(parts)


def components(project: Project) -> dict[str, list[Manifest]]:
    """Pasta -> manifestos nela (a raiz é "")."""
    by_dir: dict[str, list[Manifest]] = defaultdict(list)
    for m in parse_manifests(project):
        by_dir[m.directory].append(m)
    return dict(by_dir)


@register
class ProjectTypeDetector(Detector):
    name = "project_type"

    def detect(self, project: Project) -> list[Claim]:
        by_dir = components(project)
        sub_dirs = [d for d in by_dir if d]
        root = by_dir.get("", [])
        workspace_ev = self._workspaces(project, root)

        if len(sub_dirs) >= 2 or (workspace_ev and sub_dirs):
            comps = [
                {"path": d, "type": describe_stack(project, d, by_dir[d])} for d in sorted(sub_dirs)
            ]
            evidence = list(workspace_ev)
            evidence += [
                project.evidence(m.path, None, "manifest", f"{c['path']}: {c['type']}")
                for c in comps
                for m in by_dir[c["path"]][:1]
            ]
            stacks = " + ".join(dict.fromkeys(c["type"] for c in comps))
            return [
                self.claim(
                    project,
                    id="project.type",
                    category="project",
                    label_key="claim.project_type",
                    value=f"Monorepo ({stacks})",
                    status="confirmed",
                    evidence=evidence,
                ),
                self.claim(
                    project,
                    id="project.components",
                    category="project",
                    label_key="claim.components",
                    value=comps,
                    status="confirmed",
                    evidence=evidence[len(workspace_ev):],
                ),
            ]

        manifests = root or [m for d in sub_dirs for m in by_dir[d]]
        if manifests:
            directory = "" if root else sub_dirs[0]
            return [
                self.claim(
                    project,
                    id="project.type",
                    category="project",
                    label_key="claim.project_type",
                    value=describe_stack(project, directory, manifests),
                    status="confirmed",
                    evidence=[project.evidence(m.path, None, "manifest", m.ecosystem) for m in manifests],
                )
            ]

        # Sem manifesto: só indícios pelas linguagens.
        code = [(lang, files) for lang, files in language_counts(project).items() if lang in CODE_LANGUAGE_NAMES]
        if code:
            lang, files = code[0]
            if lang == "Jupyter Notebook":
                lang = "Python"
            return [
                self.claim(
                    project,
                    id="project.type",
                    category="project",
                    label_key="claim.project_type",
                    value_key="value.scripts",
                    status="inferred",
                    evidence=[gen_evidence(f, "file", "ev.code_file") for f in files[:3]],
                    note_key="note.project_type.scripts",
                    params={"language": lang},
                )
            ]
        return [
            self.claim(
                project,
                id="project.type",
                category="project",
                label_key="claim.project_type",
                status="unknown",
                note_key="note.project_type.none",
            )
        ]

    @staticmethod
    def _workspaces(project: Project, root: list[Manifest]) -> list[Evidence]:
        for m in root:
            if m.ecosystem == "npm" and isinstance(m.data, dict) and m.data.get("workspaces"):
                line = json_key_line(project.lines(m.path), "workspaces")
                return [project.evidence(m.path, line, "manifest")]
        return []
