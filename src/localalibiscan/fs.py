"""Única camada de acesso a ficheiros.

Regras (ver CLAUDE.md):
- Leitura livre.
- Escrita só dentro de `<projeto>/.localalibi/` ou da pasta de configuração do
  utilizador. Qualquer outra tentativa lança `ReadOnlyViolation`.
- Percorrer respeita `.gitignore` (incluindo os de subpastas) e as exclusões fixas.
- Ficheiros grandes, binários ou ligações simbólicas são registados mas não lidos.

Nenhum outro módulo deve usar `open()`, `Path.write_*` ou `os.remove` diretamente.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path, PurePosixPath

from pathspec import GitIgnoreSpec

from .config import BINARY_SNIFF_BYTES, OUTPUT_DIR_NAME, Config, load_config
from .models import FileEntry, SkipReason


class ReadOnlyViolation(PermissionError):
    """Tentativa de escrita fora das pastas permitidas."""


class FileNotReadable(OSError):
    """Ficheiro que é registado mas não pode ser lido (grande, binário, ligação)."""


class ProjectFS:
    def __init__(self, root: str | os.PathLike[str], config: Config | None = None) -> None:
        self.root = Path(root).expanduser().resolve()
        if not self.root.is_dir():
            raise NotADirectoryError(f"Não é uma pasta: {self.root}")
        self.config = config or load_config()
        self.output_dir = self.root / OUTPUT_DIR_NAME

    # ------------------------------------------------------------------ escrita

    def _allowed_write_roots(self) -> list[Path]:
        roots = []
        for base in (self.output_dir, Path(self.config.user_config_dir).expanduser()):
            # Uma pasta de saída que é ligação simbólica podia apontar para
            # dentro do projeto: nunca a aceitamos.
            if base.is_symlink():
                continue
            roots.append(base.resolve())
        return roots

    def _check_writable(self, target: str | os.PathLike[str]) -> Path:
        path = Path(target)
        if not path.is_absolute():
            path = self.root / path
        resolved = path.resolve()
        for allowed in self._allowed_write_roots():
            if resolved != allowed and resolved.is_relative_to(allowed):
                return resolved
        raise ReadOnlyViolation(
            f"Escrita recusada: {path} está fora de {self.output_dir} "
            f"e de {self.config.user_config_dir}"
        )

    def ensure_output_dir(self) -> Path:
        """Cria `.localalibi/` com um `.gitignore` que se ignora a si próprio."""
        if self.output_dir.is_symlink():
            raise ReadOnlyViolation(f"{self.output_dir} é uma ligação simbólica")
        self.output_dir.mkdir(exist_ok=True)
        gitignore = self.output_dir / ".gitignore"
        if not gitignore.exists():
            self.write_text(gitignore, "*\n")
        return self.output_dir

    def write_text(self, target: str | os.PathLike[str], content: str) -> Path:
        path = self._check_writable(target)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def write_bytes(self, target: str | os.PathLike[str], content: bytes) -> Path:
        path = self._check_writable(target)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def writable_path(self, target: str | os.PathLike[str]) -> Path:
        """Caminho verificado para quem escreve por outra via (ex.: sqlite3)."""
        path = self._check_writable(target)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def delete(self, target: str | os.PathLike[str]) -> None:
        self._check_writable(target).unlink(missing_ok=True)

    # ------------------------------------------------------------------ leitura

    def _abs(self, rel: str | os.PathLike[str]) -> Path:
        path = Path(rel)
        return path if path.is_absolute() else self.root / path

    def read_bytes(self, rel: str | os.PathLike[str]) -> bytes:
        path = self._abs(rel)
        reason = self.skip_reason(path)
        if reason:
            raise FileNotReadable(f"{path} não é lido ({reason})")
        return path.read_bytes()

    def read_text(self, rel: str | os.PathLike[str]) -> str:
        return self.read_bytes(rel).decode("utf-8", errors="replace")

    def skip_reason(self, path: Path) -> SkipReason | None:
        try:
            if path.is_symlink():
                return "symlink"
            if path.stat().st_size > self.config.max_file_size:
                return "too_large"
            with path.open("rb") as fh:
                if b"\0" in fh.read(BINARY_SNIFF_BYTES):
                    return "binary"
        except OSError:
            return "unreadable"
        return None

    # ------------------------------------------------------------------ percorrer

    def walk(self) -> Iterator[FileEntry]:
        """Ficheiros que seriam analisados, em ordem determinista."""
        for rel, path in self._iter_files():
            try:
                size = path.lstat().st_size
            except OSError:
                continue
            yield FileEntry(
                path=rel,
                extension=path.suffix.lower(),
                size=size,
                skipped=self.skip_reason(path),
            )

    def stat_files(self) -> Iterator[tuple[str, int, int]]:
        """(caminho, mtime_ns, tamanho) sem abrir ficheiros: base da cache."""
        for rel, path in self._iter_files():
            try:
                st = path.lstat()
            except OSError:
                continue
            yield rel, st.st_mtime_ns, st.st_size

    def _iter_files(self) -> Iterator[tuple[str, Path]]:
        specs: dict[str, GitIgnoreSpec] = {}

        for dirpath, dirnames, filenames in os.walk(self.root, followlinks=False):
            current = Path(dirpath)
            rel_dir = current.relative_to(self.root).as_posix()
            rel_dir = "" if rel_dir == "." else rel_dir

            gitignore = current / ".gitignore"
            if gitignore.is_file() and not gitignore.is_symlink():
                lines = gitignore.read_text(encoding="utf-8", errors="replace").splitlines()
                specs[rel_dir] = GitIgnoreSpec.from_lines(lines)

            kept_dirs = []
            for name in sorted(dirnames):
                rel = _join(rel_dir, name)
                if name in self.config.excluded_dirs:
                    continue
                if (current / name).is_symlink():
                    continue
                if any((current / name / m).exists() for m in self.config.excluded_dir_markers):
                    continue
                if _is_ignored(specs, rel, is_dir=True):
                    continue
                kept_dirs.append(name)
            dirnames[:] = kept_dirs

            for name in sorted(filenames):
                rel = _join(rel_dir, name)
                if not _is_ignored(specs, rel, is_dir=False):
                    yield rel, current / name


def _join(rel_dir: str, name: str) -> str:
    return f"{rel_dir}/{name}" if rel_dir else name


def _is_ignored(specs: dict[str, GitIgnoreSpec], rel: str, *, is_dir: bool) -> bool:
    """Aplica os `.gitignore` do mais profundo para a raiz; o primeiro que decide ganha."""
    parts = PurePosixPath(rel).parts
    for depth in range(len(parts) - 1, -1, -1):
        base = "/".join(parts[:depth])
        spec = specs.get(base)
        if spec is None:
            continue
        sub = "/".join(parts[depth:]) + ("/" if is_dir else "")
        result = spec.check_file(sub)
        if result.include is not None:
            return result.include
    return False
