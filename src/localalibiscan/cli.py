"""CLI `localalibiscan` / `las`."""

from __future__ import annotations

import shlex
from dataclasses import replace
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .config import load_config
from .detectors.project_kind import classify
from .fs import ProjectFS
from .dashboard import build_dashboard
from .html_report import render_html
from .render import render_dashboard, render_kind, render_profile
from .scan import scan as run_scan

app = typer.Typer(
    help="LocalAlibiScan — every claim has an alibi.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console(soft_wrap=True)

SKIP_LABELS = {
    "too_large": "grande, não lido",
    "binary": "binário, não lido",
    "symlink": "ligação, não lido",
    "unreadable": "ilegível",
}


def _version(value: bool) -> None:
    if value:
        console.print(f"localalibiscan {__version__}")
        raise typer.Exit()


@app.callback()
def root(
    version: Annotated[
        bool, typer.Option("--version", callback=_version, is_eager=True, help="Mostra a versão.")
    ] = False,
) -> None:
    """Diz o que cada projeto é, como está e o que mudou — com prova."""


@app.command()
def files(
    folder: Annotated[
        Path, typer.Argument(exists=True, file_okay=False, help="Pasta a percorrer.")
    ] = Path("."),
    max_size: Annotated[
        int | None,
        typer.Option("--max-size", help="Tamanho máximo em bytes para ler um ficheiro."),
    ] = None,
) -> None:
    """Lista os ficheiros que seriam analisados, com extensão e tamanho."""
    config = load_config()
    if max_size is not None:
        config = replace(config, max_file_size=max_size)
    pfs = ProjectFS(folder, config)

    table = Table(title=str(pfs.root), title_justify="left")
    table.add_column("Ficheiro", overflow="fold")
    table.add_column("Ext.")
    table.add_column("Tamanho", justify="right")
    table.add_column("Nota", style="yellow")

    total = skipped = total_bytes = 0
    for entry in pfs.walk():
        total += 1
        total_bytes += entry.size
        if entry.skipped:
            skipped += 1
        table.add_row(
            entry.path,
            entry.extension or "—",
            _human_size(entry.size),
            SKIP_LABELS.get(entry.skipped or "", ""),
        )

    console.print(table)
    console.print(
        f"{total} ficheiros, {_human_size(total_bytes)}"
        + (f", {skipped} registados mas não lidos" if skipped else "")
    )


FolderArg = Annotated[
    Path, typer.Argument(exists=True, file_okay=False, help="Pasta a analisar.")
]


@app.command()
def check(folder: FolderArg = Path(".")) -> None:
    """Mostra só o veredito da pasta e as suas evidências, sem análise."""
    render_kind(console, classify(folder, load_config()))


@app.command()
def scan(
    folder: FolderArg = Path("."),
    force: Annotated[
        bool, typer.Option("--force", help="Analisa mesmo que a pasta não pareça um projeto.")
    ] = False,
    evidence: Annotated[
        bool, typer.Option("--evidence", help="Mostra todas as evidências de cada afirmação.")
    ] = False,
) -> None:
    """Analisa a pasta e mostra o perfil, com estado e evidência por afirmação."""
    result = run_scan(folder, load_config(), force=force)
    if result.profile is None:
        render_kind(console, result.kind)
        console.print("\n[dim]Análise não feita. Use --force para analisar mesmo assim.[/]")
        raise typer.Exit(code=2)
    render_profile(console, result.profile, all_evidence=evidence)
    if result.output:
        console.print(f"[dim]Perfil guardado em {result.output}[/]", highlight=False)


@app.command()
def dashboard(
    folder: FolderArg = Path("."),
    html: Annotated[
        bool, typer.Option("--html", help="Gera ~/.localalibi/dashboard.html (autónomo, sem rede).")
    ] = False,
    lang: Annotated[
        str | None, typer.Option("--lang", help="Mostra só projetos com esta linguagem.")
    ] = None,
    depth: Annotated[
        int | None, typer.Option("--depth", help="Níveis a descer à procura de projetos.")
    ] = None,
    no_cache: Annotated[
        bool, typer.Option("--no-cache", help="Reanalisa todos os projetos.")
    ] = False,
) -> None:
    """Painel com todos os projetos de uma pasta raiz."""
    config = load_config()
    kind = classify(folder, config)
    if kind.analyzable:
        # A própria pasta é um projeto: mostra o perfil dele.
        result = run_scan(folder, config, use_cache=not no_cache)
        assert result.profile is not None
        render_profile(console, result.profile)
        console.print(
            f"\n[dim]Esta pasta é um projeto, não uma raiz. Para o perfil completo: "
            f"[bold]las scan {shlex.quote(str(kind.path))}[/][/]",
            highlight=False,
        )
        return

    with console.status("A procurar projetos…") as status:
        board = build_dashboard(
            folder,
            config,
            depth=depth,
            language=lang,
            use_cache=not no_cache,
            on_project=lambda p: status.update(f"A analisar {p.name}…"),
        )
    if not board.rows:
        render_kind(console, kind)
        console.print("\n[dim]Nenhum projeto encontrado nesta pasta.[/]")
        raise typer.Exit(code=2)

    render_dashboard(console, board)
    if html:
        out = ProjectFS(board.root, config).write_text(
            config.user_config_dir / "dashboard.html", render_html(board)
        )
        console.print(f"Relatório HTML: [bold]{out}[/]", highlight=False)


def _human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def main() -> None:
    app()


if __name__ == "__main__":
    main()
