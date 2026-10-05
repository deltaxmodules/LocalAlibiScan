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
from . import i18n
from .config import FIXED_EXCLUDED_DIRS, ConfigError, config_path, config_template, load_config
from .detectors.project_kind import classify
from .fs import ProjectFS
from .dashboard import build_dashboard
from .html_report import render_html
from .ask import ask as ask_project
from .drafting import Overview, generate_overview, overview_markdown
from .drafting import explain as explain_project
from .history import diff_snapshots, list_snapshots
from .i18n import t, tn
from .llm import NotLocal, OllamaClient
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

def _argv_language(argv: list[str]) -> str | None:
    """`--lang-ui X` na linha de comandos, lido antes de o Typer a analisar.

    A ajuda (`--help`) é montada quando o módulo é importado, por isso a língua
    tem de ser conhecida já aqui.
    """
    for i, arg in enumerate(argv):
        if arg == "--lang-ui" and i + 1 < len(argv):
            return argv[i + 1]
        if arg.startswith("--lang-ui="):
            return arg.split("=", 1)[1]
    return None


if _argv_language(sys.argv[1:]):
    i18n.set_language(_argv_language(sys.argv[1:]))

app = typer.Typer(
    help=t("cli.app.help"),
    no_args_is_help=True,
    add_completion=False,
)
console = Console(soft_wrap=True)


def _version(value: bool) -> None:
    if value:
        console.print(f"localalibiscan {__version__}")
        raise typer.Exit()


def _lang_ui(value: str | None) -> str | None:
    lang = i18n.normalize(value)
    if lang and lang not in i18n.LANGUAGES:
        raise typer.BadParameter(t("cli.lang_ui.bad", code=value, langs=", ".join(i18n.LANGUAGES)))
    i18n.set_language(lang)  # None: volta à escolha automática (ambiente, configuração)
    return value


@app.callback(help=t("cli.app.help"))
def root(
    version: Annotated[
        bool, typer.Option("--version", callback=_version, is_eager=True, help=t("cli.opt.version"))
    ] = False,
    lang_ui: Annotated[
        str | None,
        typer.Option("--lang-ui", callback=_lang_ui, is_eager=True, metavar="LANG", help=t("cli.opt.lang_ui")),
    ] = None,
) -> None:
    pass


@app.command(help=t("cli.files.help"))
def files(
    folder: Annotated[
        Path, typer.Argument(exists=True, file_okay=False, help=t("cli.arg.walk_folder"))
    ] = Path("."),
    max_size: Annotated[
        int | None,
        typer.Option("--max-size", help=t("cli.opt.max_size")),
    ] = None,
) -> None:
    config = load_config()
    if max_size is not None:
        config = replace(config, max_file_size=max_size)
    pfs = ProjectFS(folder, config)

    table = Table(title=str(pfs.root), title_justify="left")
    table.add_column(t("files.col.file"), overflow="fold")
    table.add_column(t("files.col.ext"))
    table.add_column(t("files.col.size"), justify="right")
    table.add_column(t("files.col.note"), style="yellow")

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
            t(f"files.skip.{entry.skipped}") if entry.skipped else "",
        )

    console.print(table)
    console.print(
        tn("files.total", total, size=_human_size(total_bytes))
        + (t("files.skipped", n=skipped) if skipped else "")
    )


FolderArg = Annotated[
    Path, typer.Argument(exists=True, file_okay=False, help=t("cli.arg.folder"))
]


ForceOpt = Annotated[bool, typer.Option("--force", help=t("cli.opt.force"))]
NoLlmOpt = Annotated[bool, typer.Option("--no-llm", help=t("cli.opt.no_llm"))]
ModelOpt = Annotated[str | None, typer.Option("--model", help=t("cli.opt.model"))]


def _not_analysed(kind, key: str = "cli.not_analysed") -> None:
    render_kind(console, kind)
    console.print(f"\n[dim]{escape(t(key))}[/]")
    raise typer.Exit(code=2)


@app.command(help=t("cli.check.help"))
def check(folder: FolderArg = Path(".")) -> None:
    render_kind(console, classify(folder, load_config()))


@app.command(help=t("cli.scan.help"))
def scan(
    folder: FolderArg = Path("."),
    force: ForceOpt = False,
    evidence: Annotated[
        bool, typer.Option("--evidence", help=t("cli.opt.evidence"))
    ] = False,
    only: Annotated[
        str | None,
        typer.Option("--only", help=t("cli.opt.only")),
    ] = None,
) -> None:
    result = run_scan(folder, load_config(), force=force)
    if result.profile is None:
        _not_analysed(result.kind)
    render_profile(console, result.profile, all_evidence=evidence, only=section_keys(only))
    if result.output:
        console.print(f"[dim]{escape(t('cli.scan.saved', path=result.output))}[/]", highlight=False)


@app.command(help=t("cli.dashboard.help"))
def dashboard(
    folder: FolderArg = Path("."),
    html: Annotated[
        bool, typer.Option("--html", help=t("cli.opt.html"))
    ] = False,
    lang: Annotated[
        str | None, typer.Option("--lang", help=t("cli.opt.lang"))
    ] = None,
    depth: Annotated[
        int | None, typer.Option("--depth", help=t("cli.opt.depth"))
    ] = None,
    no_cache: Annotated[
        bool, typer.Option("--no-cache", help=t("cli.opt.no_cache"))
    ] = False,
) -> None:
    config = load_config()
    kind = classify(folder, config)
    if kind.analyzable:
        # A própria pasta é um projeto: mostra o perfil dele.
        result = run_scan(folder, config, use_cache=not no_cache)
        assert result.profile is not None
        render_profile(console, result.profile)
        console.print(
            f"\n[dim]{t('cli.dashboard.is_project')} "
            f"[bold]las scan {escape(shlex.quote(str(kind.path)))}[/][/]",
            highlight=False,
        )
        return

    with console.status(t("cli.dashboard.searching")) as status:
        board = build_dashboard(
            folder,
            config,
            depth=depth,
            language=lang,
            use_cache=not no_cache,
            on_project=lambda p: status.update(escape(t("cli.dashboard.analysing", name=p.name))),
        )
    if not board.rows:
        _not_analysed(kind, "cli.dashboard.none")

    render_dashboard(console, board)
    if html:
        out = ProjectFS(board.root, config).write_text(
            config.user_config_dir / "dashboard.html", render_html(board)
        )
        console.print(f"{t('cli.dashboard.html')} [bold]{escape(str(out))}[/]", highlight=False)


@app.command(help=t("cli.refresh.help"))
def refresh(folder: FolderArg = Path("."), force: ForceOpt = False) -> None:
    result = run_scan(folder, load_config(), force=force)
    if result.profile is None:
        _not_analysed(result.kind)
    console.print(f"[bold]{escape(result.profile.root)}[/]", highlight=False)
    if result.first_scan or result.diff is None:
        console.print(f"[dim]{t('cli.refresh.first')}[/]")
        return
    render_diff(console, result.diff)


@app.command(help=t("cli.history.help"))
def history(folder: FolderArg = Path(".")) -> None:
    snaps = list_snapshots(folder)
    if not snaps:
        console.print(f"[dim]{t('cli.history.none')}[/]")
        raise typer.Exit(code=2)
    table = Table(title=str(Path(folder).resolve()), title_justify="left")
    table.add_column("#", justify="right")
    table.add_column(t("history.col.date"))
    table.add_column("HEAD")
    table.add_column(t("history.col.files"), justify="right")
    table.add_column(t("history.col.changes"))
    prev = None
    for snap in snaps:
        summary = t("history.first") if prev is None else diff_snapshots(prev, snap).summary()
        table.add_row(
            str(snap.id),
            snap.scanned_at.astimezone().strftime("%Y-%m-%d %H:%M"),
            (snap.git_head or "—")[:8],
            str(len(snap.files)),
            summary,
        )
        prev = snap
    console.print(table)


@app.command(help=t("cli.explain.help"))
def explain(folder: FolderArg = Path("."), no_llm: NoLlmOpt = False, model: ModelOpt = None) -> None:
    config = load_config()
    result = run_scan(folder, config, use_cache=True)
    if result.profile is None:
        _not_analysed(result.kind, "cli.explain.not_project")

    client, llm_off_reason = _llm_client(config, no_llm, model)

    pfs = ProjectFS(result.kind.path, config)

    def read(rel: str) -> str | None:
        try:
            return pfs.read_text(rel)
        except OSError:
            return None

    with console.status(t("cli.explain.drafting") if client else t("cli.explain.preparing")):
        exp = explain_project(result.profile, client, root=pfs.root, read=read)
        overview = generate_overview(result.profile, client) if client else Overview(None, None, llm_off_reason)
    if llm_off_reason and not exp.llm_error:
        exp.llm_error = llm_off_reason
    render_explanation(console, exp)

    out = pfs.write_text(
        pfs.output_dir / "overview.md",
        overview_markdown(exp, overview, datetime.now().strftime("%Y-%m-%d %H:%M")),
    )
    console.print(f"\n[dim]{escape(t('cli.explain.saved', path=out))}[/]", highlight=False)


@app.command(help=t("cli.ask.help"))
def ask(
    folder: Annotated[Path, typer.Argument(exists=True, file_okay=False, help=t("cli.arg.project_folder"))],
    question: Annotated[str, typer.Argument(help=t("cli.arg.question"))],
    no_llm: NoLlmOpt = False,
    model: ModelOpt = None,
    brief: Annotated[
        bool, typer.Option("--brief", help=t("cli.opt.brief"))
    ] = False,
) -> None:
    config = load_config()
    result = run_scan(folder, config, use_cache=True)
    if result.profile is None:
        _not_analysed(result.kind, "cli.ask.not_project")

    client, note = _llm_client(config, no_llm, model)
    project = Project(result.kind.path, config)
    with console.status(t("cli.ask.searching_drafting") if client else t("cli.ask.searching")):
        answer = ask_project(project, result.profile, question, client)
    render_ask(console, answer, note, brief=brief)
    if not answer.found:
        raise typer.Exit(code=1)


def _llm_client(config, no_llm: bool, model: str | None) -> tuple[OllamaClient | None, str | None]:
    if no_llm:
        return None, t("llm.off_flag")
    client = OllamaClient(config.ollama_url, model or config.ollama_model, config.ollama_timeout)
    if not client.available():
        return None, t("llm.unavailable", model=client.model, url=config.ollama_url)
    return client, None


@app.command(help=t("cli.config.help"))
def config(
    init: Annotated[
        bool, typer.Option("--init", help=t("cli.opt.init"))
    ] = False,
) -> None:
    path = config_path()
    if init:
        if path.exists():
            console.print(t("cli.config.exists", path=path), highlight=False)
            raise typer.Exit(code=1)
        cfg = load_config()
        written = ProjectFS(Path.home(), cfg).write_text(path, config_template())
        console.print(t("cli.config.created", path=written), highlight=False)
        return
    cfg = load_config()
    state = t("cli.config.file.exists") if path.exists() else t("cli.config.file.missing")
    console.print(t("cli.config.file", path=path, state=state), highlight=False)
    extra = sorted(cfg.excluded_dirs - FIXED_EXCLUDED_DIRS)
    rows = [
        (t("cli.config.ui_language"), i18n.current()),
        (t("cli.config.ignored"), ", ".join(extra) or "—"),
        (t("cli.config.max_size"), _human_size(cfg.max_file_size)),
        (t("cli.config.depth"), str(cfg.root_max_depth)),
        ("Ollama", f"{cfg.ollama_url} · {cfg.ollama_model}"),
    ]
    for label, value in rows:
        console.print(f"  {label}: [bold]{escape(value)}[/]", highlight=False)


# Fase 10: regras fixadas na linha de comandos do Streamlit, que ganha a qualquer
# ficheiro de configuração (ex.: um `.streamlit/config.toml` alheio).
UI_FLAGS: tuple[tuple[str, str], ...] = (
    ("server.address", "127.0.0.1"),  # só esta máquina
    ("browser.serverAddress", "127.0.0.1"),
    ("browser.gatherUsageStats", "false"),  # regra "sem rede"
    ("server.headless", "true"),  # sem pedido de email; o browser abre-o a CLI
    ("server.fileWatcherType", "none"),
    ("server.runOnSave", "false"),
    ("client.toolbarMode", "minimal"),
    ("global.developmentMode", "false"),
)


def ui_command(folder: Path, port: int) -> list[str]:
    """`python -m streamlit run ui.py …`: a interface corre noutro processo."""
    script = Path(__file__).with_name("ui.py")
    flags = [f"--{name}={value}" for name, value in (*UI_FLAGS, ("server.port", str(port)))]
    return [sys.executable, "-m", "streamlit", "run", str(script), *flags, "--", str(folder)]


@app.command(help=t("cli.ui.help"))
def ui(
    folder: FolderArg = Path("."),
    port: Annotated[int, typer.Option("--port", help=t("cli.opt.port"))] = 8501,
    no_browser: Annotated[bool, typer.Option("--no-browser", help=t("cli.opt.no_browser"))] = False,
) -> None:
    import importlib.util
    import os
    import subprocess
    import threading
    import webbrowser

    if importlib.util.find_spec("streamlit") is None:
        console.print(t("cli.ui.missing"), highlight=False)
        console.print("  [bold]pipx install 'localalibiscan\\[ui]' --force[/]", highlight=False)
        console.print("  [dim]pip install 'localalibiscan\\[ui]'[/]", highlight=False)
        raise typer.Exit(code=2)

    config = load_config()
    # A pasta de trabalho é a nossa: o Streamlit não lê o `.streamlit/` do projeto analisado.
    workdir = Path(config.user_config_dir).expanduser()
    workdir.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false", "LOCALALIBI_LANG": i18n.current()}
    url = f"http://127.0.0.1:{port}"
    console.print(t("cli.ui.starting", url=url), highlight=False)
    if not no_browser:
        threading.Timer(1.5, webbrowser.open, (url,)).start()
    try:
        subprocess.run(ui_command(Path(folder).resolve(), port), cwd=workdir, env=env, check=False)
    except KeyboardInterrupt:
        pass


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
    try:
        app()
    except ConfigError as exc:
        Console(stderr=True).print(f"[red]{escape(t('cli.config.invalid', error=exc))}[/]", highlight=False)
        raise SystemExit(2) from exc
    except NotLocal as exc:
        Console(stderr=True).print(f"[red]{escape(str(exc))}[/]", highlight=False)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
