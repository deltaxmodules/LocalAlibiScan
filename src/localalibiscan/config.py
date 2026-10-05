"""Configuração e constantes partilhadas.

Por agora só valores por omissão; o ficheiro ~/.localalibi/config.toml chega na Fase 8.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# Pasta (dentro de cada projeto analisado) onde a ferramenta pode escrever.
OUTPUT_DIR_NAME = ".localalibi"

# Pasta de configuração do utilizador (única outra escrita permitida).
USER_CONFIG_DIR = Path.home() / ".localalibi"

# Pastas ignoradas sempre, independentemente do .gitignore.
FIXED_EXCLUDED_DIRS: frozenset[str] = frozenset(
    {
        "node_modules",
        ".venv",
        "venv",
        "dist",
        "build",
        ".git",
        "__pycache__",
        ".next",
        "target",
        OUTPUT_DIR_NAME,
    }
)

# Ficheiros acima deste tamanho são registados mas não lidos.
DEFAULT_MAX_FILE_SIZE = 1024 * 1024  # 1 MB

# Bytes inspecionados para decidir se um ficheiro é binário.
BINARY_SNIFF_BYTES = 8192


@dataclass(frozen=True)
class Config:
    excluded_dirs: frozenset[str] = field(default=FIXED_EXCLUDED_DIRS)
    max_file_size: int = DEFAULT_MAX_FILE_SIZE
    user_config_dir: Path = USER_CONFIG_DIR


def load_config() -> Config:
    return Config()
