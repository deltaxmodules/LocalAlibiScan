"""Perguntas livres sobre o projeto, com evidências primeiro (Fase 7).

1. Procura determinista: Claims, nomes de ficheiros, funções/classes, imports e
   rotas, por palavras-chave e sinónimos simples.
2. Junta excertos (algumas linhas à volta de cada resultado).
3. A LLM (opcional) responde só com base nos excertos, citando `ficheiro:linha`.
4. O validador remove frases sem citação de uma linha que esteja nos excertos.
Sem resultados, não se chama a LLM.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from .code import code_index
from .knowledge import in_non_product_dir
from .drafting import Validated, structured_to_text, validate
from .i18n import claim_label, t
from .llm import LLMUnavailable, TextModel
from .models import Claim, ProjectProfile
from .project import Project

CONTEXT = 2  # linhas antes/depois de cada resultado
MAX_EXCERPTS = 10

STOPWORDS = frozenset(
    """
    a o as os um uma uns umas de do da dos das em no na nos nas ao aos à às e ou que como qual quais quem
    onde porque por para com sem sobre se isto isso este esta estes estas esse essa aqui ali la lá
    é sao são esta está estao estão ser foi era tem têm temos ha há usa usam usamos uso usado usada
    feito feita feitos feitas faz fazem fazemos fica ficam projeto projecto codigo código ficheiro ficheiros
    arquivo arquivos pasta pastas parte
    where what which who how why when is are was were be the an of in on at to for with by from do does did
    we our you use used uses using done made make file files code project this that these those it its there
    """.split()
)

SYNONYM_GROUPS: tuple[tuple[str, ...], ...] = (
    ("autenticacao", "autenticar", "auth", "authentication", "authenticate", "login", "logout", "signin",
     "signup", "session", "sessao", "jwt", "token", "password", "senha", "oauth", "passport", "nextauth",
     "credentials", "credenciais", "autorizacao", "authorization", "permissions", "permissoes", "roles"),
    ("pagamento", "pagamentos", "pagar", "payment", "payments", "billing", "checkout", "stripe",
     "invoice", "fatura", "faturas", "subscription", "assinatura"),
    ("dados", "bd", "database", "db", "sql", "sqlite", "postgres", "postgresql", "mysql", "mongodb",
     "query", "queries", "schema", "migration", "migracao", "orm", "prisma", "sqlalchemy"),
    ("email", "emails", "mail", "smtp", "sendgrid", "resend", "nodemailer", "correio", "notificacao",
     "notificacoes", "notification", "notifications"),
    ("upload", "uploads", "storage", "armazenamento", "s3", "bucket"),
    ("teste", "testes", "test", "tests", "pytest", "jest", "vitest"),
    ("configuracao", "configuracoes", "config", "settings", "env", "environment", "variaveis", "variables",
     "definicoes"),
    ("rota", "rotas", "endpoint", "endpoints", "route", "routes", "router", "api"),
    ("ia", "ai", "llm", "openai", "anthropic", "ollama", "gpt", "claude", "gemini", "prompt", "chat"),
    ("interface", "ui", "frontend", "componente", "componentes", "component", "components", "page",
     "pagina", "paginas", "view", "views", "screen", "screens", "ecra"),
    ("log", "logs", "logging", "logger"),
    ("cache", "redis"),
    ("erro", "erros", "error", "errors", "exception", "excecao", "excecoes", "falha", "failure"),
    ("arranque", "arranca", "start", "startup", "starts", "main", "entrypoint", "inicio", "bootstrap"),
)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def base_terms(question: str) -> list[str]:
    """Palavras da própria pergunta (sem palavras vazias)."""
    words = re.findall(r"[\w.+#-]+", normalize(question))
    base = [w.strip(".-") for w in words if len(w.strip(".-")) >= 2 and w not in STOPWORDS]
    return list(dict.fromkeys(w for w in base if w and w not in STOPWORDS))


def terms_of(question: str) -> list[str]:
    """Palavras da pergunta seguidas dos sinónimos."""
    base = base_terms(question)
    expanded = list(base)
    for word in base:
        for group in SYNONYM_GROUPS:
            if word in group:
                expanded.extend(t for t in group if t not in expanded)
    return expanded


def identifier_tokens(name: str) -> set[str]:
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name)
    return {t for t in re.split(r"[^A-Za-z0-9]+", normalize(spaced)) if t}


def _matches(term: str, text: str) -> bool:
    tokens = identifier_tokens(text)
    if term in tokens:
        return True
    return len(term) >= 4 and term in normalize(text)


@dataclass
class Hit:
    file: str
    line: int
    reason: str
    score: int


@dataclass
class Excerpt:
    file: str
    start: int
    end: int
    lines: list[str]
    reasons: list[str] = field(default_factory=list)

    def citations(self) -> set[str]:
        return {f"{self.file}:{n}" for n in range(self.start, self.end + 1)}


@dataclass
class AskResult:
    question: str
    terms: list[str]
    excerpts: list[Excerpt]
    suggestions: list[str] = field(default_factory=list)
    answer: Validated | None = None
    model: str | None = None
    llm_error: str | None = None

    @property
    def found(self) -> bool:
        return bool(self.excerpts)


def search(project: Project, profile: ProjectProfile, question: str) -> tuple[list[str], list[Hit]]:
    terms = terms_of(question)
    direct = set(base_terms(question))
    hits: list[Hit] = []
    if not terms:
        return terms, hits

    def add(file: str, line: int | None, reason: str, score: int, matched: set[str]) -> None:
        if file in project.paths:
            # Termos escritos na pergunta valem mais do que sinónimos.
            bonus = 2 if matched & direct else 0
            # Testes, exemplos e templates mostram-se, mas depois do código do produto.
            penalty = 3 if in_non_product_dir(file) else 0
            hits.append(Hit(file, line or 1, reason, score + bonus - penalty))

    def matched(text: str) -> set[str]:
        return {t for t in terms if _matches(t, text)}

    # Claims (inclui serviços, BD, frameworks, rotas) e as suas evidências.
    for claim in profile.claims:
        if claim.status == "unknown" or claim.category in ("important_files", "language", "structure", "manifest"):
            continue
        text = " ".join([claim.id, claim.label, claim_label(claim), json.dumps(claim.value, ensure_ascii=False) if claim.value else ""])
        m = matched(text)
        if m:
            score = 4 if claim.category in ("service", "database", "orm", "framework", "route") else 2
            for ev in claim.evidence[:4]:
                kind_bonus = 1 if ev.kind == "code" else 0
                add(ev.file, ev.line, f"{claim_label(claim)}: {_short_value(claim)}", score + kind_bonus, m)

    index = code_index(project)
    for path, facts in index.files.items():
        for sym in facts.functions + facts.classes:
            m = matched(sym.name)
            if m:
                add(path, sym.line, t("ask.reason.defines", name=sym.name), 3, m)
        for imp in facts.imports:
            m = matched(imp.module) | set().union(*(matched(n) for n in imp.names)) if imp.names else matched(imp.module)
            if m:
                add(path, imp.line, t("ask.reason.imports", module=imp.module), 2, m)

    for path in project.paths:
        m = matched(PurePosixPath(path).stem)
        if m:
            add(path, 1, t("ask.reason.filename"), 1, m)

    return terms, hits


def build_excerpts(project: Project, hits: list[Hit]) -> list[Excerpt]:
    # Melhor pontuação por (ficheiro, linha); depois junta janelas sobrepostas.
    best: dict[tuple[str, int], Hit] = {}
    for h in hits:
        key = (h.file, h.line)
        if key not in best or h.score > best[key].score:
            best[key] = h
        elif h.reason not in best[key].reason:
            best[key].reason += f"; {h.reason}"
    ranked = sorted(best.values(), key=lambda h: (-h.score, h.file, h.line))

    def reasons_of(hit: Hit) -> list[str]:
        return list(dict.fromkeys(r for r in hit.reason.split("; ") if r))

    excerpts: list[Excerpt] = []
    for hit in ranked:
        lines = project.lines(hit.file)
        if not lines:
            continue
        start, end = max(1, hit.line - CONTEXT), min(len(lines), hit.line + CONTEXT)
        merged = next((e for e in excerpts if e.file == hit.file and start <= e.end + 1 and end >= e.start - 1), None)
        if merged:
            merged.start, merged.end = min(merged.start, start), max(merged.end, end)
            merged.lines = lines[merged.start - 1 : merged.end]
            merged.reasons.extend(r for r in reasons_of(hit) if r not in merged.reasons)
            continue
        if len(excerpts) >= MAX_EXCERPTS:
            continue
        excerpts.append(Excerpt(hit.file, start, end, lines[start - 1 : end], reasons_of(hit)))
    return excerpts


def suggestions(profile: ProjectProfile, project: Project) -> list[str]:
    """Termos que existem no projeto (para quando a procura não encontra nada)."""
    out: list[str] = []
    for claim in profile.claims:
        if claim.category in ("framework", "service", "database", "orm") and claim.status != "unknown":
            out.append(str(claim.value))
    routes = [c.value.get("path") for c in profile.claims if c.category == "route" and isinstance(c.value, dict)]
    out += sorted({"/" + r.strip("/").split("/")[0] for r in routes if r and r.strip("/")})[:5]
    dirs = sorted({PurePosixPath(p).parts[0] for p in project.paths if "/" in p})
    out += dirs[:6]
    return list(dict.fromkeys(out))[:12]


# Pedido em inglês; a resposta sai na língua da pergunta.
ASK_SYSTEM = (
    "You answer questions about a software project using ONLY the code excerpts provided. "
    "Never use outside knowledge or invent files, functions or services. Answer in the same "
    "language the question was written in. Each sentence says what happens at that place (which function, "
    "which route, what it does) and cites, in \"ids\", the file:line locations of the excerpts that support it. "
    "Do not repeat the same sentence for different places. If the excerpts are not enough to answer, "
    "say so in one sentence citing the closest excerpt."
)


def answer_with_llm(result: AskResult, model: TextModel) -> None:
    blocks = []
    for e in result.excerpts:
        numbered = "\n".join(f"{n}: {text}" for n, text in zip(range(e.start, e.end + 1), e.lines))
        blocks.append(f"### {e.file} (lines {e.start}-{e.end})\n{numbered}")
    prompt = (
        f"Question: {result.question}\n\n"
        "Answer in 1 to 4 short sentences. Each sentence cites in \"ids\" one or more locations in the format "
        "file:line (e.g. \"folder/file.py:12\"), chosen from the numbered lines below.\n"
        'Return only JSON: {"sentences": [{"text": "<sentence>", "ids": ["<file>:<line>"]}]}\n\n'
        "Excerpts:\n" + "\n\n".join(blocks)
    )
    raw = model.generate(prompt, system=ASK_SYSTEM, json_mode=True)
    try:
        text = structured_to_text(json.loads(raw))
    except json.JSONDecodeError:
        text = raw
    # "ficheiro:10-12" conta como "ficheiro:10".
    text = re.sub(r"(:\d+)\s*-\s*\d+", r"\1", text)
    known = set().union(*(e.citations() for e in result.excerpts))
    result.answer = validate(text, known)
    result.model = model.name


def ask(project: Project, profile: ProjectProfile, question: str, model: TextModel | None) -> AskResult:
    terms, hits = search(project, profile, question)
    result = AskResult(question, terms, build_excerpts(project, hits))
    if not result.found:
        result.suggestions = suggestions(profile, project)
        return result  # sem evidências: nunca se chama a LLM
    if model is not None:
        try:
            answer_with_llm(result, model)
        except LLMUnavailable as exc:
            result.llm_error = str(exc)
    return result


def _short_value(claim: Claim) -> str:
    if isinstance(claim.value, dict):
        return str(claim.value.get("path") or claim.value.get("name") or claim.label)
    return str(claim.value)[:60]


__all__ = ["AskResult", "Excerpt", "ask", "search", "terms_of"]
