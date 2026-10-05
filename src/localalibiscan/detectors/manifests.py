"""Detetor `manifests`: dependências e scripts declarados, com linha de origem.

`parse_manifests(project)` é partilhada (com cache) por outros detetores.
"""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any

from ..knowledge import PARSED_MANIFESTS, in_non_product_dir
from ..models import Claim
from ..project import Project
from .base import Detector, register


@dataclass
class Dependency:
    name: str
    spec: str
    line: int | None
    dev: bool = False


@dataclass
class Script:
    name: str
    command: str
    line: int | None


@dataclass
class Manifest:
    path: str
    ecosystem: str
    data: Any = None
    dependencies: list[Dependency] = field(default_factory=list)
    scripts: list[Script] = field(default_factory=list)
    error: str | None = None

    @property
    def directory(self) -> str:
        parent = PurePosixPath(self.path).parent.as_posix()
        return "" if parent == "." else parent


def parse_manifests(project: Project) -> list[Manifest]:
    if "manifests" not in project.cache:
        found = []
        for entry in project.files:
            p = PurePosixPath(entry.path)
            if p.name not in PARSED_MANIFESTS or len(p.parts) - 1 > project.config.manifest_max_depth:
                continue
            if in_non_product_dir(entry.path):
                continue  # examples/, tests/, playground/...: não são dependências do projeto
            found.append(_parse(project, entry.path, PARSED_MANIFESTS[p.name]))
        project.cache["manifests"] = sorted(found, key=lambda m: (m.path.count("/"), m.path))
    return project.cache["manifests"]


def _parse(project: Project, path: str, ecosystem: str) -> Manifest:
    manifest = Manifest(path=path, ecosystem=ecosystem)
    text = project.text(path)
    if text is None:
        manifest.error = "ficheiro não lido (grande ou binário)"
        return manifest
    lines = text.splitlines()
    name = PurePosixPath(path).name
    try:
        if name in ("package.json", "composer.json"):
            _parse_json_manifest(manifest, text, lines)
        elif name == "requirements.txt":
            _parse_requirements(manifest, lines)
        elif name == "pyproject.toml":
            _parse_pyproject(manifest, text, lines)
        elif name == "go.mod":
            _parse_gomod(manifest, lines)
        elif name == "Cargo.toml":
            _parse_cargo(manifest, text, lines)
    except (ValueError, tomllib.TOMLDecodeError) as exc:
        manifest.error = f"não foi possível ler: {exc}"
    return manifest


# --------------------------------------------------------------------- localizar linhas


def json_key_line(lines: list[str], key: str, parent: str | None = None) -> int | None:
    """Linha (1-based) de `"key":`, dentro do objeto `"parent":` se for dado."""
    start, stop = 0, len(lines)
    if parent is not None:
        parent_line = _find(lines, rf'"{re.escape(parent)}"\s*:', 0, len(lines))
        if parent_line is None:
            return None
        start = parent_line  # índice da linha seguinte (0-based)
        indent = len(lines[parent_line - 1]) - len(lines[parent_line - 1].lstrip())
        # Se o objeto abre e fecha na mesma linha, procura só nela.
        if lines[parent_line - 1].rstrip().endswith("}") or lines[parent_line - 1].rstrip().endswith("},"):
            start, stop = parent_line - 1, parent_line
        else:
            for i in range(start, len(lines)):
                stripped = lines[i].strip()
                if stripped.startswith(("}", "]")) and len(lines[i]) - len(lines[i].lstrip()) <= indent:
                    stop = i
                    break
    return _find(lines, rf'"{re.escape(key)}"\s*:', start, stop)


def toml_key_line(lines: list[str], section: str, key: str) -> int | None:
    """Linha de `key =` dentro de `[section]`."""
    header = re.compile(rf"^\s*\[{re.escape(section)}\]\s*(#.*)?$")
    start = next((i + 1 for i, l in enumerate(lines) if header.match(l)), None)
    if start is None:
        return None
    stop = next((i for i in range(start, len(lines)) if re.match(r"^\s*\[", lines[i])), len(lines))
    return _find(lines, rf'^\s*["\']?{re.escape(key)}["\']?\s*=', start, stop)


def text_line(lines: list[str], needle: str, start: int = 0) -> int | None:
    for i in range(start, len(lines)):
        if needle in lines[i]:
            return i + 1
    return None


def _find(lines: list[str], pattern: str, start: int, stop: int) -> int | None:
    rx = re.compile(pattern)
    for i in range(start, stop):
        if rx.search(lines[i]):
            return i + 1
    return None


# --------------------------------------------------------------------- formatos


def _parse_json_manifest(m: Manifest, text: str, lines: list[str]) -> None:
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("o conteúdo não é um objeto JSON")
    m.data = data
    sections = (
        [("dependencies", False), ("devDependencies", True), ("peerDependencies", False), ("optionalDependencies", False)]
        if m.ecosystem == "npm"
        else [("require", False), ("require-dev", True)]
    )
    for section, dev in sections:
        deps = data.get(section)
        if not isinstance(deps, dict):
            continue
        for name, spec in deps.items():
            m.dependencies.append(Dependency(name, str(spec), json_key_line(lines, name, section), dev))
    scripts = data.get("scripts")
    if isinstance(scripts, dict):
        for name, cmd in scripts.items():
            m.scripts.append(Script(name, str(cmd), json_key_line(lines, name, "scripts")))


_REQ = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(\[[^\]]*\])?\s*(.*)$")


def pep508_name(requirement: str) -> tuple[str, str] | None:
    match = _REQ.match(requirement)
    if not match:
        return None
    name = re.sub(r"[-_.]+", "-", match.group(1)).lower()
    spec = match.group(3).split(";")[0].strip()
    return name, spec


def _parse_requirements(m: Manifest, lines: list[str]) -> None:
    for i, raw in enumerate(lines, start=1):
        line = raw.split(" #")[0].strip()
        if not line or line.startswith(("#", "-", "git+", "http")):
            continue
        parsed = pep508_name(line)
        if parsed:
            m.dependencies.append(Dependency(parsed[0], parsed[1], i))


def _parse_pyproject(m: Manifest, text: str, lines: list[str]) -> None:
    data = tomllib.loads(text)
    m.data = data
    project = data.get("project", {})

    def add_list(reqs: list[Any], dev: bool) -> None:
        for req in reqs:
            parsed = pep508_name(str(req))
            if parsed:
                line = text_line(lines, f'"{req}"') or text_line(lines, f"'{req}'")
                m.dependencies.append(Dependency(parsed[0], parsed[1], line, dev))

    add_list(project.get("dependencies", []), False)
    for group, reqs in project.get("optional-dependencies", {}).items():
        add_list(reqs, dev=group in ("dev", "test", "tests", "lint", "docs"))
    for group, reqs in data.get("dependency-groups", {}).items():
        add_list([r for r in reqs if isinstance(r, str)], dev=True)

    poetry = data.get("tool", {}).get("poetry", {})
    for section, dev in (("dependencies", False), ("dev-dependencies", True)):
        for name, spec in poetry.get(section, {}).items():
            if name.lower() == "python":
                continue
            line = toml_key_line(lines, f"tool.poetry.{section}", name)
            m.dependencies.append(Dependency(name.lower(), _toml_spec(spec), line, dev))

    for name, target in project.get("scripts", {}).items():
        m.scripts.append(Script(name, str(target), toml_key_line(lines, "project.scripts", name)))
    for name, target in poetry.get("scripts", {}).items():
        m.scripts.append(Script(name, str(target), toml_key_line(lines, "tool.poetry.scripts", name)))


def _parse_gomod(m: Manifest, lines: list[str]) -> None:
    in_block = False
    for i, raw in enumerate(lines, start=1):
        line = raw.split("//")[0].strip()
        if line.startswith("require ("):
            in_block = True
            continue
        if in_block and line == ")":
            in_block = False
            continue
        if line.startswith("require "):
            line = line[len("require ") :]
        elif not in_block:
            continue
        parts = line.split()
        if len(parts) >= 2:
            indirect = "// indirect" in raw
            m.dependencies.append(Dependency(parts[0], parts[1], i, dev=indirect))


def _parse_cargo(m: Manifest, text: str, lines: list[str]) -> None:
    data = tomllib.loads(text)
    m.data = data
    for section, dev in (("dependencies", False), ("dev-dependencies", True), ("build-dependencies", True)):
        for name, spec in data.get(section, {}).items():
            m.dependencies.append(Dependency(name, _toml_spec(spec), toml_key_line(lines, section, name), dev))


def _toml_spec(spec: Any) -> str:
    if isinstance(spec, dict):
        return str(spec.get("version", ""))
    return str(spec)


# --------------------------------------------------------------------- detetor


@register
class ManifestsDetector(Detector):
    name = "manifests"

    def detect(self, project: Project) -> list[Claim]:
        manifests = parse_manifests(project)
        claims: list[Claim] = []
        if not manifests:
            return [
                self.claim(
                    project,
                    id="manifest.files",
                    category="manifest",
                    label="Manifestos",
                    value=None,
                    status="unknown",
                    note="Nenhum manifesto conhecido encontrado",
                )
            ]

        claims.append(
            self.claim(
                project,
                id="manifest.files",
                category="manifest",
                label="Manifestos",
                value=[m.path for m in manifests],
                status="confirmed",
                evidence=[project.evidence(m.path, None, "manifest", m.ecosystem) for m in manifests],
            )
        )

        deps: dict[str, Claim] = {}
        scripts: dict[str, Claim] = {}
        for m in manifests:
            if m.error:
                claims.append(
                    self.claim(
                        project,
                        id=f"manifest.error.{m.path}",
                        category="manifest",
                        label=f"Manifesto {m.path}",
                        value=None,
                        status="unknown",
                        evidence=[project.evidence(m.path, None, "manifest", m.error)],
                        note=m.error,
                    )
                )
                continue
            for dep in m.dependencies:
                ev = project.evidence(m.path, dep.line, "dependency")
                cid = f"dep.{m.ecosystem}.{dep.name}"
                if cid in deps:
                    deps[cid].evidence.append(ev)
                    deps[cid].value["dev"] = deps[cid].value["dev"] and dep.dev
                    continue
                deps[cid] = self.claim(
                    project,
                    id=cid,
                    category="dependency",
                    label=dep.name,
                    value={"name": dep.name, "spec": dep.spec, "ecosystem": m.ecosystem, "dev": dep.dev},
                    status="confirmed",
                    evidence=[ev],
                    note="declarada no manifesto",
                )
            for script in m.scripts:
                prefix = f"{m.directory}:" if m.directory else ""
                cid = f"script.{m.ecosystem}.{prefix}{script.name}"
                if cid in scripts:
                    continue
                scripts[cid] = self.claim(
                    project,
                    id=cid,
                    category="script",
                    label=f"{prefix}{script.name}",
                    value=script.command,
                    status="confirmed",
                    evidence=[project.evidence(m.path, script.line, "manifest")],
                )
        claims.extend(deps.values())
        claims.extend(scripts.values())
        return claims
