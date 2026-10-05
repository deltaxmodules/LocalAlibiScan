from __future__ import annotations

import hashlib
import shutil
from dataclasses import replace
import subprocess
from pathlib import Path

import pytest

from localalibiscan.config import Config, load_config

FIXTURES = Path(__file__).parent / "fixtures"

ALL_FIXTURES = [
    "node_sqlite_lying_readme",
    "python_fastapi_openai",
    "python_dep_unused",
    "empty_project",
    "monorepo_mixed",
    "projects_root",
    "not_a_project",
    "loose_scripts",
]

# Uma pasta `.git` não pode ser guardada dentro de outro repositório, por isso
# os projetos que precisam de git recebem `git init` numa cópia temporária.
GIT_PROJECTS = {
    "projects_root": ["alpha_api", "beta_web", "gamma_cli"],  # delta_tool fica sem git
    "empty_project": ["."],  # "só um README", mas num repositório: é um projeto
}


def tree_hash(root: Path) -> dict[str, str]:
    """Hash de todos os ficheiros fora de `.localalibi/` (para provar só leitura)."""
    out = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if ".localalibi" in rel.parts or ".git" in rel.parts or not path.is_file():
            continue
        out[rel.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def _git_init(path: Path) -> None:
    run = lambda *args: subprocess.run(["git", *args], cwd=path, check=True, capture_output=True)
    run("init", "-q")
    run("add", "-A")
    run("-c", "user.name=test", "-c", "user.email=test@example.com", "commit", "-q", "-m", "init")


@pytest.fixture(autouse=True)
def isolated_user_config(tmp_path_factory, monkeypatch) -> None:
    """Os testes nunca leem o ~/.localalibi/config.toml real do utilizador."""
    monkeypatch.setenv("LOCALALIBI_CONFIG", str(tmp_path_factory.getbasetemp() / "no-config.toml"))
    monkeypatch.delenv("LOCALALIBI_OLLAMA_MODEL", raising=False)
    monkeypatch.delenv("LOCALALIBI_OLLAMA_URL", raising=False)


@pytest.fixture
def config(tmp_path: Path) -> Config:
    """Config isolada: a pasta pessoal e a de configuração ficam em tmp."""
    return replace(load_config(), home_dir=tmp_path, user_config_dir=tmp_path / "user_cfg")


@pytest.fixture
def fixture_copy(tmp_path: Path):
    """Copia uma fixture para uma pasta temporária (com git onde for preciso)."""

    def _copy(name: str) -> Path:
        dest = tmp_path / "work" / name
        shutil.copytree(FIXTURES / name, dest, ignore=shutil.ignore_patterns(".localalibi"))
        for sub in GIT_PROJECTS.get(name, []):
            _git_init(dest / sub)
        return dest

    return _copy
