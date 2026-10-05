from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

import pytest

from localalibiscan.config import FIXED_EXCLUDED_DIRS, load_config
from localalibiscan.fs import FileNotReadable, ProjectFS, ReadOnlyViolation

from .conftest import FIXTURES, tree_hash


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    (root / "main.py").write_text("print('hi')\n")
    return root


@pytest.fixture
def pfs(project: Path, tmp_path: Path) -> ProjectFS:
    config = replace(load_config(), user_config_dir=tmp_path / "user_cfg")
    return ProjectFS(project, config)


def paths(pfs: ProjectFS) -> list[str]:
    return sorted(e.path for e in pfs.walk())


# --------------------------------------------------------------------- escrita


@pytest.mark.parametrize(
    "target",
    [
        "main.py",  # ficheiro do projeto
        "new_file.txt",  # ficheiro novo na raiz
        "src/x.py",
        ".localalibi/../main.py",  # escapar com ..
        ".localalibi",  # a própria pasta
        "/tmp/localalibi_escape.txt",  # caminho absoluto fora
    ],
)
def test_write_outside_output_dir_raises(pfs: ProjectFS, project: Path, target: str) -> None:
    before = tree_hash(project)
    with pytest.raises(ReadOnlyViolation):
        pfs.write_text(target, "x")
    with pytest.raises(ReadOnlyViolation):
        pfs.write_bytes(target, b"x")
    with pytest.raises(ReadOnlyViolation):
        pfs.delete(target)
    assert tree_hash(project) == before
    assert not Path("/tmp/localalibi_escape.txt").exists()


def test_write_inside_output_dir_allowed(pfs: ProjectFS, project: Path) -> None:
    pfs.ensure_output_dir()
    assert (project / ".localalibi/.gitignore").read_text() == "*\n"
    pfs.write_text(".localalibi/project.json", "{}")
    pfs.write_text(project / ".localalibi/sub/deep.md", "ok")
    assert (project / ".localalibi/project.json").read_text() == "{}"
    assert (project / ".localalibi/sub/deep.md").read_text() == "ok"


def test_write_in_user_config_dir_allowed(pfs: ProjectFS, tmp_path: Path) -> None:
    pfs.write_text(tmp_path / "user_cfg" / "dashboard.html", "<html>")
    assert (tmp_path / "user_cfg/dashboard.html").exists()


def test_symlink_inside_output_dir_cannot_escape(pfs: ProjectFS, project: Path) -> None:
    pfs.ensure_output_dir()
    os.symlink(project / "main.py", project / ".localalibi/link.py")
    with pytest.raises(ReadOnlyViolation):
        pfs.write_text(".localalibi/link.py", "hacked")
    assert (project / "main.py").read_text() == "print('hi')\n"


def test_output_dir_as_symlink_is_refused(pfs: ProjectFS, project: Path) -> None:
    (project / "src").mkdir()
    os.symlink(project / "src", project / ".localalibi")
    with pytest.raises(ReadOnlyViolation):
        pfs.write_text(".localalibi/x.txt", "x")
    with pytest.raises(ReadOnlyViolation):
        pfs.ensure_output_dir()
    assert list((project / "src").iterdir()) == []


# --------------------------------------------------------------------- percorrer


def test_fixed_exclusions(pfs: ProjectFS, project: Path) -> None:
    for name in FIXED_EXCLUDED_DIRS:
        (project / name).mkdir(exist_ok=True)
        (project / name / "inside.js").write_text("x")
        (project / "pkg" / name).mkdir(parents=True, exist_ok=True)
        (project / "pkg" / name / "nested.js").write_text("x")
    assert paths(pfs) == ["main.py"]


def test_respects_gitignore(pfs: ProjectFS, project: Path) -> None:
    (project / ".gitignore").write_text("*.log\nsecret/\n!keep.log\n/only_root.txt\n")
    (project / "debug.log").write_text("x")
    (project / "keep.log").write_text("x")
    (project / "only_root.txt").write_text("x")
    (project / "secret").mkdir()
    (project / "secret/key.txt").write_text("x")
    (project / "sub").mkdir()
    (project / "sub/only_root.txt").write_text("x")
    (project / "sub/trace.log").write_text("x")
    assert paths(pfs) == [".gitignore", "keep.log", "main.py", "sub/only_root.txt"]


def test_nested_gitignore(pfs: ProjectFS, project: Path) -> None:
    (project / ".gitignore").write_text("*.tmp\n")
    (project / "pkg").mkdir()
    (project / "pkg/.gitignore").write_text("generated/\n!important.tmp\n")
    (project / "pkg/generated").mkdir()
    (project / "pkg/generated/a.py").write_text("x")
    (project / "pkg/important.tmp").write_text("x")
    (project / "pkg/other.tmp").write_text("x")
    (project / "generated").mkdir()
    (project / "generated/b.py").write_text("x")  # regra de pkg/ não se aplica aqui
    assert paths(pfs) == [
        ".gitignore",
        "generated/b.py",
        "main.py",
        "pkg/.gitignore",
        "pkg/important.tmp",
    ]


def test_large_and_binary_files_registered_not_read(project: Path) -> None:
    config = replace(load_config(), max_file_size=100)
    pfs = ProjectFS(project, config)
    (project / "big.txt").write_text("a" * 101)
    (project / "image.png").write_bytes(b"\x89PNG\r\n\x00\x00data")
    entries = {e.path: e for e in pfs.walk()}
    assert entries["big.txt"].skipped == "too_large"
    assert entries["big.txt"].size == 101
    assert entries["image.png"].skipped == "binary"
    assert entries["main.py"].skipped is None
    with pytest.raises(FileNotReadable):
        pfs.read_text("big.txt")
    with pytest.raises(FileNotReadable):
        pfs.read_bytes("image.png")
    assert pfs.read_text("main.py") == "print('hi')\n"


def test_symlinks_not_followed(pfs: ProjectFS, project: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "elsewhere.py").write_text("x")
    os.symlink(outside, project / "linked_dir")
    os.symlink(outside / "elsewhere.py", project / "linked_file.py")
    entries = {e.path: e for e in pfs.walk()}
    assert "linked_dir/elsewhere.py" not in entries
    assert entries["linked_file.py"].skipped == "symlink"


def test_entry_metadata(pfs: ProjectFS) -> None:
    (entry,) = list(pfs.walk())
    assert entry.extension == ".py"
    assert entry.size == len("print('hi')\n")


def test_walk_node_fixture_skips_node_modules() -> None:
    found = [e.path for e in ProjectFS(FIXTURES / "node_sqlite_lying_readme").walk()]
    assert "src/db/database.ts" in found
    assert "package.json" in found
    assert not any("node_modules" in p for p in found)


def test_walk_marks_binaries_in_not_a_project() -> None:
    entries = {e.path: e for e in ProjectFS(FIXTURES / "not_a_project").walk()}
    assert entries["photos/beach.jpg"].skipped == "binary"
    assert entries["photos/sunset.png"].skipped == "binary"
    assert entries["documents/shopping_list.txt"].skipped is None


def test_any_virtualenv_is_excluded(pfs: ProjectFS, project: Path) -> None:
    venv = project / ".venv-build"
    (venv / "lib/python3.12/site-packages/pkg").mkdir(parents=True)
    (venv / "pyvenv.cfg").write_text("home = /usr/bin\n")
    (venv / "lib/python3.12/site-packages/pkg/mod.py").write_text("x")
    vendored = project / "vendor/lib/site-packages"
    vendored.mkdir(parents=True)
    (vendored / "other.py").write_text("x")
    assert paths(pfs) == ["main.py"]
