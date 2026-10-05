"""Configuração e constantes partilhadas.

Valores por omissão, depois `~/.localalibi/config.toml`, depois o ambiente.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# Pasta (dentro de cada projeto analisado) onde a ferramenta pode escrever.
OUTPUT_DIR_NAME = ".localalibi"

# Pasta de configuração do utilizador (única outra escrita permitida).
USER_CONFIG_DIR = Path.home() / ".localalibi"

# Pastas que contêm um destes ficheiros são ambientes, não código do projeto
# (ex.: um virtualenv com outro nome, como ".venv-build").
EXCLUDED_DIR_MARKERS: tuple[str, ...] = ("pyvenv.cfg",)
EXCLUDED_DIR_NAMES_EXTRA: frozenset[str] = frozenset({"site-packages"})

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
) | EXCLUDED_DIR_NAMES_EXTRA

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
    excluded_dir_markers: tuple[str, ...] = EXCLUDED_DIR_MARKERS
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

    # --- Fase 6: redação com LLM local (opcional)
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5-coder:7b"
    ollama_timeout: float = 180.0

    # --- Fase 9: língua da interface ([ui] language). None = automática (ver i18n.py).
    language: str | None = None


CONFIG_FILE_NAME = "config.toml"

def config_template() -> str:
    """Conteúdo de `las config --init`, com os comentários na língua da interface."""
    from .i18n import t

    return t("config.template")


class ConfigError(ValueError):
    """Ficheiro de configuração inválido."""


def _t(key: str) -> str:
    from .i18n import t

    return t(key)


def config_path() -> Path:
    import os

    custom = os.environ.get("LOCALALIBI_CONFIG")
    return Path(custom).expanduser() if custom else USER_CONFIG_DIR / CONFIG_FILE_NAME


def load_config(path: Path | None = None) -> Config:
    """Valores por omissão, depois `~/.localalibi/config.toml`, depois o ambiente."""
    import os
    import tomllib

    overrides: dict = {}
    file = path or config_path()
    if file.is_file():
        try:
            data = tomllib.loads(file.read_text(encoding="utf-8"))
        except (tomllib.TOMLDecodeError, OSError) as exc:
            raise ConfigError(f"{file}: {exc}") from exc
        scan = data.get("scan", {})
        if scan.get("ignore"):
            if not isinstance(scan["ignore"], list) or not all(isinstance(x, str) for x in scan["ignore"]):
                raise ConfigError(f"{file}: {_t('config.error.ignore')}")
            overrides["excluded_dirs"] = FIXED_EXCLUDED_DIRS | frozenset(scan["ignore"])
        if "max_file_size" in scan:
            overrides["max_file_size"] = int(scan["max_file_size"])
        if "depth" in data.get("dashboard", {}):
            overrides["root_max_depth"] = int(data["dashboard"]["depth"])
        ollama = data.get("ollama", {})
        for key, field_name, cast in (("url", "ollama_url", str), ("model", "ollama_model", str), ("timeout", "ollama_timeout", float)):
            if key in ollama:
                overrides[field_name] = cast(ollama[key])
        language = data.get("ui", {}).get("language")
        if language is not None:
            if not isinstance(language, str):
                raise ConfigError(f"{file}: {_t('config.error.language')}")
            overrides["language"] = language

    if os.environ.get("LOCALALIBI_OLLAMA_MODEL"):
        overrides["ollama_model"] = os.environ["LOCALALIBI_OLLAMA_MODEL"]
    if os.environ.get("LOCALALIBI_OLLAMA_URL"):
        overrides["ollama_url"] = os.environ["LOCALALIBI_OLLAMA_URL"]
    return Config(**overrides)
