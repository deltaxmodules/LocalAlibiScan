"""Modelos de dados (Pydantic v2).

`Claim` e `Evidence` são o contrato central (SPEC.md, secção 4): nunca mudam de
forma incompatível.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

SkipReason = Literal["too_large", "binary", "symlink", "unreadable"]

Status = Literal["confirmed", "inferred", "contradiction", "unknown"]

STATUS_SYMBOL: dict[str, str] = {
    "confirmed": "✓",
    "inferred": "≈",
    "contradiction": "⚠",
    "unknown": "?",
}

EvidenceKind = Literal[
    "dependency",  # linha de um manifesto que declara uma dependência
    "manifest",  # o próprio manifesto, ou um campo dele
    "code",  # linha de código-fonte
    "file",  # existência de um ficheiro ou pasta
    "doc",  # linha de documentação
    "count",  # contagem de ficheiros
    "git",  # informação do git
    "config",  # ficheiros de configuração (.env.example, ...)
]


class FileEntry(BaseModel):
    """Um ficheiro que seria analisado."""

    path: str  # relativo à raiz do projeto, com "/" como separador
    extension: str  # ".py", ".ts", "" se não tiver
    size: int  # bytes
    skipped: SkipReason | None = None  # registado mas não lido

    @property
    def readable(self) -> bool:
        return self.skipped is None


class Evidence(BaseModel):
    file: str  # relativo à pasta analisada (pode começar por "../")
    line: int | None = None  # 1-based; None quando a prova é o ficheiro inteiro
    snippet: str = ""
    kind: EvidenceKind

    def location(self) -> str:
        return f"{self.file}:{self.line}" if self.line else self.file


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


class Claim(BaseModel):
    id: str
    category: str
    label: str
    value: Any = None
    status: Status
    evidence: list[Evidence] = Field(default_factory=list)
    source: str
    detected_at: datetime = Field(default_factory=utcnow)
    note: str | None = None

    @property
    def symbol(self) -> str:
        return STATUS_SYMBOL[self.status]


class ProjectProfile(BaseModel):
    """Conteúdo de `.localalibi/project.json`."""

    tool: str = "localalibiscan"
    version: str
    root: str
    verdict: str
    forced: bool = False
    scanned_at: datetime
    claims: list[Claim]

    def get(self, claim_id: str) -> Claim | None:
        return next((c for c in self.claims if c.id == claim_id), None)
