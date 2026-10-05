"""Extrator determinista de afirmações da documentação (Fase 4).

Procura os nomes da tabela `tech.TECHS` em README e ficheiros Markdown,
guardando ficheiro, linha e frase. Nunca altera a documentação.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cache
from pathlib import PurePosixPath

from .project import Project
from .tech import CASE_SENSITIVE_DOC_NAMES, TECHS, Tech

DOC_SUFFIXES = frozenset({".md", ".markdown", ".rst"})
SKIP_NAMES = ("changelog", "history", "license", "contributing", "code_of_conduct", "security")
SKIP_DIRS = frozenset({"test", "tests", "__tests__", "fixtures", "examples", "example", "e2e", "spec"})
# Instruções para agentes de IA, não documentação do projeto (têm tabelas de alternativas).
AGENT_FILES = frozenset({"claude.md", "agents.md", "gemini.md", "copilot-instructions.md", "cursor.md", "llms.txt"})
DOC_DIRS = frozenset({"docs", "doc", "documentation"})
URL = re.compile(r"\b(?:https?|ftp)://\S+|\bwww\.\S+")
NEGATION = re.compile(
    r"\b(no|not|without|sem|não|nao|nunca|never|instead of|em vez de|rather than|avoid|evitar)\s+(\S+\s+){0,2}$",
    re.IGNORECASE,
)

# Frases que falam de mudanças: a tecnologia pode ser a antiga (limitação conhecida).
MIGRATION = re.compile(
    r"\b(migr\w*|switch\w*|moved|replac\w*|substitu\w*|mud[áa]mos|mudou|troc\w*|pass[áa]mos|"
    r"deprecated|legacy|previously|anteriormente|antig[oa]s?|em vez de|instead of|no longer|já não)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class DocMention:
    tech: Tech
    file: str
    line: int
    text: str
    ambiguous: bool  # migração, negação ou comparação: não serve para contradições

    @property
    def in_readme(self) -> bool:
        return PurePosixPath(self.file).name.lower().startswith("readme")


def is_doc_source(path: str) -> bool:
    """README (até 2 níveis), Markdown na raiz e em docs/. Nunca pastas ocultas."""
    p = PurePosixPath(path)
    name = p.name.lower()
    dirs = [part.lower() for part in p.parts[:-1]]
    if any(d.startswith(".") or d in SKIP_DIRS for d in dirs):
        return False
    if name.startswith(SKIP_NAMES) or name in AGENT_FILES:
        return False
    if name.startswith("readme"):
        return len(dirs) <= 2
    if p.suffix.lower() not in DOC_SUFFIXES:
        return False
    return not dirs or dirs[0] in DOC_DIRS


@cache
def _pattern(name: str) -> re.Pattern[str]:
    flags = 0 if name in CASE_SENSITIVE_DOC_NAMES else re.IGNORECASE
    return re.compile(rf"(?<![\w.-]){re.escape(name)}(?![\w-])", flags)


LIST_OR_HEADING = re.compile(r"^\s*([-*+]|\d+[.)]|#{1,6})\s")
SENTENCE_START = re.compile(r"(^|[.!?:]\s+)$")


def _find(name: str, line: str) -> tuple[bool, bool]:
    """(mencionado, negado) — negado: "no Redis", "sem PostgreSQL"."""
    found = negated = False
    for match in _pattern(name).finditer(line):
        before = line[: match.start()]
        if name in CASE_SENSITIVE_DOC_NAMES and not LIST_OR_HEADING.match(line):
            # "Click the button": palavra comum no início de uma frase normal.
            if SENTENCE_START.search(before.lstrip()):
                continue
        found = True
        negated = negated or bool(NEGATION.search(before))
    return found, negated


def doc_mentions(project: Project) -> list[DocMention]:
    if "doc_mentions" in project.cache:
        return project.cache["doc_mentions"]
    mentions: list[DocMention] = []
    for entry in project.readable():
        if not is_doc_source(entry.path):
            continue
        for i, raw in enumerate(project.lines(entry.path), start=1):
            line = URL.sub(" ", raw)
            if not line.strip():
                continue
            migration = bool(MIGRATION.search(line))
            for tech in TECHS:
                hits = [_find(n, line) for n in tech.names_in_docs()]
                if any(found for found, _ in hits):
                    negated = any(neg for _, neg in hits)
                    mentions.append(DocMention(tech, entry.path, i, raw.strip(), migration or negated))
    project.cache["doc_mentions"] = mentions
    return mentions
