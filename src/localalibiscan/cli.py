"""CLI `localalibiscan` / `las`."""

from __future__ import annotations

import shlex
import sys
from datetime import datetime
from dataclasses import replace
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from . import __version__
from .config import CONFIG_TEMPLATE, FIXED_EXCLUDED_DIRS, config_path, load_config
from .detectors.project_kind import classify
from .fs import ProjectFS
from .dashboard import build_dashboard
from .html_report import render_html
from .ask import ask as ask_project
from .drafting import Overview, generate_overview, overview_markdown
from .drafting import explain as explain_project
from .history import diff_snapshots, list_snapshots
from .llm import OllamaClient
from .project import Project
from .render import (
    section_keys,
    render_ask,
    render_dashboard,
    render_diff,
    render_explanation,
    render_kind,
    render_profile,
)
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
    only: Annotated[
        str | None,
        typer.Option("--only", help="Só estas secções, ex.: database,framework,route,docs_vs_code."),
    ] = None,
) -> None:
    """Analisa a pasta e mostra o perfil, com estado e evidência por afirmação."""
    result = run_scan(folder, load_config(), force=force)
    if result.profile is None:
        render_kind(console, result.kind)
        console.print("\n[dim]Análise não feita. Use --force para analisar mesmo assim.[/]")
        raise typer.Exit(code=2)
    render_profile(console, result.profile, all_evidence=evidence, only=section_keys(only))
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


@app.command()
def refresh(
    folder: FolderArg = Path("."),
    force: Annotated[
        bool, typer.Option("--force", help="Analisa mesmo que a pasta não pareça um projeto.")
    ] = False,
) -> None:
    """Nova análise e o que mudou desde a anterior, em linguagem de arquitetura."""
    result = run_scan(folder, load_config(), force=force)
    if result.profile is None:
        render_kind(console, result.kind)
        console.print("\n[dim]Análise não feita. Use --force para analisar mesmo assim.[/]")
        raise typer.Exit(code=2)
    console.print(f"[bold]{result.profile.root}[/]", highlight=False)
    if result.first_scan or result.diff is None:
        console.print("[dim]Primeira análise: o próximo refresh vai comparar com esta.[/]")
        return
    render_diff(console, result.diff)


@app.command()
def history(folder: FolderArg = Path(".")) -> None:
    """Lista as análises anteriores, com um resumo de uma linha."""
    snaps = list_snapshots(folder)
    if not snaps:
        console.print("[dim]Sem histórico. Corra «las scan» ou «las refresh» primeiro.[/]")
        raise typer.Exit(code=2)
    table = Table(title=str(Path(folder).resolve()), title_justify="left")
    table.add_column("#", justify="right")
    table.add_column("Data")
    table.add_column("HEAD")
    table.add_column("Ficheiros", justify="right")
    table.add_column("Mudanças")
    prev = None
    for snap in snaps:
        summary = "primeira análise" if prev is None else diff_snapshots(prev, snap).summary()
        table.add_row(
            str(snap.id),
            snap.scanned_at.astimezone().strftime("%Y-%m-%d %H:%M"),
            (snap.git_head or "—")[:8],
            str(len(snap.files)),
            summary,
        )
        prev = snap
    console.print(table)


@app.command()
def explain(
    folder: FolderArg = Path("."),
    no_llm: Annotated[
        bool, typer.Option("--no-llm", help="Não usa o Ollama: mostra só factos.")
    ] = False,
    model: Annotated[
        str | None, typer.Option("--model", help="Modelo do Ollama (por omissão o da configuração).")
    ] = None,
) -> None:
    """Explique-me este projeto: perguntas fixas respondidas com factos (e IA opcional)."""
    config = load_config()
    result = run_scan(folder, config, use_cache=True)
    if result.profile is None:
        render_kind(console, result.kind)
        console.print("\n[dim]Não é um projeto: nada para explicar. Use «las scan --force» primeiro.[/]")
        raise typer.Exit(code=2)

    client, llm_off_reason = _llm_client(config, no_llm, model)

    pfs = ProjectFS(result.kind.path, config)

    def read(rel: str) -> str | None:
        try:
            return pfs.read_text(rel)
        except OSError:
            return None

    with console.status("A redigir com o modelo local…" if client else "A preparar…"):
        exp = explain_project(result.profile, client, root=pfs.root, read=read)
        overview = generate_overview(result.profile, client) if client else Overview(None, None, llm_off_reason)
    if llm_off_reason and not exp.llm_error:
        exp.llm_error = llm_off_reason
    render_explanation(console, exp)

    out = pfs.write_text(
        pfs.output_dir / "overview.md",
        overview_markdown(exp, overview, datetime.now().strftime("%Y-%m-%d %H:%M")),
    )
    console.print(f"\n[dim]Resumo guardado em {out}[/]", highlight=False)


@app.command()
def ask(
    folder: Annotated[Path, typer.Argument(exists=True, file_okay=False, help="Pasta do projeto.")],
    question: Annotated[str, typer.Argument(help="Pergunta, ex.: \"Onde é feita a autenticação?\"")],
    no_llm: Annotated[
        bool, typer.Option("--no-llm", help="Não usa o Ollama: mostra só as evidências.")
    ] = False,
    model: Annotated[
        str | None, typer.Option("--model", help="Modelo do Ollama (por omissão o da configuração).")
    ] = None,
    brief: Annotated[
        bool, typer.Option("--brief", help="Evidências numa linha cada, sem os excertos de código.")
    ] = False,
) -> None:
    """Pergunta livre: procura evidências primeiro; a IA (opcional) só responde com elas."""
    config = load_config()
    result = run_scan(folder, config, use_cache=True)
    if result.profile is None:
        render_kind(console, result.kind)
        console.print("\n[dim]Não é um projeto. Use «las scan --force» primeiro.[/]")
        raise typer.Exit(code=2)

    client, note = _llm_client(config, no_llm, model)
    project = Project(result.kind.path, config)
    with console.status("A procurar evidências…" + (" e a redigir…" if client else "")):
        answer = ask_project(project, result.profile, question, client)
    render_ask(console, answer, note, brief=brief)
    if not answer.found:
        raise typer.Exit(code=1)


def _llm_client(config, no_llm: bool, model: str | None) -> tuple[OllamaClient | None, str | None]:
    if no_llm:
        return None, "desligada com --no-llm"
    client = OllamaClient(config.ollama_url, model or config.ollama_model, config.ollama_timeout)
    if not client.available():
        return None, f"Ollama ou modelo {client.model} não disponível em {config.ollama_url}"
    return client, None


@app.command()
def config(
    init: Annotated[
        bool, typer.Option("--init", help="Cria ~/.localalibi/config.toml com os valores por omissão.")
    ] = False,
) -> None:
    """Mostra a configuração em uso (e onde está o ficheiro)."""
    path = config_path()
    if init:
        if path.exists():
            console.print(f"Já existe: {path}", highlight=False)
            raise typer.Exit(code=1)
        cfg = load_config()
        written = ProjectFS(Path.home(), cfg).write_text(path, CONFIG_TEMPLATE)
        console.print(f"Criado: {written}", highlight=False)
        return
    cfg = load_config()
    console.print(f"Ficheiro: {path} {'(existe)' if path.exists() else '(não existe — use --init)'}", highlight=False)
    extra = sorted(cfg.excluded_dirs - FIXED_EXCLUDED_DIRS)
    rows = [
        ("Pastas ignoradas (extra)", ", ".join(extra) or "—"),
        ("Tamanho máximo lido", _human_size(cfg.max_file_size)),
        ("Profundidade do painel", str(cfg.root_max_depth)),
        ("Ollama", f"{cfg.ollama_url} · {cfg.ollama_model}"),
    ]
    for label, value in rows:
        console.print(f"  {label}: [bold]{escape(value)}[/]", highlight=False)


def _human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def main() -> None:
    # Consolas do Windows em cp1252 não imprimem ✓ ≈ ⚠ ✗: força UTF-8 na saída.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure") and (stream.encoding or "").lower().replace("-", "") != "utf8":
            stream.reconfigure(encoding="utf-8", errors="replace")
    app()


if __name__ == "__main__":
    main()
