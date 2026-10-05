"""Relatório HTML estático e autónomo do painel (sem servidor nem rede)."""

from __future__ import annotations

import html
import json
from datetime import datetime

from . import __version__
from .dashboard import Dashboard, Row
from .detectors.project_kind import verdict_label
from .i18n import claim_label, claim_note, current, evidence_snippet, item_reason, t
from .models import Claim
from .render import format_value, sections

HEAD_KEYS = (
    "board.col.project", "board.col.type", "html.col.stack", "html.col.db", "html.col.services",
    "html.col.last_change", "board.col.changes", "board.col.alerts",
)

STATUS_CLASS = {"confirmed": "ok", "inferred": "weak", "contradiction": "bad", "unknown": "unk"}

CSS = """
:root{--bg:#f7f7f5;--card:#fff;--fg:#1d1d1f;--muted:#6b6b70;--line:#e3e3e0;--accent:#2457c5;
--ok:#1f7a3a;--weak:#a86b00;--bad:#c62828;--unk:#8a8a8f;--code:#f1f1ee;}
@media (prefers-color-scheme:dark){:root{--bg:#141416;--card:#1d1d20;--fg:#ececee;--muted:#9a9aa1;
--line:#2e2e33;--accent:#7aa2ff;--ok:#5cc27a;--weak:#e0a83a;--bad:#ff6b6b;--unk:#8a8a90;--code:#26262a;}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
main{max-width:1200px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:22px;margin:0 0 4px;display:flex;align-items:center;gap:10px}
.logo{width:32px;height:32px}.logo.dark{display:none}
@media (prefers-color-scheme:dark){.logo.light{display:none}.logo.dark{display:inline}}
.sub{color:var(--muted);margin:0 0 20px;word-break:break-all}
.controls{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px}
.controls input,.controls select{font:inherit;padding:6px 10px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--fg)}
.controls input{flex:1;min-width:180px}
.head,.project>summary{display:grid;grid-template-columns:2fr 1.5fr 1.5fr 1.2fr 1.3fr 1fr .8fr .8fr;gap:12px;align-items:start}
.head{padding:0 16px 6px;color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.04em}
.project{background:var(--card);border:1px solid var(--line);border-radius:10px;margin-bottom:8px}
.project>summary{list-style:none;cursor:pointer;padding:12px 16px}
.project>summary::-webkit-details-marker{display:none}
.project[open]>summary{border-bottom:1px solid var(--line)}
.name{font-weight:600;word-break:break-word}
.name small{display:block;font-weight:400;color:var(--muted)}
.chips span{display:inline-block;margin:0 4px 4px 0;padding:1px 8px;border-radius:999px;background:var(--code);font-size:12px}
.alerts .bad{color:var(--bad);font-weight:600}.alerts .unk{color:var(--unk)}
.body{padding:8px 16px 16px}
.body h3{font-size:13px;margin:16px 0 6px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
.claim{padding:4px 0}
.sym{display:inline-block;width:1.4em;font-weight:700}
.ok .sym{color:var(--ok)}.weak .sym{color:var(--weak)}.bad .sym{color:var(--bad)}.unk .sym{color:var(--unk)}
.note{color:var(--muted);font-style:italic;margin-left:1.4em}
.ev{margin:2px 0 0 1.4em;font:12px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--muted);word-break:break-all}
.ev b{color:var(--accent);font-weight:500}
.banner{margin:8px 0;padding:6px 10px;border-radius:8px;background:var(--code);color:var(--weak)}
.empty{color:var(--muted);padding:24px;text-align:center}
.legend{color:var(--muted);font-size:12px;margin-top:24px}
@media (max-width:820px){.head{display:none}.project>summary{grid-template-columns:1fr 1fr}.project>summary .name{grid-column:1/-1}}
"""

JS = """
const q=document.getElementById('q'),lang=document.getElementById('lang'),sort=document.getElementById('sort');
const list=document.getElementById('list'),items=[...list.querySelectorAll('.project')];
function apply(){const t=q.value.toLowerCase(),l=lang.value;let shown=0;
 for(const el of items){const ok=(!t||el.dataset.search.includes(t))&&(!l||el.dataset.langs.split('|').includes(l));
  el.hidden=!ok;if(ok)shown++;}
 document.getElementById('none').hidden=shown>0;}
function order(){const k=sort.value;items.sort((a,b)=>k==='name'?a.dataset.name.localeCompare(b.dataset.name)
 :(b.dataset.time||'').localeCompare(a.dataset.time||''));items.forEach(el=>list.appendChild(el));}
q.addEventListener('input',apply);lang.addEventListener('change',apply);sort.addEventListener('change',()=>{order();apply();});
"""


def _icon_data_uri(name: str) -> str:
    """Ícone embutido em base64: o relatório continua autónomo (sem rede)."""
    import base64
    from importlib.resources import files

    data = files("localalibiscan.assets").joinpath(name).read_bytes()
    return "data:image/png;base64," + base64.b64encode(data).decode()


def display_path(path: object) -> str:
    """Caminho para mostrar: a pasta pessoal aparece como "~" (relatórios partilháveis)."""
    from pathlib import Path

    p = Path(str(path))
    try:
        return "~/" + p.relative_to(Path.home()).as_posix()
    except ValueError:
        return p.as_posix()


def _e(value: object) -> str:
    return html.escape(str(value), quote=True)


def _chips(values: list[str]) -> str:
    return "".join(f"<span>{_e(v)}</span>" for v in values) or "<span>—</span>"


def _claim_html(claim: Claim) -> str:
    cls = STATUS_CLASS[claim.status]
    if claim.id == "files.important" and isinstance(claim.value, list):
        value = "<br>".join(f"{i}. {_e(it['path'])} — {_e(item_reason(it))}" for i, it in enumerate(claim.value, 1))
        return f'<div class="claim {cls}"><span class="sym">{claim.symbol}</span>{_e(claim_label(claim))}:<div class="ev">{value}</div></div>'
    parts = [f'<div class="claim {cls}"><span class="sym">{claim.symbol}</span>{_e(claim_label(claim))}: <b>{_e(format_value(claim))}</b>']
    note = claim_note(claim)
    if note:
        parts.append(f'<div class="note">{_e(note)}</div>')
    for ev in claim.evidence:
        text = evidence_snippet(ev)
        snippet = f" {_e(text)}" if text else ""
        parts.append(f'<div class="ev"><b>{_e(ev.location())}</b>{snippet}</div>')
    parts.append("</div>")
    return "".join(parts)


def _project_html(row: Row) -> str:
    probable = row.verdict == "probable_project"
    name = ("≈ " if probable else "") + row.name
    last = row.last_change.strftime("%Y-%m-%d") if row.last_change else "?"
    source = row.profile.last_change_source if row.profile else None
    if source == "files":
        source = t("explain.source.files")
    alerts = row.alerts
    alert_html = (
        (f'<span class="bad">⚠ {alerts["contradiction"]}</span> ' if alerts["contradiction"] else "")
        + (f'<span class="unk">? {alerts["unknown"]}</span>' if alerts["unknown"] else "")
    ) or "—"
    search = " ".join([row.name, row.project_type, *row.stack, *row.databases, *row.services]).lower()

    body = []
    if row.error:
        body.append(f'<div class="banner">{_e(t("html.error", error=row.error))}</div>')
    elif row.profile:
        if probable:
            body.append(f'<div class="banner">{_e(t("html.probable"))}</div>')
        by_cat: dict[str, list[Claim]] = {}
        for claim in row.profile.claims:
            by_cat.setdefault(claim.category, []).append(claim)
        for cat, title in sections(by_cat):
            if by_cat.get(cat):
                body.append(f"<h3>{_e(title)}</h3>" + "".join(_claim_html(c) for c in by_cat[cat]))
        body.append(f'<div class="legend">{_e(t("html.scanned_at", when=row.profile.scanned_at.isoformat(), path=display_path(row.path)))}</div>')

    return f"""<details class="project" data-name="{_e(row.name.lower())}" data-time="{_e(row.last_change.isoformat() if row.last_change else '')}" data-langs="{_e('|'.join(row.languages))}" data-search="{_e(search)}">
<summary><div class="name">{_e(name)}<small>{_e(verdict_label(row.verdict))}</small></div>
<div>{_e(row.project_type)}</div><div class="chips">{_chips(row.stack)}</div><div class="chips">{_chips(row.databases)}</div>
<div class="chips">{_chips(row.services)}</div><div>{_e(last)}{f' <small>({_e(source)})</small>' if source else ''}</div><div>{_e(row.changes)}</div><div class="alerts">{alert_html}</div></summary>
<div class="body">{''.join(body)}</div></details>"""


def render_html(dashboard: Dashboard, generated_at: datetime | None = None) -> str:
    generated_at = generated_at or datetime.now()
    langs = sorted({lang for row in dashboard.rows for lang in row.languages})
    options = "".join(f'<option value="{_e(l)}">{_e(l)}</option>' for l in langs)
    projects = "\n".join(_project_html(r) for r in dashboard.rows)
    icon, icon_dark = _icon_data_uri("icon-64.png"), _icon_data_uri("icon-dark-64.png")
    meta = json.dumps({"root": display_path(dashboard.root), "projects": len(dashboard.rows), "version": __version__})
    return f"""<!doctype html>
<html lang="{_e(current())}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_e(t("html.title"))}</title>
<link rel="icon" type="image/png" href="{icon}" media="(prefers-color-scheme: light)">
<link rel="icon" type="image/png" href="{icon_dark}" media="(prefers-color-scheme: dark)">
<style>{CSS}</style>
</head>
<body>
<main>
<h1><img class="logo light" src="{icon}" alt=""><img class="logo dark" src="{icon_dark}" alt="">LocalAlibiScan</h1>
<p class="sub">{_e(t("html.sub", n=len(dashboard.rows), root=display_path(dashboard.root), when=generated_at.strftime('%Y-%m-%d %H:%M')))}</p>
<div class="controls">
<input id="q" type="search" placeholder="{_e(t("html.search"))}" aria-label="{_e(t("html.search.label"))}">
<select id="lang" aria-label="{_e(t("html.language"))}"><option value="">{_e(t("html.all_languages"))}</option>{options}</select>
<select id="sort" aria-label="{_e(t("html.sort"))}"><option value="time">{_e(t("html.col.last_change"))}</option><option value="name">{_e(t("html.sort.name"))}</option></select>
</div>
<div class="head">{"".join(f"<div>{_e(t(k))}</div>" for k in HEAD_KEYS)}</div>
<div id="list">
{projects}
</div>
<div id="none" class="empty" {'hidden' if dashboard.rows else ''}>{_e(t("html.none"))}</div>
<p class="legend">{_e(t("html.legend"))}</p>
</main>
<script type="application/json" id="meta">{_e(meta)}</script>
<script>{JS}</script>
</body>
</html>
"""
