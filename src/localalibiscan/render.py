"""Apresentação no terminal (Rich). Só formata; nunca decide factos."""

from __future__ import annotations

import shlex
from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.markup import escape

from .detectors.project_kind import VERDICT_SYMBOL, KindResult, verdict_label
from .i18n import claim_label, claim_note, claim_text_value, evidence_snippet, item_reason, t, tn
from .models import Claim, Evidence, ProjectProfile

if TYPE_CHECKING:
    from .dashboard import Dashboard
    from .ask import AskResult
    from .drafting import Explanation
    from .history import Diff

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

# Ordem das secções do perfil; títulos em locales/ (`section.<categoria>`).
SECTION_ORDER: tuple[str, ...] = (
    "project", "language", "entry_point", "structure", "database", "orm", "framework", "service",
    "route", "docs_vs_code", "important_files", "docs", "manifest", "dependency", "script",
)


def sections(categories) -> list[tuple[str, str]]:
    """(categoria, título) pela ordem fixa, seguidas das categorias desconhecidas."""
    out = [(cat, t(f"section.{cat}")) for cat in SECTION_ORDER]
    out += [(cat, cat.replace("_", " ").capitalize()) for cat in categories if cat not in SECTION_ORDER]
    return out
COMPACT_CATEGORIES = frozenset({"dependency", "script", "route"})


def format_value(claim: Claim) -> str:
    value: Any = claim_text_value(claim)
    if value is None:
        return t("value.undetermined") if claim.status == "unknown" else "—"
    if claim.category == "route" and isinstance(value, dict):
        return f"[{value.get('framework')}]" + (f" {value['handler']}()" if value.get("handler") else "")
    if claim.category == "dependency" and isinstance(value, dict):
        return f"{value.get('spec') or '*'}" + (" (dev)" if value.get("dev") else "")
    if claim.id == "project.kind":
        return verdict_label(value)
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
    snippet = evidence_snippet(ev)
    return f"{loc}  [dim]{escape(snippet)}[/]" if snippet else loc


def render_claim(console: Console, claim: Claim, *, all_evidence: bool = False) -> None:
    style = STATUS_STYLE[claim.status]
    head = f"  [{style}]{claim.symbol}[/] [bold]{escape(claim_label(claim))}[/]"
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
                f"      {i:>2}. [cyan]{escape(item['path'])}[/]  [dim]{escape(item_reason(item))}[/]",
                highlight=False,
            )
        return

    console.print(f"{head}: {value}", highlight=False)
    note = claim_note(claim)
    if note:
        console.print(f"      [italic dim]{escape(note)}[/]", highlight=False)
    shown = claim.evidence if all_evidence else claim.evidence[:1]
    for ev in shown:
        console.print(f"      └ {format_evidence(ev)}", highlight=False)
    hidden = len(claim.evidence) - len(shown)
    if hidden > 0:
        console.print(f"      [dim]  {escape(tn('profile.more_evidence', hidden))}[/]", highlight=False)


def render_kind(console: Console, kind: KindResult, *, show_evidence: bool = True) -> None:
    style = VERDICT_STYLE[kind.verdict]
    console.print(
        f"[{style}]{VERDICT_SYMBOL[kind.verdict]} {verdict_label(kind.verdict)}[/]  [dim]{escape(str(kind.path))}[/]",
        highlight=False,
    )
    note = claim_note(kind.claim)
    if note:
        console.print(f"  [italic]{escape(note)}[/]", highlight=False)
    if show_evidence and kind.verdict != "root":
        for ev in kind.claim.evidence:
            console.print(f"  └ {format_evidence(ev)}", highlight=False)

    if kind.verdict == "root":
        for sub, ev in zip(kind.subprojects, kind.claim.evidence):
            rel = sub.relative_to(kind.path).as_posix()
            console.print(f"    • [bold]{escape(rel)}[/]  [dim]({escape(ev.file)})[/]", highlight=False)
        console.print(f"\n  {t('kind.suggestion')}: [bold]las dashboard {_q(kind.path)}[/]", highlight=False)
    elif kind.verdict == "subfolder" and kind.project_root:
        console.print(f"\n  {t('kind.suggestion')}: [bold]las scan {_q(kind.project_root)}[/]", highlight=False)


SECTION_ALIASES = {
    "db": "database", "databases": "database", "frameworks": "framework", "services": "service",
    "routes": "route", "docs-vs-code": "docs_vs_code", "files": "important_files",
    "dependencies": "dependency", "scripts": "script", "languages": "language", "entry": "entry_point",
}


def section_keys(only: str | None) -> set[str] | None:
    """"database,docs_vs_code" -> categorias; None mostra tudo."""
    if not only:
        return None
    keys = {SECTION_ALIASES.get(k.strip().lower(), k.strip().lower()) for k in only.split(",") if k.strip()}
    return keys or None


def render_profile(
    console: Console, profile: ProjectProfile, *, all_evidence: bool = False, only: set[str] | None = None
) -> None:
    if profile.verdict == "probable_project":
        console.print(f"[bold yellow]{t('profile.probable.title')}[/] [yellow]{t('profile.probable.text')}[/]\n")
    elif profile.forced:
        console.print(
            f"[bold yellow]{t('profile.forced.title')}[/] "
            f"[yellow]{escape(t('profile.forced.text', verdict=verdict_label(profile.verdict)))}[/]\n"
        )
    console.print(f"[bold]{escape(profile.root)}[/]", highlight=False)

    by_cat: dict[str, list[Claim]] = {}
    for claim in profile.claims:
        by_cat.setdefault(claim.category, []).append(claim)

    for cat, title in sections(by_cat):
        claims = by_cat.get(cat)
        if not claims or (only is not None and cat not in only):
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
    table.add_column(t("board.col.project"), style="bold", overflow="fold", ratio=3)
    table.add_column(t("board.col.type"), overflow="fold", ratio=2)
    table.add_column(t("board.col.stack"), overflow="fold", ratio=2)
    table.add_column(t("board.col.db"), overflow="fold", ratio=2)
    table.add_column(t("board.col.services"), overflow="fold", ratio=2)
    table.add_column(t("board.col.changed_at"), no_wrap=True)
    table.add_column(t("board.col.changes"), no_wrap=True)
    table.add_column(t("board.col.alerts"), no_wrap=True)
    for row in board.rows:
        name = ("≈ " if row.verdict == "probable_project" else "") + row.name
        if row.error:
            table.add_row(escape(name), f"[red]{t('board.error')}[/]", escape(row.error), "", "", "", "", "")
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
            escape(row.changes),
            alert_text,
        )
    console.print(table)
    console.print(
        f"[dim]{escape(t('board.footer', n=len(board.rows), cached=board.cached_count, secs=f'{board.elapsed:.2f}'))}[/]",
        highlight=False,
    )


DIFF_STYLE = {"+": "green", "-": "red", "~": "yellow", "⚠": "bold red"}


def render_diff(console: Console, diff: Diff) -> None:
    if diff.empty:
        console.print(f"[dim]{t('diff.none')}[/]")
        return
    for title, items in (
        (t("diff.added"), diff.added),
        (t("diff.removed"), diff.removed),
        (t("diff.changed"), diff.changed),
        (t("diff.alerts"), diff.alerts),
    ):
        if not items:
            continue
        console.print(f"\n[bold underline]{title}[/]")
        for ch in items:
            loc = f"  [dim]←[/] [cyan]{escape(ch.location)}[/]" if ch.location else ""
            console.print(f"  [{DIFF_STYLE[ch.sign]}]{ch.sign}[/] {escape(ch.text)}{loc}", highlight=False)


def render_explanation(console: Console, exp: Explanation) -> None:
    console.print(f"[bold]{escape(exp.profile.root)}[/]", highlight=False)
    if exp.model and not exp.llm_error:
        console.print(f"[yellow]{t('explain.ai_on')}[/] [dim]{escape(t('explain.ai_on.detail', model=exp.model))}[/]")
    else:
        reason = exp.llm_error or t("llm.unavailable_default")
        console.print(f"[dim]{escape(t('explain.ai_off', reason=reason))}[/]")
    for a in exp.answers:
        console.print(f"\n[bold underline]{escape(a.question.text)}[/]")
        if a.unknown:
            console.print(f"  [dim]{t('explain.no_facts')}[/]")
            continue
        if a.drafted:
            for sentence in a.drafted.sentences:
                console.print(
                    f"  [yellow]≈[/] {escape(sentence.text)} [dim]\\[{escape(', '.join(sentence.ids))}][/]",
                    highlight=False,
                )
        for line in a.lines:
            console.print(f"  [dim]·[/] {escape(line)}", highlight=False)
        for claim in a.facts:
            if claim.id == "files.important" and isinstance(claim.value, list):
                for i, item in enumerate(claim.value, start=1):
                    console.print(f"  {i:>2}. [cyan]{escape(item['path'])}[/]  [dim]{escape(item_reason(item))}[/]", highlight=False)
                continue
            style = STATUS_STYLE[claim.status]
            loc = f"  [dim]←[/] [cyan]{escape(claim.evidence[0].location())}[/]" if claim.evidence else ""
            console.print(
                f"  [{style}]{claim.symbol}[/] {escape(claim_label(claim))}: {escape(format_value(claim))}{loc}",
                highlight=False,
            )


def render_ask(console: Console, result: AskResult, llm_note: str | None, *, brief: bool = False) -> None:
    console.print(f"[bold]{t('ask.question')}[/] {escape(result.question)}", highlight=False)
    if not result.found:
        console.print(f"\n[yellow]{t('ask.not_found')}[/] [dim]{t('ask.not_found.llm')}[/]")
        if result.suggestions:
            console.print(f"[dim]{t('ask.suggestions')}[/] {escape(', '.join(result.suggestions))}", highlight=False)
        return
    if result.answer and result.answer.sentences:
        console.print(f"\n[yellow]{t('ask.ai_answer')}[/] [dim]{escape(t('ask.ai_answer.model', model=result.model or ''))}[/]")
        for sentence in result.answer.sentences:
            console.print(f"  [yellow]≈[/] {escape(sentence.text)} [dim]\\[{escape(', '.join(sentence.ids))}][/]", highlight=False)
        if result.answer.removed:
            console.print(f"  [dim]{escape(tn('validator.removed', len(result.answer.removed)))}[/]")
    elif llm_note or result.llm_error:
        console.print(f"\n[dim]{escape(t('ask.ai_off', reason=result.llm_error or llm_note or ''))}[/]")
    else:
        console.print(f"\n[dim]{t('ask.ai_empty')}[/]")

    console.print(f"\n[bold underline]{t('ask.evidence')}[/]")
    for e in result.excerpts:
        console.print(f"  [cyan]{escape(e.file)}:{e.start}-{e.end}[/]  [dim]{escape('; '.join(e.reasons))}[/]", highlight=False)
        if brief:
            continue
        for n, text in zip(range(e.start, e.end + 1), e.lines):
            console.print(f"    [dim]{n:>4}[/] {escape(text.rstrip()[:150])}", highlight=False)
