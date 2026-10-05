"""Redação com LLM local, sempre a partir de factos (Fase 6).

- A LLM recebe só Claims (id, rótulo, valor, estado, nota) — nunca código.
- Cada frase gerada tem de citar ids existentes: `Usa SQLite [db.sqlite].`
- O validador remove frases sem citação ou com ids inventados.
- Sem Ollama, tudo continua a funcionar: só se mostram os factos.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .history import diff_snapshots, list_snapshots
from .llm import LLMUnavailable, TextModel
from .models import Claim, ProjectProfile

README_ID = "docs.readme"
AI_MARK = "≈ redigido pela IA a partir de factos"

# ---------------------------------------------------------------------- validador

CITATION = re.compile(r"\[([^\[\]]+)\]")
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
LIST_PREFIX = re.compile(r"^\s*(?:[-*+•]|\d+[.)])\s+")


@dataclass
class Sentence:
    text: str  # sem as citações
    ids: list[str]

    def render(self) -> str:
        body = self.text.rstrip()
        end = body[-1] if body and body[-1] in ".!?" else "."
        return f"{body.rstrip('.!?')} [{', '.join(self.ids)}]{end}"


@dataclass
class Validated:
    sentences: list[Sentence] = field(default_factory=list)
    removed: list[tuple[str, str]] = field(default_factory=list)  # (frase, motivo)

    @property
    def text(self) -> str:
        return " ".join(s.render() for s in self.sentences)


def _segments(text: str) -> list[str]:
    out: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or set(line) <= {"-", "*", "_", "="}:
            continue
        line = LIST_PREFIX.sub("", line)
        for part in SENTENCE_SPLIT.split(line):
            part = part.strip()
            if not part:
                continue
            # "Usa SQLite. [db.sqlite]" -> a citação pertence à frase anterior.
            if out and CITATION.sub("", part).strip(" .;,") == "":
                out[-1] = f"{out[-1]} {part}"
            else:
                out.append(part)
    return out


def validate(text: str, known_ids: set[str]) -> Validated:
    """Mantém só frases que citam pelo menos um id e em que todos os ids existem."""
    result = Validated()
    for segment in _segments(text):
        ids: list[str] = []
        for group in CITATION.findall(segment):
            ids.extend(i.strip().strip("`'\"") for i in re.split(r"[,;]", group) if i.strip())
        body = CITATION.sub("", segment).strip()
        body = re.sub(r"\s+([.!?,;:])", r"\1", body).strip()
        if not ids:
            result.removed.append((segment, "sem citação"))
            continue
        unknown = [i for i in ids if i not in known_ids]
        if unknown:
            result.removed.append((segment, f"id inexistente: {', '.join(unknown)}"))
            continue
        if not re.search(r"[^\W\d_]{3}", CITATION.sub("", body)):
            result.removed.append((segment, "sem texto"))
            continue
        result.sentences.append(Sentence(body, list(dict.fromkeys(ids))))
    return result


def structured_to_text(value: object) -> str:
    """Converte a saída JSON da LLM ([{"text", "ids"}] ou texto) em «frase [ids]» por linha.

    Tudo passa depois pelo mesmo `validate`: o formato estruturado só ajuda
    modelos pequenos a citar; não dispensa a validação.
    """
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        value = value.get("sentences", value.get("answer", []))
    lines = []
    for item in value if isinstance(value, list) else []:
        if isinstance(item, str):
            lines.append(item)
        elif isinstance(item, dict):
            text = str(item.get("text", "")).strip()
            ids = item.get("ids") or []
            ids = [str(i) for i in ids] if isinstance(ids, list) else [str(ids)]
            ids = [i.strip().strip("[]`'\" ").strip() for i in ids]
            ids = [i for i in ids if i]
            lines.append(f"{text} [{', '.join(ids)}]" if ids else text)
    return "\n".join(lines)


def _facts_block(facts: list[dict]) -> str:
    """Um facto por linha, com o id em destaque (mais fácil de citar que JSON)."""
    lines = []
    for f in facts:
        note = f" — {f['note']}" if f.get("note") else ""
        lines.append(f"[{f['id']}] {f['label']}: {f['value']} (status: {f['status']}){note}")
    return "\n".join(lines)


# Exemplo só com marcadores: um exemplo com tecnologias reais é copiado por modelos pequenos.
EXAMPLE = 'Formato: {"sentences": [{"text": "<frase sobre um facto>", "ids": ["<id do facto>"]}]}'


def _example_for(keys: list[str]) -> str:
    inner = ", ".join(f'"{k}": [{{"text": "<frase>", "ids": ["<id>"]}}]' for k in keys)
    return f"Formato: {{{inner}}}"


# ---------------------------------------------------------------------- factos para a LLM

MAX_PER_CATEGORY = {"dependency": 25, "route": 20, "script": 10}


def compact_facts(claims: list[Claim]) -> list[dict]:
    """Só o que a LLM precisa: sem excertos de código."""
    counts: dict[str, int] = {}
    out = []
    for c in claims:
        limit = MAX_PER_CATEGORY.get(c.category)
        if limit is not None:
            counts[c.category] = counts.get(c.category, 0) + 1
            if counts[c.category] > limit:
                continue
        value = c.value if not isinstance(c.value, (dict, list)) else json.dumps(c.value, ensure_ascii=False)
        value = str(value)[:200] if value is not None else None
        fact = {"id": c.id, "label": c.label, "value": value, "status": c.status}
        if c.note:
            fact["note"] = c.note
        out.append(fact)
    return out


SYSTEM = (
    "És um redator técnico rigoroso. Escreves APENAS com base nos factos fornecidos, "
    "em português de Portugal. Nunca inventes tecnologias, ficheiros ou comportamentos. "
    "Cada frase termina com os ids dos factos que a suportam entre parênteses retos, por "
    "exemplo: «Usa SQLite para guardar dados [db.sqlite].» Usa só ids que aparecem nos factos. "
    "Factos com status «inferred» descrevem-se com cautela (por exemplo «declara», «parece»). "
    "Factos «unknown» significam que não foi possível determinar. Factos «contradiction» são divergências."
)


def readme_excerpt(profile: ProjectProfile, read: Callable[[str], str | None]) -> tuple[str, int] | None:
    """Primeiro parágrafo do README (depois do título) e a linha onde começa."""
    claim = profile.get(README_ID)
    if not claim or not claim.value:
        return None
    text = read(claim.value)
    if not text:
        return None
    lines = text.splitlines()
    para: list[str] = []
    start = 0
    in_code = False
    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if in_code or stripped.startswith(("#", "![", "[![", "<")):
            if para:
                break
            continue
        if not stripped:
            if para:
                break
            continue
        if not para:
            start = i
        para.append(stripped)
        if sum(len(p) for p in para) > 800:
            break
    return (" ".join(para)[:900], start) if para else None


# ---------------------------------------------------------------------- overview


@dataclass
class Overview:
    model: str | None
    summary: Validated | None
    error: str | None = None


def generate_overview(profile: ProjectProfile, model: TextModel | None) -> Overview:
    if model is None:
        return Overview(None, None, "redação desligada")
    facts = compact_facts(profile.claims)
    prompt = (
        "Escreve um resumo do projeto em 4 a 8 frases curtas. Cada frase cita, em «ids», "
        "os ids (entre parênteses retos na lista) dos factos que a suportam. "
        'Devolve só JSON: {"sentences": [{"text": "...", "ids": ["..."]}]}.\n'
        f"{EXAMPLE}\n\nFactos:\n{_facts_block(facts)}"
    )
    try:
        raw = model.generate(prompt, system=SYSTEM, json_mode=True)
    except LLMUnavailable as exc:
        return Overview(model.name, None, str(exc))
    try:
        text = structured_to_text(json.loads(raw))
    except json.JSONDecodeError:
        text = raw
    return Overview(model.name, validate(text, {c.id for c in profile.claims}))


# ---------------------------------------------------------------------- explain

UI_TECH = {"react", "vue", "svelte", "angular", "nextjs", "nuxt", "vite", "streamlit", "gradio", "electron"}
BACKEND_TECH = {"express", "fastify", "koa", "nestjs", "hono", "fastapi", "flask", "django"}
START_SCRIPTS = {"start", "dev", "serve", "build"}


def _known(claims: list[Claim]) -> list[Claim]:
    return [c for c in claims if c.status != "unknown"]


def _tech(claims: list[Claim], prefix: str, ids: set[str]) -> list[Claim]:
    return [c for c in claims if c.id.startswith(prefix) and c.id.split(".", 1)[1] in ids]


def _q_what(cs: list[Claim]) -> list[Claim]:
    keep = ("project.type", "project.components", "lang.primary")
    return [c for c in cs if c.id in keep or c.category in ("framework", "service", "database")]


def _q_start(cs: list[Claim]) -> list[Claim]:
    return [c for c in cs if c.category == "entry_point"] + [
        c for c in cs if c.category == "script" and c.label.split(":")[-1] in START_SCRIPTS
    ]


def _q_ui(cs: list[Claim]) -> list[Claim]:
    pages = [c for c in cs if c.category == "route" and isinstance(c.value, dict) and c.value.get("method") == "PAGE"]
    return _tech(cs, "framework.", UI_TECH) + pages[:10]


def _q_backend(cs: list[Claim]) -> list[Claim]:
    routes = [c for c in cs if c.category == "route" and isinstance(c.value, dict) and c.value.get("method") != "PAGE"]
    return _tech(cs, "framework.", BACKEND_TECH) + routes[:15]


def _q_data(cs: list[Claim]) -> list[Claim]:
    return [c for c in cs if c.category in ("database", "orm")]


def _q_apis(cs: list[Claim]) -> list[Claim]:
    return [c for c in cs if c.category == "service"]


def _q_files(cs: list[Claim]) -> list[Claim]:
    return [c for c in cs if c.id == "files.important"]


def _q_communication(cs: list[Claim]) -> list[Claim]:
    components = [c for c in cs if c.id == "project.components"]
    has_ui, has_backend = bool(_q_ui(cs)), bool(_tech(cs, "framework.", BACKEND_TECH))
    if not components and not (has_ui and has_backend):
        return []
    routes = [c for c in cs if c.category == "route"][:10]
    return components + _tech(cs, "framework.", UI_TECH | BACKEND_TECH) + routes + _q_apis(cs)


def _q_docs(cs: list[Claim]) -> list[Claim]:
    docs = [c for c in cs if c.category == "docs_vs_code"]
    readme = [c for c in cs if c.id == README_ID]
    return docs + readme if readme else docs


@dataclass(frozen=True)
class Question:
    key: str
    text: str
    select: Callable[[list[Claim]], list[Claim]] | None  # None = resposta determinista própria
    llm: bool = True


QUESTIONS: tuple[Question, ...] = (
    Question("what", "O que faz este projeto?", _q_what),
    Question("start", "Como arranca?", _q_start),
    Question("ui", "Onde está a interface?", _q_ui),
    Question("backend", "Onde está o backend?", _q_backend),
    Question("data", "Onde estão os dados?", _q_data),
    Question("apis", "Que APIs externas usa?", _q_apis),
    Question("files", "Quais são os ficheiros mais importantes?", _q_files, llm=False),
    Question("communication", "Como comunicam os componentes?", _q_communication),
    Question("recent", "O que mudou recentemente?", None, llm=False),
    Question("docs", "A documentação corresponde ao código?", _q_docs),
    Question("unknown", "O que não foi possível determinar?", None, llm=False),
)


@dataclass
class Answer:
    question: Question
    facts: list[Claim] = field(default_factory=list)
    lines: list[str] = field(default_factory=list)  # linhas deterministas extra (com fonte)
    drafted: Validated | None = None

    @property
    def unknown(self) -> bool:
        return not self.facts and not self.lines


@dataclass
class Explanation:
    profile: ProjectProfile
    answers: list[Answer]
    model: str | None
    llm_error: str | None = None
    readme: tuple[str, int] | None = None


def explain(
    profile: ProjectProfile,
    model: TextModel | None,
    *,
    root: Path,
    read: Callable[[str], str | None],
) -> Explanation:
    claims = _known(profile.claims)
    readme = readme_excerpt(profile, read)
    answers: list[Answer] = []
    for q in QUESTIONS:
        answer = Answer(q)
        if q.select is not None:
            answer.facts = q.select(claims)
        if q.key == "what" and readme:
            readme_file = profile.get(README_ID).value  # type: ignore[union-attr]
            answer.lines.append(f"Fonte: {readme_file}:{readme[1]} — «{readme[0][:300]}»")
        elif q.key == "docs" and answer.facts and not any(c.category == "docs_vs_code" for c in answer.facts):
            answer.lines.append("Nenhuma divergência detetada entre a documentação e o código.")
        elif q.key == "recent":
            answer.lines.extend(_recent_lines(root, profile))
        elif q.key == "unknown":
            unknown = [c for c in profile.claims if c.status == "unknown"]
            answer.lines.extend(f"? {c.label}" + (f" — {c.note}" if c.note else "") for c in unknown)
            if not unknown:
                answer.lines.append("Todos os aspetos analisados foram determinados.")
        answers.append(answer)

    explanation = Explanation(profile, answers, model.name if model else None, readme=readme)
    if model is not None:
        try:
            _draft_answers(explanation, model)
        except LLMUnavailable as exc:
            explanation.llm_error = str(exc)
    return explanation


def _recent_lines(root: Path, profile: ProjectProfile) -> list[str]:
    lines = []
    if profile.last_change:
        source = "git" if profile.last_change_source == "git" else "ficheiros"
        lines.append(f"Última alteração: {profile.last_change.astimezone():%Y-%m-%d %H:%M} ({source})")
    snaps = list_snapshots(root, limit=2)
    if len(snaps) == 2:
        diff = diff_snapshots(snaps[0], snaps[1])
        if diff.empty:
            lines.append(f"Sem alterações entre as duas últimas análises ({snaps[0].scanned_at:%Y-%m-%d}).")
        for ch in diff.all()[:12]:
            lines.append(f"{ch.sign} {ch.text}" + (f" ({ch.location})" if ch.location else ""))
    elif not lines:
        return []
    return lines


def _draft_answers(explanation: Explanation, model: TextModel) -> None:
    asked = [a for a in explanation.answers if a.question.llm and a.facts]
    if not asked:
        return
    blocks = []
    for a in asked:
        block = f"## {a.question.key}: {a.question.text}\n{_facts_block(compact_facts(a.facts))}"
        if a.question.key == "what" and explanation.readme:
            block += f"\n[{README_ID}] Excerto do README: {explanation.readme[0]}"
        blocks.append(block)
    keys = [a.question.key for a in asked]
    prompt = (
        "Responde a cada pergunta em 1 a 3 frases curtas, usando só os factos listados nessa pergunta. "
        "Cada frase cita, em «ids», os ids (entre parênteses retos) dos factos que a suportam. "
        f"Devolve só um objeto JSON com exatamente estas chaves: {', '.join(keys)}.\n"
        f"{_example_for(keys)}\n\n" + "\n\n".join(blocks)
    )
    raw = model.generate(prompt, system=SYSTEM, json_mode=True)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    for a in asked:
        value = data.get(a.question.key)
        if value is None:
            continue
        text = structured_to_text(value)
        allowed = {c.id for c in a.facts}
        if a.question.key == "what" and explanation.readme:
            allowed.add(README_ID)
        a.drafted = validate(text, allowed)


# ---------------------------------------------------------------------- overview.md


def overview_markdown(explanation: Explanation, overview: Overview, generated_at: str) -> str:
    p = explanation.profile
    name = Path(p.root).name
    out = [f"# {name}", "", f"> Gerado pelo LocalAlibiScan em {generated_at}. Cada afirmação cita os factos (Claims) de onde vem.", ""]
    out += ["## Resumo", ""]
    if overview.summary and overview.summary.sentences:
        out += [f"*{AI_MARK} (modelo {overview.model}).*", "", overview.summary.text, ""]
        if overview.summary.removed:
            out += [f"*{len(overview.summary.removed)} frase(s) removida(s) pelo validador (sem citação válida).*", ""]
    else:
        reason = overview.error or "nenhuma frase passou no validador"
        out += [f"*Redação por IA indisponível ({reason}). Só factos abaixo.*", ""]

    out += ["## Explique-me este projeto", ""]
    for a in explanation.answers:
        out += [f"### {a.question.text}", ""]
        if a.unknown:
            out += ["? Sem factos para responder.", ""]
            continue
        if a.drafted and a.drafted.sentences:
            out += [f"*≈ IA:* {a.drafted.text}", ""]
        for line in a.lines:
            out.append(f"- {line}")
        for c in a.facts:
            loc = f" — `{c.evidence[0].location()}`" if c.evidence else ""
            out.append(f"- {c.symbol} **{c.label}**: {_value(c)}{loc} `[{c.id}]`")
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def _value(c: Claim) -> str:
    from .render import format_value

    if c.id == "files.important" and isinstance(c.value, list):
        return "; ".join(f"{i['path']} ({i['reason']})" for i in c.value)
    return format_value(c)
