"""Tabelas de conhecimento partilhadas pelos detetores."""

from __future__ import annotations

# Extensão -> linguagem de programação (conta para "ficheiros de código").
CODE_LANGUAGES: dict[str, str] = {
    ".py": "Python",
    ".pyw": "Python",
    ".ipynb": "Jupyter Notebook",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".mts": "TypeScript",
    ".cts": "TypeScript",
    ".go": "Go",
    ".rs": "Rust",
    ".php": "PHP",
    ".rb": "Ruby",
    ".java": "Java",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".swift": "Swift",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".cc": "C++",
    ".hpp": "C++",
    ".cs": "C#",
    ".scala": "Scala",
    ".dart": "Dart",
    ".lua": "Lua",
    ".r": "R",
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".ps1": "PowerShell",
    ".vue": "Vue",
    ".svelte": "Svelte",
    ".sql": "SQL",
}

# Extensões contadas como linguagem mas que não são "código" por si só.
MARKUP_LANGUAGES: dict[str, str] = {
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sass": "SCSS",
    ".less": "Less",
}

# Manifestos que fazem de uma pasta um projeto. Os seis primeiros são lidos
# pelo detetor `manifests`; os restantes só contam para o veredito.
PARSED_MANIFESTS: dict[str, str] = {
    "package.json": "npm",
    "requirements.txt": "pypi",
    "pyproject.toml": "pypi",
    "go.mod": "go",
    "Cargo.toml": "cargo",
    "composer.json": "composer",
}
OTHER_MANIFESTS: frozenset[str] = frozenset(
    {
        "setup.py",
        "setup.cfg",
        "Pipfile",
        "Gemfile",
        "pom.xml",
        "build.gradle",
        "build.gradle.kts",
        "Package.swift",
        "pubspec.yaml",
        "mix.exs",
        "deno.json",
    }
)
MANIFEST_NAMES: frozenset[str] = frozenset(PARSED_MANIFESTS) | OTHER_MANIFESTS

ECOSYSTEM_LANGUAGE: dict[str, str] = {
    "npm": "Node.js",
    "pypi": "Python",
    "go": "Go",
    "cargo": "Rust",
    "composer": "PHP",
}

DOC_EXTENSIONS: frozenset[str] = frozenset({".md", ".markdown", ".rst", ".txt"})


def language_of(extension: str) -> str | None:
    return CODE_LANGUAGES.get(extension) or MARKUP_LANGUAGES.get(extension)


def is_code(extension: str) -> bool:
    return extension in CODE_LANGUAGES


# Pastas cujo código não é "do projeto" para efeitos de arranque/estrutura.
NON_PRODUCT_DIRS: frozenset[str] = frozenset(
    {"test", "tests", "__tests__", "spec", "fixtures", "examples", "example", "docs", "e2e"}
)


def in_non_product_dir(path: str) -> bool:
    return any(part.lower() in NON_PRODUCT_DIRS for part in path.split("/")[:-1])
