"""Índice de código de um projeto: factos por ficheiro e resolução de imports."""

from __future__ import annotations

from collections import Counter
from functools import cached_property
from pathlib import PurePosixPath

from ..project import Project
from .parser import FileFacts, Import, grammar_for, parse_source

JS_EXTENSIONS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts")


def package_of(module: str, language: str) -> str | None:
    """Pacote externo a que um import pertence, ou None se for relativo/local."""
    if not module or module.startswith((".", "/")):
        return None
    if language == "python":
        return module.split(".")[0]
    if module.startswith("node:"):
        return module
    parts = module.split("/")
    if module.startswith("@"):
        return "/".join(parts[:2]) if len(parts) >= 2 else module
    return parts[0]


class CodeIndex:
    def __init__(self, project: Project) -> None:
        self.project = project
        self.files: dict[str, FileFacts] = {}
        for entry in project.readable():
            grammar = grammar_for(entry.extension)
            if grammar is None:
                continue
            try:
                source = project.fs.read_bytes(entry.path)
            except OSError:
                continue
            self.files[entry.path] = parse_source(entry.path, source, grammar)

    def external_package(self, facts: FileFacts, imp: Import) -> str | None:
        pkg = package_of(imp.module, "python" if facts.language == "python" else "js")
        if pkg is None:
            return None
        if facts.language == "python" and self.resolve(facts.path, imp):
            return None  # módulo do próprio projeto com o mesmo nome
        return pkg

    # ------------------------------------------------------------- resolução

    def resolve(self, importer: str, imp: Import) -> str | None:
        """Ficheiro do projeto para onde um import aponta, se for local."""
        paths = self.project.paths
        base = PurePosixPath(importer).parent
        if self.files.get(importer) and self.files[importer].language == "python":
            module = imp.module
            if module.startswith("."):
                dots = len(module) - len(module.lstrip("."))
                pkg = base
                for _ in range(dots - 1):
                    pkg = pkg.parent
                rel = module.lstrip(".").replace(".", "/")
                candidates_base = [pkg / rel if rel else pkg]
            else:
                rel = module.replace(".", "/")
                candidates_base = [PurePosixPath(rel), PurePosixPath("src") / rel, base / rel]
            for cand in candidates_base:
                for path in (f"{cand}.py", f"{cand}/__init__.py"):
                    norm = _normalize(path)
                    if norm in paths:
                        return norm
            return None

        if not imp.module.startswith("."):
            return None
        target = _normalize(str(base / imp.module))
        if target in paths:
            return target
        stem = target
        for ext in (".js", ".jsx", ".mjs", ".cjs"):  # TS importa "./x.js" que é "./x.ts"
            if stem.endswith(ext):
                stem = stem[: -len(ext)]
                break
        for ext in JS_EXTENSIONS:
            if f"{stem}{ext}" in paths:
                return f"{stem}{ext}"
        for ext in JS_EXTENSIONS:
            if f"{stem}/index{ext}" in paths:
                return f"{stem}/index{ext}"
        return None

    @cached_property
    def inbound(self) -> Counter[str]:
        """Ficheiro -> número de ficheiros (distintos) que o importam."""
        counts: Counter[str] = Counter()
        for path, facts in self.files.items():
            targets = {self.resolve(path, imp) for imp in facts.imports}
            for target in targets - {None, path}:
                counts[target] += 1
        return counts


def _normalize(path: str) -> str:
    parts: list[str] = []
    for part in PurePosixPath(path).parts:
        if part == "..":
            if parts:
                parts.pop()
        elif part != ".":
            parts.append(part)
    return "/".join(parts)


def code_index(project: Project) -> CodeIndex:
    if "code_index" not in project.cache:
        project.cache["code_index"] = CodeIndex(project)
    return project.cache["code_index"]
