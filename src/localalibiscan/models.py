"""Modelos de dados (Pydantic v2).

`Claim` e `Evidence` são o contrato central (SPEC.md, secção 4): nunca mudam de
forma incompatível. Os campos `*_key` + `params` (Fase 9) são opcionais: dizem
como traduzir o texto gerado; o texto em `label`/`note`/`snippet` fica em inglês.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, model_serializer

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
    # Fase 9: o excerto é texto gerado (não uma linha do ficheiro) e traduz-se assim.
    snippet_key: str | None = None
    params: dict[str, Any] | None = None

    @model_serializer(mode="wrap")
    def _drop_empty_keys(self, handler):
        return _without_empty_i18n(handler(self))

    def location(self) -> str:
        return f"{self.file}:{self.line}" if self.line else self.file


I18N_FIELDS = ("label_key", "value_key", "note_key", "snippet_key", "params")


def _without_empty_i18n(data):
    """Campos de tradução vazios não se gravam: o JSON mantém a forma da secção 4."""
    if isinstance(data, dict):
        for name in I18N_FIELDS:
            if name in data and data[name] is None:
                del data[name]
    return data


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
    # Fase 9: chaves de tradução (ver i18n.py). Ausentes em perfis antigos.
    label_key: str | None = None
    value_key: str | None = None
    note_key: str | None = None
    params: dict[str, Any] | None = None

    @model_serializer(mode="wrap")
    def _drop_empty_keys(self, handler):
        return _without_empty_i18n(handler(self))

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
    # Cache (Fase 3): se a impressão digital não mudou, o perfil é reutilizado.
    fingerprint: str | None = None
    git_head: str | None = None
    last_change: datetime | None = None
    last_change_source: Literal["git", "files"] | None = None

    def get(self, claim_id: str) -> Claim | None:
        return next((c for c in self.claims if c.id == claim_id), None)
