"""Contexto de um projeto em análise, partilhado pelos detetores."""

from __future__ import annotations

from datetime import datetime
from functools import cached_property
from pathlib import Path
from typing import Any

from .config import Config, load_config
from .fs import FileNotReadable, ProjectFS
from .models import Claim, Evidence, FileEntry, utcnow


class Project:
    def __init__(self, root: str | Path, config: Config | None = None) -> None:
        self.config = config or load_config()
        self.fs = ProjectFS(root, self.config)
        self.root = self.fs.root
        self.now: datetime = utcnow()
        # Dados derivados partilhados entre detetores (ex.: manifestos lidos).
        self.cache: dict[str, Any] = {}
        self._text: dict[str, str | None] = {}
        # Claims produzidos até agora, pela ordem dos detetores.
        self.claims: list[Claim] = []

    @cached_property
    def files(self) -> list[FileEntry]:
        return list(self.fs.walk())

    @cached_property
    def paths(self) -> set[str]:
        return {f.path for f in self.files}

    def readable(self) -> list[FileEntry]:
        return [f for f in self.files if f.readable]

    def text(self, rel: str) -> str | None:
        """Conteúdo de um ficheiro, ou None se não puder ser lido."""
        if rel not in self._text:
            try:
                self._text[rel] = self.fs.read_text(rel)
            except (FileNotReadable, OSError):
                self._text[rel] = None
        return self._text[rel]

    def lines(self, rel: str) -> list[str]:
        content = self.text(rel)
        return content.splitlines() if content is not None else []

    def evidence(self, rel: str, line: int | None, kind: str, snippet: str | None = None) -> Evidence:
        """Evidência com o excerto da linha indicada (se não for dado)."""
        if snippet is None and line:
            lines = self.lines(rel)
            snippet = lines[line - 1] if 0 < line <= len(lines) else ""
        return Evidence(file=rel, line=line, snippet=_clip(snippet or ""), kind=kind)


def _clip(text: str, limit: int = 160) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"
