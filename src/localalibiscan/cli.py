"""CLI `localalibiscan` / `las`."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .config import load_config
from .fs import ProjectFS

app = typer.Typer(
    help="LocalAlibiScan — every claim has an alibi.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()

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
