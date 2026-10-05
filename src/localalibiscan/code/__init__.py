"""Análise de código-fonte (Fase 2)."""

from .index import CodeIndex, code_index
from .parser import Call, Decorator, FileFacts, Import, StringLit, Symbol

__all__ = ["Call", "CodeIndex", "Decorator", "FileFacts", "Import", "StringLit", "Symbol", "code_index"]
