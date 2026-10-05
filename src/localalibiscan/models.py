"""Modelos de dados (Pydantic v2).

Os modelos `Claim` e `Evidence` chegam na Fase 1.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

SkipReason = Literal["too_large", "binary", "symlink", "unreadable"]


class FileEntry(BaseModel):
    """Um ficheiro que seria analisado."""

    path: str  # relativo à raiz do projeto, com "/" como separador
    extension: str  # ".py", ".ts", "" se não tiver
    size: int  # bytes
    skipped: SkipReason | None = None  # registado mas não lido

    @property
    def readable(self) -> bool:
        return self.skipped is None
