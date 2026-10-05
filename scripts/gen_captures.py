"""Gera as capturas do README/manual e a página de exemplo, na língua pedida.

    python scripts/gen_captures.py            # inglês (por omissão)
    LOCALALIBI_LANG=pt python scripts/gen_captures.py

- docs/img/{dashboard,contradiction}.svg e cópias em site/public/img/
  (a partir das fixtures, copiadas para uma pasta temporária "~/projects").
- site/public/example/index.html: o painel HTML de projetos open source
  conhecidos (clonados uma vez para .demo-cache/, como em demo-video.sh).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from rich.console import Console

from localalibiscan.config import load_config
from localalibiscan.dashboard import build_dashboard
from localalibiscan.html_report import render_html
from localalibiscan.render import render_claim, render_dashboard, sections
from localalibiscan.scan import scan

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
CACHE = ROOT / ".demo-cache"
DASHBOARD_FIXTURES = (
    "loose_scripts", "monorepo_mixed", "node_sqlite_lying_readme", "python_dep_unused", "python_fastapi_openai",
)
OSS = (
    "expressjs/express", "pallets/flask", "encode/httpx", "fastapi/full-stack-fastapi-template",
    "gothinkster/node-express-realworld-example-app", "openai/openai-quickstart-node", "vitejs/vite",
)


def copy_tree(src: Path, dest: Path) -> None:
    shutil.copytree(src, dest, symlinks=True, ignore=shutil.ignore_patterns(".localalibi"))


def svg(console: Console, title: str, *outputs: Path) -> None:
    text = console.export_svg(title=title)
    for out in outputs:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"escrito {out.relative_to(ROOT)}")


def captures(work: Path) -> None:
    config = load_config()
    projects = work / "projects"
    for name in DASHBOARD_FIXTURES:
        copy_tree(FIXTURES / name, projects / name)
    build_dashboard(projects, config)  # primeira análise: a segunda mostra a cache
    board = build_dashboard(projects, config)
    board.root = Path("~/projects")

    console = Console(record=True, width=150, force_terminal=True, color_system="truecolor")
    console.print("[dim]$[/] las dashboard ~/projects\n")
    render_dashboard(console, board)
    svg(console, "las dashboard", ROOT / "docs/img/dashboard.svg", ROOT / "site/public/img/dashboard.svg")

    profile = scan(projects / "node_sqlite_lying_readme", config, use_cache=True).profile
    console = Console(record=True, width=110, force_terminal=True, color_system="truecolor")
    console.print("[dim]$[/] las scan ~/projects/node_sqlite_lying_readme [dim](excerpt)[/]")
    by_cat: dict[str, list] = {}
    for claim in profile.claims:
        by_cat.setdefault(claim.category, []).append(claim)
    for cat, title in sections(by_cat):
        if cat in ("database", "docs_vs_code") and by_cat.get(cat):
            console.print(f"\n[bold underline]{title}[/]")
            for claim in by_cat[cat]:
                render_claim(console, claim, all_evidence=True)
    svg(console, "las scan", ROOT / "docs/img/contradiction.svg", ROOT / "site/public/img/contradiction.svg")


def example_page(work: Path) -> None:
    CACHE.mkdir(exist_ok=True)
    root = work / "oss-examples"
    for repo in OSS:
        name = repo.split("/")[1]
        if not (CACHE / name).is_dir():
            subprocess.run(["git", "clone", "-q", "--depth", "1", f"https://github.com/{repo}.git", str(CACHE / name)], check=True)
        copy_tree(CACHE / name, root / name)
    board = build_dashboard(root, load_config())
    board.root = Path("oss-examples")
    out = ROOT / "site/public/example/index.html"
    out.write_text(render_html(board), encoding="utf-8")
    print(f"escrito {out.relative_to(ROOT)} ({len(board.rows)} projetos)")


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        captures(work)
        if "--no-example" not in sys.argv:
            example_page(work)
    return 0


if __name__ == "__main__":
    sys.exit(main())
