"""Detetores `database`, `frameworks` e `external_services`.

Todos usam a tabela `tech.TECHS` e a mesma regra de promoção (SPEC.md, secção 4):
- dependência declarada sozinha            -> inferred
- dependência + uso no código              -> confirmed
- uso no código sem dependência declarada  -> confirmed, com nota
- só indícios de configuração (.env, ...)  -> inferred
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from ..code import code_index
from ..knowledge import in_non_product_dir
from ..models import Claim, Evidence
from ..project import Project
from ..tech import CATEGORY_PREFIX, TECHS, Tech, matches, matches_any, techs_in
from .base import Detector, gen_evidence, register
from .manifests import parse_manifests

MAX_EVIDENCE = 12
USAGES_PER_FILE = 2
PYTHON_STDLIB = frozenset({"sqlite3"})

ENV_FILES = frozenset({".env.example", ".env.sample", ".env.template", ".env.dist", ".env.local.example", "example.env"})
COMPOSE_FILES = frozenset({"docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"})
DOCKER_IMAGES = {
    "postgres": "postgresql",
    "postgis/postgis": "postgresql",
    "mysql": "mysql",
    "mariadb": "mysql",
    "mongo": "mongodb",
    "redis": "redis",
    "redis/redis-stack": "redis",
    "ollama/ollama": "ollama",
}
PRISMA_PROVIDERS = {"postgresql": "postgresql", "mysql": "mysql", "sqlite": "sqlite", "mongodb": "mongodb", "cockroachdb": "postgresql"}
ENV_LINE = re.compile(r"^\s*(?:export\s+)?([A-Z][A-Z0-9_]*)\s*=\s*(.*)$")
IMAGE_LINE = re.compile(r"""^\s*image:\s*["']?([\w./-]+)""")
PRISMA_PROVIDER = re.compile(r"""^\s*provider\s*=\s*["'](\w+)["']""")


@dataclass
class Signals:
    deps: list[Evidence] = field(default_factory=list)
    code: list[Evidence] = field(default_factory=list)
    weak: list[Evidence] = field(default_factory=list)
    stdlib_only: bool = False  # código vem de um import da biblioteca padrão

    def add(self, bucket: list[Evidence], ev: Evidence) -> None:
        if not any(e.file == ev.file and e.line == ev.line for e in bucket):
            bucket.append(ev)


def _import_matches(tech: Tech, module: str, package: str) -> bool:
    for pattern in tech.imports:
        if matches(pattern, package) or matches(pattern, module):
            return True
        if not pattern.endswith("*") and (module.startswith(pattern + ".") or module.startswith(pattern + "/")):
            return True
    return False


def tech_signals(project: Project) -> dict[str, Signals]:
    """Todas as provas por tecnologia (com cache)."""
    if "tech_signals" in project.cache:
        return project.cache["tech_signals"]
    signals: dict[str, Signals] = {t.id: Signals() for t in TECHS}

    # 1) dependências declaradas
    for m in parse_manifests(project):
        for dep in m.dependencies:
            for tech in TECHS:
                patterns = tech.npm if m.ecosystem == "npm" else tech.pypi if m.ecosystem == "pypi" else ()
                if matches_any(patterns, dep.name):
                    signals[tech.id].add(signals[tech.id].deps, project.evidence(m.path, dep.line, "dependency"))

    # 2) código: imports, utilização dos nomes importados e literais de texto
    index = code_index(project)
    for path, facts in index.files.items():
        if in_non_product_dir(path):
            continue  # código de testes/exemplos não prova o que o projeto usa
        for imp in facts.imports:
            package = index.external_package(facts, imp)
            if package is None:
                continue
            for tech in TECHS:
                if not _import_matches(tech, imp.module, package):
                    continue
                sig = signals[tech.id]
                stdlib = facts.language == "python" and package in PYTHON_STDLIB
                sig.stdlib_only = (sig.stdlib_only or not sig.code) and stdlib
                sig.add(sig.code, project.evidence(path, imp.line, "code"))
                used = 0
                for call in facts.calls:
                    if used >= USAGES_PER_FILE:
                        break
                    if _uses(call.callee, imp.names) and call.line != imp.line:
                        sig.add(sig.code, project.evidence(path, call.line, "code"))
                        used += 1
        for lit in facts.strings:
            lowered = lit.value.strip().lower()
            for tech in TECHS:
                # "postgres://" sozinho é uma menção (ex.: uma tabela como esta); só um
                # URL ou connection string completa prova uso.
                if lowered not in tech.strings and any(fragment in lowered for fragment in tech.strings):
                    signals[tech.id].add(signals[tech.id].code, project.evidence(path, lit.line, "code"))

    # 3) configuração: .env.example, docker-compose, ficheiros de config, schema.prisma
    for entry in project.readable():
        if in_non_product_dir(entry.path):
            continue
        name = PurePosixPath(entry.path).name
        if name in ENV_FILES:
            _scan_env_file(project, entry.path, signals)
        elif name in COMPOSE_FILES:
            for i, line in enumerate(project.lines(entry.path), start=1):
                match = IMAGE_LINE.match(line)
                if match:
                    image = match.group(1).split(":")[0]
                    tech_id = DOCKER_IMAGES.get(image) or DOCKER_IMAGES.get(image.split("/")[-1])
                    if tech_id:
                        signals[tech_id].add(signals[tech_id].weak, project.evidence(entry.path, i, "config"))
        if name == "schema.prisma":
            for i, line in enumerate(project.lines(entry.path), start=1):
                match = PRISMA_PROVIDER.match(line)
                if match and match.group(1) in PRISMA_PROVIDERS:
                    tech_id = PRISMA_PROVIDERS[match.group(1)]
                    # O provider do Prisma é configuração explícita da BD usada.
                    signals[tech_id].add(signals[tech_id].code, project.evidence(entry.path, i, "config"))
        for tech in TECHS:
            if name in tech.config_files:
                signals[tech.id].add(signals[tech.id].weak, gen_evidence(entry.path, "config", "ev.config_file"))

    project.cache["tech_signals"] = signals
    return signals


def _uses(callee: str, names: list[str]) -> bool:
    callee = callee.removeprefix("new ")
    return any(callee == n or callee.startswith(n + ".") for n in names if n)


def _scan_env_file(project: Project, path: str, signals: dict[str, Signals]) -> None:
    for i, line in enumerate(project.lines(path), start=1):
        match = ENV_LINE.match(line)
        if not match:
            continue
        key, value = match.group(1), match.group(2).lower()
        for tech in TECHS:
            if matches_any(tech.env, key) or (value and any(f in value for f in tech.strings)):
                signals[tech.id].add(signals[tech.id].weak, project.evidence(path, i, "config"))


class TechDetector(Detector):
    category: str
    unknown_id: str | None = None

    def detect(self, project: Project) -> list[Claim]:
        signals = tech_signals(project)
        claims = []
        for tech in techs_in(self.category):
            sig = signals[tech.id]
            if not (sig.deps or sig.code or sig.weak):
                continue
            note = None
            if sig.code:
                status = "confirmed"
                if not sig.deps and not sig.stdlib_only:
                    note = "note.tech.code_only"
            elif sig.deps:
                status = "inferred"
                note = "note.tech.dep_only"
            else:
                status = "inferred"
                note = "note.tech.config_only"
            evidence = (sig.deps + sig.code + sig.weak)[:MAX_EVIDENCE]
            claims.append(
                self.claim(
                    project,
                    id=f"{CATEGORY_PREFIX[self.category]}.{tech.id}",
                    category=self.category,
                    label_key=f"category.{self.category}",
                    value=tech.name,
                    status=status,
                    evidence=evidence,
                    note_key=note,
                )
            )
        if not claims and self.unknown_id:
            claims.append(
                self.claim(
                    project,
                    id=self.unknown_id,
                    category=self.category,
                    label_key=f"category.{self.category}",
                    status="unknown",
                    note_key=f"note.{self.category}.none",
                )
            )
        return claims


@register
class DatabaseDetector(TechDetector):
    name = "database"
    category = "database"
    unknown_id = "db.engine"


@register
class OrmDetector(TechDetector):
    name = "orm"
    category = "orm"


@register
class FrameworksDetector(TechDetector):
    name = "frameworks"
    category = "framework"
    unknown_id = "framework.main"


@register
class ExternalServicesDetector(TechDetector):
    name = "external_services"
    category = "service"
    unknown_id = "service.external"
