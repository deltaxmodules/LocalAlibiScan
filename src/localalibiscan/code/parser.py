"""Extração de factos de código com tree-sitter (Python, JavaScript, TypeScript).

Por ficheiro: imports (com os nomes locais que criam), funções, classes,
chamadas (com o primeiro argumento de texto), decoradores e literais de texto.
Nunca executa código: só lê e analisa a árvore sintática.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cache

from tree_sitter import Node, Parser

EXTENSION_GRAMMAR: dict[str, str] = {
    ".py": "python",
    ".pyw": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".mts": "typescript",
    ".cts": "typescript",
    ".tsx": "tsx",
}

MAX_TEXT = 200


@dataclass
class Import:
    module: str  # "openai", "./routes/notes", ".models"
    line: int
    names: list[str] = field(default_factory=list)  # nomes locais criados


@dataclass
class Symbol:
    name: str
    line: int
    exported: bool = False


@dataclass
class Call:
    callee: str  # "client.chat.completions.create", "new Database"
    line: int
    first_string: str | None = None
    args: list[str] = field(default_factory=list)  # texto dos argumentos (curto)


@dataclass
class Decorator:
    text: str  # sem o "@"
    line: int
    target: str | None  # nome da função/classe decorada


@dataclass
class StringLit:
    value: str
    line: int


@dataclass
class FileFacts:
    path: str
    language: str
    imports: list[Import] = field(default_factory=list)
    functions: list[Symbol] = field(default_factory=list)
    classes: list[Symbol] = field(default_factory=list)
    calls: list[Call] = field(default_factory=list)
    decorators: list[Decorator] = field(default_factory=list)
    strings: list[StringLit] = field(default_factory=list)
    error: bool = False  # a árvore tem erros de sintaxe (os factos são parciais)


@cache
def _parser(grammar: str) -> Parser:
    from tree_sitter_language_pack import get_parser

    return get_parser(grammar)


def grammar_for(extension: str) -> str | None:
    return EXTENSION_GRAMMAR.get(extension)


def parse_source(path: str, source: bytes, grammar: str) -> FileFacts:
    tree = _parser(grammar).parse(source)
    lang = "python" if grammar == "python" else "javascript"
    facts = FileFacts(path=path, language=grammar, error=tree.root_node.has_error)
    visit = _visit_python if lang == "python" else _visit_js
    stack = [tree.root_node]
    while stack:
        node = stack.pop()
        visit(node, facts)
        stack.extend(reversed(node.named_children))
    return facts


# ----------------------------------------------------------------------- utilidades


def _text(node: Node | None) -> str:
    if node is None:
        return ""
    return node.text.decode("utf-8", errors="replace")


def _line(node: Node) -> int:
    return node.start_point[0] + 1


def _short(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= MAX_TEXT else text[: MAX_TEXT - 1] + "…"


def _string_value(node: Node) -> str | None:
    """Valor de um literal de texto (sem aspas nem prefixos), ou None."""
    if node.type == "string":
        parts = [c for c in node.named_children if c.type in ("string_content", "string_fragment")]
        if parts:
            return "".join(_text(p) for p in parts)
        raw = _text(node)
        # string vazia: '' ou "" (com prefixos em Python, ex. f"")
        return "" if raw.rstrip("\"'").lstrip("rbfuRBFU\"'") == "" else None
    if node.type == "template_string":
        if any(c.type == "template_substitution" for c in node.named_children):
            return None
        return _text(node).strip("`")
    return None


def _args(node: Node | None) -> tuple[str | None, list[str]]:
    if node is None:
        return None, []
    first_string = None
    texts = []
    for i, arg in enumerate(node.named_children):
        if arg.type == "comment":
            continue
        texts.append(_short(_text(arg)))
        if i == 0:
            first_string = _string_value(arg)
    return first_string, texts[:6]


def _record_string(node: Node, facts: FileFacts) -> None:
    value = _string_value(node)
    if value and len(value) <= MAX_TEXT:
        facts.strings.append(StringLit(value, _line(node)))


# ----------------------------------------------------------------------- Python


def _visit_python(node: Node, facts: FileFacts) -> None:
    t = node.type
    if t == "import_statement":
        for child in node.named_children:
            if child.type == "dotted_name":
                facts.imports.append(Import(_text(child), _line(node), [_text(child).split(".")[0]]))
            elif child.type == "aliased_import":
                name = _text(child.child_by_field_name("name"))
                alias = _text(child.child_by_field_name("alias"))
                facts.imports.append(Import(name, _line(node), [alias or name.split(".")[0]]))
    elif t == "import_from_statement":
        module = _text(node.child_by_field_name("module_name"))
        names = []
        for child in node.children_by_field_name("name"):
            if child.type == "aliased_import":
                names.append(_text(child.child_by_field_name("alias")))
            else:
                names.append(_text(child).split(".")[-1])
        facts.imports.append(Import(module, _line(node), names))
    elif t == "function_definition":
        facts.functions.append(Symbol(_text(node.child_by_field_name("name")), _line(node)))
    elif t == "class_definition":
        facts.classes.append(Symbol(_text(node.child_by_field_name("name")), _line(node)))
    elif t == "decorated_definition":
        target = node.child_by_field_name("definition")
        name = _text(target.child_by_field_name("name")) if target is not None else None
        for child in node.named_children:
            if child.type == "decorator":
                facts.decorators.append(Decorator(_short(_text(child).lstrip("@")), _line(child), name))
    elif t == "call":
        first, args = _args(node.child_by_field_name("arguments"))
        facts.calls.append(Call(_short(_text(node.child_by_field_name("function"))), _line(node), first, args))
    elif t == "string":
        _record_string(node, facts)


# ----------------------------------------------------------------------- JS / TS


def _is_exported(node: Node) -> bool:
    parent = node.parent
    for _ in range(3):
        if parent is None:
            return False
        if parent.type == "export_statement":
            return True
        parent = parent.parent
    return False


def _import_names(node: Node) -> list[str]:
    names = []
    clause = next((c for c in node.named_children if c.type == "import_clause"), None)
    if clause is None:
        return names
    for child in clause.named_children:
        if child.type == "identifier":
            names.append(_text(child))
        elif child.type == "namespace_import":
            names.extend(_text(c) for c in child.named_children if c.type == "identifier")
        elif child.type == "named_imports":
            for spec in child.named_children:
                if spec.type == "import_specifier":
                    alias = spec.child_by_field_name("alias") or spec.child_by_field_name("name")
                    names.append(_text(alias))
    return names


def _declarator_names(node: Node) -> list[str]:
    """Nomes ligados por `const X = require(...)` / `const { a, b } = require(...)`."""
    parent = node.parent
    while parent is not None and parent.type not in ("variable_declarator", "expression_statement", "program"):
        parent = parent.parent
    if parent is None or parent.type != "variable_declarator":
        return []
    name = parent.child_by_field_name("name")
    if name is None:
        return []
    if name.type == "identifier":
        return [_text(name)]
    return [
        _text(c.child_by_field_name("value") or c) if c.type == "pair_pattern" else _text(c)
        for c in name.named_children
        if c.type in ("shorthand_property_identifier_pattern", "pair_pattern", "identifier")
    ]


def _visit_js(node: Node, facts: FileFacts) -> None:
    t = node.type
    if t == "import_statement":
        source = _string_value(node.child_by_field_name("source")) if node.child_by_field_name("source") else None
        if source is not None:
            facts.imports.append(Import(source, _line(node), _import_names(node)))
    elif t == "export_statement" and node.child_by_field_name("source") is not None:
        source = _string_value(node.child_by_field_name("source"))
        if source is not None:
            facts.imports.append(Import(source, _line(node), []))
    elif t in ("call_expression", "new_expression"):
        fn = node.child_by_field_name("function" if t == "call_expression" else "constructor")
        first, args = _args(node.child_by_field_name("arguments"))
        callee = _short(_text(fn))
        if t == "new_expression":
            callee = f"new {callee}"
        elif fn is not None and (callee == "require" or fn.type == "import") and first is not None:
            facts.imports.append(Import(first, _line(node), _declarator_names(node)))
        facts.calls.append(Call(callee, _line(node), first, args))
    elif t in ("function_declaration", "generator_function_declaration", "method_definition"):
        facts.functions.append(Symbol(_text(node.child_by_field_name("name")), _line(node), _is_exported(node)))
    elif t == "variable_declarator":
        value = node.child_by_field_name("value")
        if value is not None and value.type in ("arrow_function", "function_expression", "function"):
            facts.functions.append(Symbol(_text(node.child_by_field_name("name")), _line(node), _is_exported(node)))
    elif t in ("class_declaration", "class"):
        name = node.child_by_field_name("name")
        if name is not None:
            facts.classes.append(Symbol(_text(name), _line(node), _is_exported(node)))
    elif t in ("string", "template_string"):
        _record_string(node, facts)
