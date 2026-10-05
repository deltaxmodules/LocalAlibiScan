from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path

import pytest

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


@pytest.fixture
def fixture_copy(tmp_path: Path):
    """Copia uma fixture para uma pasta temporária (com git onde for preciso)."""

    def _copy(name: str) -> Path:
        dest = tmp_path / name
        shutil.copytree(FIXTURES / name, dest)
        for sub in GIT_PROJECTS.get(name, []):
            _git_init(dest / sub)
        return dest

    return _copy
