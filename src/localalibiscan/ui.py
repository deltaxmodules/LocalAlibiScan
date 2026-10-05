"""Interface gráfica local em Streamlit (Fase 10). Só apresentação.

Arrancada por `las ui`, que fixa as regras de rede (só 127.0.0.1, sem
estatísticas). Este módulo não decide factos: chama `classify`,
`build_dashboard`, `scan`, `list_snapshots`/`diff_snapshots`, `explain` e `ask`.

Texto vindo do projeto analisado nunca é interpretado como Markdown/HTML: vai
em blocos de código, tabelas ou Markdown escapado (`md`). Uma imagem em
Markdown faria um pedido de rede.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import streamlit as st

from localalibiscan import __version__, i18n
from localalibiscan.ask import ask as ask_project
from localalibiscan.config import Config, load_config
from localalibiscan.dashboard import Dashboard, Row, build_dashboard
from localalibiscan.detectors.project_kind import VERDICT_SYMBOL, KindResult, classify, verdict_label
from localalibiscan.drafting import Explanation
from localalibiscan.drafting import explain as explain_project
from localalibiscan.history import Diff, diff_snapshots, list_snapshots
from localalibiscan.html_report import display_path
from localalibiscan.i18n import claim_label, claim_note, evidence_snippet, item_reason, t, tn
from localalibiscan.llm import OllamaClient
from localalibiscan.models import STATUS_SYMBOL, Claim, Evidence, ProjectProfile
from localalibiscan.project import Project
from localalibiscan.render import COMPACT_CATEGORIES, format_value, sections
from localalibiscan.scan import ScanResult, scan

STATUSES = ("confirmed", "inferred", "contradiction", "unknown")
STATUS_COLOR = {"confirmed": "green", "inferred": "orange", "contradiction": "red", "unknown": "gray"}
EXCERPT_CONTEXT = 3  # linhas antes/depois da linha citada
MAX_EXCERPTS_PER_CLAIM = 5

# Pontuação com significado em Markdown (e `$` para LaTeX, `:` para cores e emojis do Streamlit).
_MD_SPECIAL = re.compile(r"([\\`*_{}\[\]()#+\-.!|<>~:$&])")


def md(value: object) -> str:
    """Texto literal dentro de Markdown: tudo o que tem significado é escapado."""
    text = str(value).replace("\r", " ").replace("\n", " ")
    return _MD_SPECIAL.sub(r"\\\1", text)


def excerpt(project: Project, ev: Evidence, context: int = EXCERPT_CONTEXT) -> str | None:
    """Linhas à volta da evidência, numeradas, com `→` na linha citada."""
    if not ev.line:
        return None
    lines = project.lines(ev.file)
    if not 0 < ev.line <= len(lines):
        return None
    start, end = max(1, ev.line - context), min(len(lines), ev.line + context)
    return "\n".join(
        f"{'→' if n == ev.line else ' '}{n:>5} │ {lines[n - 1].rstrip()[:200]}" for n in range(start, end + 1)
    )


def dashboard_table(board: Dashboard) -> list[dict[str, Any]]:
    """Linhas do painel como dicionários (texto simples, para `st.dataframe`)."""
    out = []
    for row in board.rows:
        name = ("≈ " if row.verdict == "probable_project" else "") + row.name
        if row.error:
            out.append({t("board.col.project"): name, t("board.col.type"): t("board.error"), t("gui.col.error"): row.error})
            continue
        alerts = row.alerts
        out.append(
            {
                t("board.col.project"): name,
                t("board.col.type"): row.project_type,
                t("board.col.stack"): ", ".join(row.stack) or "—",
                t("board.col.db"): ", ".join(row.databases) or "—",
                t("board.col.services"): ", ".join(row.services) or "—",
                t("board.col.changed_at"): row.last_change.astimezone().strftime("%Y-%m-%d") if row.last_change else "?",
                t("board.col.changes"): row.changes,
                "⚠": alerts["contradiction"],
                "?": alerts["unknown"],
            }
        )
    return out


def filter_rows(rows: list[Row], text: str = "", language: str | None = None) -> list[Row]:
    text = text.strip().lower()
    out = []
    for row in rows:
        haystack = " ".join([row.name, *row.stack, *row.databases, *row.services, *row.languages]).lower()
        if text and text not in haystack:
            continue
        if language and language.lower() not in (lang.lower() for lang in row.languages):
            continue
        out.append(row)
    return out


def status_counts(profile: ProjectProfile) -> dict[str, int]:
    counts = dict.fromkeys(STATUSES, 0)
    for claim in profile.claims:
        counts[claim.status] += 1
    return counts


def symbol_md(status: str) -> str:
    return f":{STATUS_COLOR[status]}[{md(STATUS_SYMBOL[status])}]"


# ---------------------------------------------------------------------- Streamlit


def _initial_folder(argv: list[str]) -> str:
    # A pasta pessoal aparece como "~" (capturas e ecrãs partilhados).
    return display_path(Path(argv[0]).expanduser().resolve() if argv else Path.cwd())


def main() -> None:
    st.set_page_config(page_title="LocalAlibiScan", page_icon=str(_asset("icon-64.png")), layout="wide")

    if "folder" not in st.session_state:
        st.session_state.folder = _initial_folder(sys.argv[1:])
    if "nonce" not in st.session_state:
        st.session_state.nonce = 0

    with st.sidebar:
        st.image(str(_asset("icon-64.png")), width=48)
        st.markdown(f"**LocalAlibiScan** {md(__version__)}")
        current = i18n.current() if i18n.current() in i18n.LANGUAGES else i18n.DEFAULT_LANG
        lang = st.selectbox(
            t("gui.language"), i18n.LANGUAGES, index=i18n.LANGUAGES.index(current), key="lang",
            format_func=lambda code: t("gui.language.name", lang=code),
        )
        i18n.set_language(lang)
        st.text_input(t("gui.folder"), key="folder", help=t("gui.folder.help"))
        use_llm = st.toggle(t("gui.use_llm"), value=True, help=t("gui.use_llm.help"), key="use_llm")
        if st.button(t("gui.refresh"), help=t("gui.refresh.help"), width="stretch"):
            st.session_state.nonce += 1
            st.cache_resource.clear()
        st.caption(t("gui.legend"))

    folder = Path(st.session_state.folder).expanduser()
    if not folder.is_dir():
        st.error(t("gui.folder.invalid", path=folder))
        return

    config = load_config()
    kind = classify(folder, config)
    if kind.analyzable:
        _project_view(config, kind.path, nonce=st.session_state.nonce, use_llm=use_llm)
        return

    with st.spinner(t("cli.dashboard.searching")):
        board = _cached_board(str(folder.resolve()), st.session_state.nonce, i18n.current())
    if not board.rows:
        _kind_view(kind)
        return
    selected = _dashboard_view(board)
    if selected is not None:
        st.divider()
        _project_view(config, selected.path, nonce=st.session_state.nonce, use_llm=use_llm, row=selected)


def _asset(name: str) -> Path:
    from importlib.resources import files

    return Path(str(files("localalibiscan.assets").joinpath(name)))


# Cada interação volta a correr o script: a cache do Streamlit evita voltar a
# percorrer as pastas. `nonce` muda com o botão "Atualizar"; a impressão digital
# de `scan` decide então se é preciso reanalisar. A língua entra na chave porque
# o painel guarda textos já traduzidos (ex.: "novo").
@st.cache_resource(show_spinner=False)
def _cached_board(root: str, nonce: int, lang: str) -> Dashboard:
    return build_dashboard(root, load_config(), use_cache=True)


@st.cache_resource(show_spinner=False)
def _cached_scan(root: str, nonce: int, lang: str) -> ScanResult:
    return scan(root, load_config(), use_cache=True)


@st.cache_resource(show_spinner=False)
def _cached_project(root: str, nonce: int) -> Project:
    return Project(root, load_config())


def _kind_view(kind: KindResult) -> None:
    st.subheader(f"{VERDICT_SYMBOL[kind.verdict]} {md(verdict_label(kind.verdict))}")
    st.caption(md(display_path(kind.path)))
    note = claim_note(kind.claim)
    if note:
        st.markdown(f"*{md(note)}*")
    for ev in kind.claim.evidence:
        st.code(f"{ev.location()}  {evidence_snippet(ev)}".rstrip(), language=None)
    if kind.verdict == "subfolder" and kind.project_root:
        if st.button(t("gui.open_root", path=kind.project_root)):
            st.session_state.folder = str(kind.project_root)
            st.rerun()
    else:
        st.info(t("gui.no_projects"))


def _dashboard_view(board: Dashboard) -> Row | None:
    st.title(t("gui.dashboard.title"))
    st.caption(md(display_path(board.root)))
    languages = sorted({lang for row in board.rows for lang in row.languages}, key=str.lower)
    c1, c2 = st.columns([3, 1])
    text = c1.text_input(t("gui.filter"), key="filter", placeholder=t("gui.filter.placeholder"))
    language = c2.selectbox(t("gui.filter.language"), [None, *languages], key="filter_lang", format_func=lambda v: v or t("gui.all"))
    rows = filter_rows(board.rows, text, language)
    st.dataframe(dashboard_table(Dashboard(board.root, rows)), hide_index=True, width="stretch")
    st.caption(t("board.footer", n=len(board.rows), cached=board.cached_count, secs=f"{board.elapsed:.2f}"))
    analysable = [r for r in rows if r.profile is not None]
    if not analysable:
        return None
    names = [r.name for r in analysable]
    choice = st.selectbox(t("gui.pick_project"), [None, *names], key="project", format_func=lambda v: v or "—")
    return next((r for r in analysable if r.name == choice), None)


def _project_view(config: Config, root: Path, *, nonce: int, use_llm: bool, row: Row | None = None) -> None:
    if row is not None and row.profile is not None:
        profile = row.profile
    else:
        result = _cached_scan(str(root), nonce, i18n.current())
        if result.profile is None:
            _kind_view(result.kind)
            return
        profile = result.profile
    project = _cached_project(profile.root, nonce)

    st.header(md(Path(profile.root).name))
    st.caption(md(display_path(profile.root)))
    if profile.verdict == "probable_project":
        st.warning(f"{t('profile.probable.title')} {t('profile.probable.text')}")

    counts = status_counts(profile)
    for col, status in zip(st.columns(len(STATUSES)), STATUSES):
        col.metric(f"{STATUS_SYMBOL[status]} {t(f'status.{status}')}", counts[status])

    tabs = st.tabs([t("gui.tab.profile"), t("gui.tab.history"), t("gui.tab.explain"), t("gui.tab.ask")])
    with tabs[0]:
        _profile_tab(profile, project)
    with tabs[1]:
        _history_tab(Path(profile.root))
    with tabs[2]:
        _explain_tab(config, profile, project, use_llm)
    with tabs[3]:
        _ask_tab(config, profile, project, use_llm)


def _profile_tab(profile: ProjectProfile, project: Project) -> None:
    key = f"statuses:{profile.root}"
    wanted = st.multiselect(
        t("gui.filter.status"), STATUSES, default=list(STATUSES), key=key,
        format_func=lambda s: f"{STATUS_SYMBOL[s]} {t(f'status.{s}')}",
    )
    by_cat: dict[str, list[Claim]] = {}
    for claim in profile.claims:
        if claim.status in wanted:
            by_cat.setdefault(claim.category, []).append(claim)
    for cat, title in sections(by_cat):
        claims = by_cat.get(cat)
        if not claims:
            continue
        st.subheader(md(title))
        if cat in COMPACT_CATEGORIES:
            st.dataframe(
                [
                    {
                        "": c.symbol,
                        t("gui.col.name"): claim_label(c),
                        t("gui.col.value"): format_value(c),
                        t("gui.col.evidence"): c.evidence[0].location() if c.evidence else "—",
                        "+": len(c.evidence) - 1 if c.evidence else 0,
                    }
                    for c in claims
                ],
                hide_index=True,
                width="stretch",
            )
            continue
        for claim in claims:
            _claim(claim, project)


def _claim(claim: Claim, project: Project) -> None:
    if claim.id == "files.important" and isinstance(claim.value, list):
        st.markdown(f"{symbol_md(claim.status)} **{md(claim_label(claim))}**")
        st.dataframe(
            [{"#": i, t("gui.col.file"): item["path"], t("gui.col.why"): item_reason(item)} for i, item in enumerate(claim.value, 1)],
            hide_index=True,
            width="stretch",
        )
        return
    st.markdown(f"{symbol_md(claim.status)} **{md(claim_label(claim))}**: {md(format_value(claim))}")
    note = claim_note(claim)
    if note:
        st.caption(md(note))
    if not claim.evidence:
        return
    with st.expander(tn("gui.evidence", len(claim.evidence), first=md(claim.evidence[0].location()))):
        for ev in claim.evidence[:MAX_EXCERPTS_PER_CLAIM]:
            st.caption(md(ev.location()))
            code = excerpt(project, ev)
            st.code(code if code is not None else evidence_snippet(ev) or ev.location(), language=None)
        rest = claim.evidence[MAX_EXCERPTS_PER_CLAIM:]
        if rest:
            st.code("\n".join(f"{ev.location()}  {evidence_snippet(ev)}".rstrip() for ev in rest), language=None)


def _history_tab(root: Path) -> None:
    snaps = list_snapshots(root)
    if not snaps:
        st.info(t("cli.history.none"))
        return
    table, prev = [], None
    for snap in snaps:
        table.append(
            {
                "#": snap.id,
                t("history.col.date"): snap.scanned_at.astimezone().strftime("%Y-%m-%d %H:%M"),
                "HEAD": (snap.git_head or "—")[:8],
                t("history.col.files"): len(snap.files),
                t("history.col.changes"): t("history.first") if prev is None else diff_snapshots(prev, snap).summary(),
            }
        )
        prev = snap
    st.dataframe(list(reversed(table)), hide_index=True, width="stretch")
    if len(snaps) < 2:
        return
    ids = [s.id for s in snaps]
    c1, c2 = st.columns(2)
    old = c1.selectbox(t("gui.history.from"), ids, index=len(ids) - 2, key=f"from:{root}")
    new = c2.selectbox(t("gui.history.to"), ids, index=len(ids) - 1, key=f"to:{root}")
    by_id = {s.id: s for s in snaps}
    _diff(diff_snapshots(by_id[old], by_id[new]))


def _diff(diff: Diff) -> None:
    if diff.empty:
        st.caption(t("diff.none"))
        return
    colors = {"+": "green", "-": "red", "~": "orange", "⚠": "red"}
    for title, items in ((t("diff.added"), diff.added), (t("diff.removed"), diff.removed),
                         (t("diff.changed"), diff.changed), (t("diff.alerts"), diff.alerts)):
        if not items:
            continue
        st.markdown(f"**{md(title)}**")
        for ch in items:
            loc = f" ← `{ch.location}`" if ch.location and "`" not in ch.location else ""
            st.markdown(f":{colors[ch.sign]}[{md(ch.sign)}] {md(ch.text)}{loc}")


def _llm(config: Config, use_llm: bool) -> tuple[OllamaClient | None, str | None]:
    if not use_llm:
        return None, t("llm.off_flag")
    client = OllamaClient(config.ollama_url, config.ollama_model, config.ollama_timeout)
    if not client.available():
        return None, t("llm.unavailable", model=client.model, url=config.ollama_url)
    return client, None


def _explain_tab(config: Config, profile: ProjectProfile, project: Project, use_llm: bool) -> None:
    key = f"explain:{profile.root}:{i18n.current()}"
    if st.button(t("gui.explain.run"), key=f"btn:{key}"):
        client, reason = _llm(config, use_llm)
        with st.spinner(t("cli.explain.drafting") if client else t("cli.explain.preparing")):
            exp = explain_project(profile, client, root=project.root, read=project.text)
        if reason and not exp.llm_error:
            exp.llm_error = reason
        st.session_state[key] = exp
    exp: Explanation | None = st.session_state.get(key)
    if exp is None:
        st.caption(t("gui.explain.hint"))
        return
    if exp.model and not exp.llm_error:
        st.caption(f"{t('explain.ai_on')} {t('explain.ai_on.detail', model=exp.model)}")
    else:
        st.caption(t("explain.ai_off", reason=exp.llm_error or t("llm.unavailable_default")))
    for answer in exp.answers:
        st.markdown(f"#### {md(answer.question.text)}")
        if answer.unknown:
            st.caption(t("explain.no_facts"))
            continue
        if answer.drafted:
            for s in answer.drafted.sentences:
                st.markdown(f":orange[≈] {md(s.text)} " + " ".join(f"`{i}`" for i in s.ids if "`" not in i))
        for line in answer.lines:
            st.markdown(f"· {md(line)}")
        for claim in answer.facts:
            if claim.id == "files.important" and isinstance(claim.value, list):
                for i, item in enumerate(claim.value, 1):
                    st.markdown(f"{i}\\. {md(item['path'])} — {md(item_reason(item))}")
                continue
            loc = f" ← {md(claim.evidence[0].location())}" if claim.evidence else ""
            st.markdown(f"{symbol_md(claim.status)} {md(claim_label(claim))}: {md(format_value(claim))}{loc}")


def _ask_tab(config: Config, profile: ProjectProfile, project: Project, use_llm: bool) -> None:
    key = f"ask:{profile.root}"
    with st.form(f"form:{key}"):
        question = st.text_input(t("gui.ask.label"), placeholder=t("gui.ask.placeholder"), key=f"q:{key}")
        submitted = st.form_submit_button(t("gui.ask.run"))
    if submitted and question.strip():
        client, note = _llm(config, use_llm)
        with st.spinner(t("cli.ask.searching_drafting") if client else t("cli.ask.searching")):
            result = ask_project(project, profile, question.strip(), client)
        st.session_state[key] = (result, note)
    if key not in st.session_state:
        return
    result, note = st.session_state[key]
    st.markdown(f"**{t('ask.question')}** {md(result.question)}")
    if not result.found:
        st.warning(f"{t('ask.not_found')} {t('ask.not_found.llm')}")
        if result.suggestions:
            st.caption(f"{t('ask.suggestions')} {md(', '.join(result.suggestions))}")
        return
    if result.answer and result.answer.sentences:
        st.markdown(f"**{md(t('ask.ai_answer'))}** {md(t('ask.ai_answer.model', model=result.model or ''))}")
        for s in result.answer.sentences:
            st.markdown(f":orange[≈] {md(s.text)} " + " ".join(f"`{i}`" for i in s.ids if "`" not in i))
        if result.answer.removed:
            st.caption(tn("validator.removed", len(result.answer.removed)))
    elif note or result.llm_error:
        st.caption(t("ask.ai_off", reason=result.llm_error or note or ""))
    else:
        st.caption(t("ask.ai_empty"))
    st.markdown(f"**{md(t('ask.evidence'))}**")
    for e in result.excerpts:
        st.caption(f"{md(e.file)}:{e.start}–{e.end} · {md('; '.join(e.reasons))}")
        st.code(
            "\n".join(f"{n:>5} │ {text.rstrip()[:200]}" for n, text in zip(range(e.start, e.end + 1), e.lines)),
            language=None,
        )


if __name__ == "__main__":
    main()
