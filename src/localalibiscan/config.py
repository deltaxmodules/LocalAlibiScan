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

# Um ficheiro com este nome trava a procura da raiz para cima
# (como GIT_CEILING_DIRECTORIES). Usado em tests/fixtures/.
CEILING_MARKER = ".localalibi-ceiling"


@dataclass(frozen=True)
class Config:
    excluded_dirs: frozenset[str] = field(default=FIXED_EXCLUDED_DIRS)
    max_file_size: int = DEFAULT_MAX_FILE_SIZE
    user_config_dir: Path = USER_CONFIG_DIR
    # A procura da raiz nunca sobe acima desta pasta.
    home_dir: Path = field(default_factory=Path.home)

    # --- Fase 1: veredito da pasta
    # Ficheiros de código (ou notebooks) para uma pasta sem manifesto nem .git
    # ser um "provável projeto".
    probable_min_code_files: int = 3
    # Subpastas-projeto necessárias para uma pasta ser uma "raiz".
    root_min_subprojects: int = 2
    # Níveis a descer à procura de subprojetos.
    root_max_depth: int = 2
    # Níveis a subir à procura da raiz de um projeto.
    subfolder_max_up: int = 5
    # Máximo de ficheiros percorridos só para decidir o veredito.
    kind_max_files: int = 20000
    # Profundidade máxima (em pastas) dos manifestos lidos.
    manifest_max_depth: int = 2


def load_config() -> Config:
    return Config()
