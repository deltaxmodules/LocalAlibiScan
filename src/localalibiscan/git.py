"""Git só de leitura (`rev-parse`, `log`, `status`) via subprocess.

`GIT_OPTIONAL_LOCKS=0` impede o git de escrever no índice durante leituras.
Nunca corre comandos que alterem o repositório.
"""

from __future__ import annotations

import os
import subprocess
from datetime import datetime
from pathlib import Path

ALLOWED = frozenset({"rev-parse", "log", "status"})
TIMEOUT = 10


def _git(repo: Path, *args: str) -> str | None:
    if not args or args[0] not in ALLOWED:
        raise ValueError(f"Comando git não permitido: {args[:1]}")
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0"}
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            env=env,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def is_repo(path: Path) -> bool:
    return (path / ".git").exists()


def head(path: Path) -> str | None:
    return _git(path, "rev-parse", "HEAD") if is_repo(path) else None


def last_commit_date(path: Path) -> datetime | None:
    if not is_repo(path):
        return None
    out = _git(path, "log", "-1", "--format=%cI")
    try:
        return datetime.fromisoformat(out) if out else None
    except ValueError:
        return None
