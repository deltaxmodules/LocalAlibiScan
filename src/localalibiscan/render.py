"""Apresentação no terminal (Rich). Só formata; nunca decide factos."""

from __future__ import annotations

import shlex
from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.markup import escape

from .detectors.project_kind import VERDICT_LABEL, VERDICT_SYMBOL, KindResult
from .models import Claim, Evidence, ProjectProfile

if TYPE_CHECKING:
    from .dashboard import Dashboard

STATUS_STYLE = {
    "confirmed": "green",
    "inferred": "yellow",
    "contradiction": "bold red",
    "unknown": "dim",
}
VERDICT_STYLE = {
    "project": "green",
    "root": "cyan",
    "subfolder": "cyan",
    "probable_project": "yellow",
    "not_a_project": "red",
}

SECTIONS: list[tuple[str, str]] = [
    ("project", "Projeto"),
    ("language", "Linguagens"),
    ("entry_point", "Arranque"),
    ("structure", "Estrutura"),
    ("database", "Base de dados"),
    ("orm", "ORM"),
    ("framework", "Frameworks"),
    ("service", "Serviços externos"),
    ("route", "Rotas"),
    ("important_files", "Ficheiros importantes"),
    ("docs", "Documentação"),
    ("manifest", "Manifestos"),
    ("dependency", "Dependências"),
    ("script", "Scripts"),
]
COMPACT_CATEGORIES = frozenset({"dependency", "script", "route"})


def format_value(claim: Claim) -> str:
    value: Any = claim.value
    if value is None:
        return "não determinado" if claim.status == "unknown" else "—"
    if claim.category == "route" and isinstance(value, dict):
        return f"[{value.get('framework')}]" + (f" {value['handler']}()" if value.get("handler") else "")
    if claim.category == "dependency" and isinstance(value, dict):
        return f"{value.get('spec') or '*'}" + (" (dev)" if value.get("dev") else "")
    if claim.id == "project.kind":
        return VERDICT_LABEL.get(value, value)
    if isinstance(value, dict):
        return ", ".join(f"{k} {v}" for k, v in value.items())
    if isinstance(value, list):
        items = []
        for item in value:
            if isinstance(item, dict) and "path" in item:
                extra = item.get("type") or item.get("code_files")
                items.append(f"{item['path']} ({extra})" if extra is not None else item["path"])
            else:
                items.append(str(item))
        return ", ".join(items)
    return str(value)


def format_evidence(ev: Evidence) -> str:
    loc = f"[cyan]{escape(ev.location())}[/]"
    return f"{loc}  [dim]{escape(ev.snippet)}[/]" if ev.snippet else loc


def render_claim(console: Console, claim: Claim, *, all_evidence: bool = False) -> None:
    style = STATUS_STYLE[claim.status]
    head = f"  [{style}]{claim.symbol}[/] [bold]{escape(claim.label)}[/]"
    value = escape(format_value(claim))
    if claim.category in COMPACT_CATEGORIES:
        loc = f"  [dim]←[/] [cyan]{escape(claim.evidence[0].location())}[/]" if claim.evidence else ""
        more = f" [dim](+{len(claim.evidence) - 1})[/]" if len(claim.evidence) > 1 and not all_evidence else ""
        console.print(f"{head} {value}{loc}{more}", highlight=False)
        if all_evidence:
            for ev in claim.evidence[1:]:
                console.print(f"      └ {format_evidence(ev)}", highlight=False)
        return

    if claim.id == "files.important" and isinstance(claim.value, list):
        console.print(f"{head}:", highlight=False)
        for i, item in enumerate(claim.value, start=1):
            console.print(
                f"      {i:>2}. [cyan]{escape(item['path'])}[/]  [dim]{escape(item['reason'])}[/]",
                highlight=False,
            )
        return

    console.print(f"{head}: {value}", highlight=False)
    if claim.note:
        console.print(f"      [italic dim]{escape(claim.note)}[/]", highlight=False)
    shown = claim.evidence if all_evidence else claim.evidence[:1]
    for ev in shown:
        console.print(f"      └ {format_evidence(ev)}", highlight=False)
    hidden = len(claim.evidence) - len(shown)
    if hidden > 0:
        console.print(f"      [dim]  +{hidden} evidências (--evidence)[/]", highlight=False)


def render_kind(console: Console, kind: KindResult, *, show_evidence: bool = True) -> None:
    style = VERDICT_STYLE[kind.verdict]
    console.print(
        f"[{style}]{VERDICT_SYMBOL[kind.verdict]} {VERDICT_LABEL[kind.verdict]}[/]  [dim]{escape(str(kind.path))}[/]",
        highlight=False,
    )
    if kind.claim.note:
        console.print(f"  [italic]{escape(kind.claim.note)}[/]", highlight=False)
    if show_evidence and kind.verdict != "root":
        for ev in kind.claim.evidence:
            console.print(f"  └ {format_evidence(ev)}", highlight=False)

    if kind.verdict == "root":
        for sub, ev in zip(kind.subprojects, kind.claim.evidence):
            rel = sub.relative_to(kind.path).as_posix()
            console.print(f"    • [bold]{escape(rel)}[/]  [dim]({escape(ev.file)})[/]", highlight=False)
        console.print(f"\n  Sugestão: [bold]las dashboard {_q(kind.path)}[/]", highlight=False)
    elif kind.verdict == "subfolder" and kind.project_root:
        console.print(f"\n  Sugestão: [bold]las scan {_q(kind.project_root)}[/]", highlight=False)


def render_profile(console: Console, profile: ProjectProfile, *, all_evidence: bool = False) -> None:
    if profile.verdict == "probable_project":
        console.print(
            "[bold yellow]≈ Provável projeto:[/] [yellow]sem .git nem manifesto. "
            "Os resultados abaixo baseiam-se em indícios.[/]\n"
        )
    elif profile.forced:
        console.print(
            f"[bold yellow]Análise forçada:[/] [yellow]o veredito é «{VERDICT_LABEL[profile.verdict]}».[/]\n"
        )
    console.print(f"[bold]{escape(profile.root)}[/]", highlight=False)

    by_cat: dict[str, list[Claim]] = {}
    for claim in profile.claims:
        by_cat.setdefault(claim.category, []).append(claim)

    known = [cat for cat, _ in SECTIONS]
    order = SECTIONS + [(cat, cat.replace("_", " ").capitalize()) for cat in by_cat if cat not in known]
    for cat, title in order:
        claims = by_cat.get(cat)
        if not claims:
            continue
        console.print(f"\n[bold underline]{title}[/]")
        for claim in claims:
            render_claim(console, claim, all_evidence=all_evidence)

    counts: dict[str, int] = {}
    for c in profile.claims:
        counts[c.status] = counts.get(c.status, 0) + 1
    summary = "  ".join(
        f"[{STATUS_STYLE[s]}]{sym} {counts[s]}[/]"
        for s, sym in (("confirmed", "✓"), ("inferred", "≈"), ("contradiction", "⚠"), ("unknown", "?"))
        if counts.get(s)
    )
    console.print(f"\n{summary}")


def _q(path: Any) -> str:
    return escape(shlex.quote(str(path)))


def render_dashboard(console: Console, board: Dashboard) -> None:
    from rich.table import Table

    table = Table(title=str(board.root), title_justify="left", show_lines=False, expand=True)
    table.add_column("Projeto", style="bold", overflow="fold", ratio=3)
    table.add_column("Tipo", overflow="fold", ratio=2)
    table.add_column("Stack", overflow="fold", ratio=2)
    table.add_column("BD", overflow="fold", ratio=2)
    table.add_column("Serviços", overflow="fold", ratio=2)
    table.add_column("Alterado", no_wrap=True)
    table.add_column("Alertas", no_wrap=True)
    for row in board.rows:
        name = ("≈ " if row.verdict == "probable_project" else "") + row.name
        if row.error:
            table.add_row(escape(name), "[red]erro[/]", escape(row.error), "", "", "", "")
            continue
        last = row.last_change.astimezone().strftime("%Y-%m-%d") if row.last_change else "?"
        if row.profile and row.profile.last_change_source == "git":
            last += " [dim]git[/]"
        alerts = row.alerts
        alert_text = " ".join(
            t for t in (
                f"[bold red]⚠ {alerts['contradiction']}[/]" if alerts["contradiction"] else "",
                f"[dim]? {alerts['unknown']}[/]" if alerts["unknown"] else "",
            ) if t
        ) or "—"
        table.add_row(
            escape(name),
            escape(row.project_type),
            escape(", ".join(row.stack) or "—"),
            escape(", ".join(row.databases) or "—"),
            escape(", ".join(row.services) or "—"),
            last,
            alert_text,
        )
    console.print(table)
    console.print(
        f"[dim]{len(board.rows)} projetos · {board.cached_count} da cache · {board.elapsed:.2f}s · "
        "≈ provável projeto / inferido · ⚠ contradições · ? por determinar[/]",
        highlight=False,
    )
