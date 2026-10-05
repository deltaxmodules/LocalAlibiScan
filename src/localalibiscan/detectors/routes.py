"""Detetor `routes`: rotas HTTP com ficheiro e linha.

Suporta FastAPI/Flask (decoradores), Express/Fastify/Koa/Hono (chamadas
`app.get('/x', ...)`), e as convenções de ficheiros do Next.js (App Router e
`pages/api`). Prefixos de routers são resolvidos quando estão no mesmo ficheiro
ou montados com `include_router` / `register_blueprint` / `app.use` /
`fastify.register` a partir de um import local.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..code import FileFacts, code_index
from ..code.index import CodeIndex
from ..knowledge import in_non_product_dir
from ..models import Claim
from ..project import Project
from .base import Detector, register
from .manifests import parse_manifests

HTTP_METHODS = ("get", "post", "put", "delete", "patch", "options", "head")
PY_ROUTE = re.compile(
    r"^(?P<obj>[\w.]+)\.(?P<verb>get|post|put|delete|patch|options|head|route|api_route|websocket)\((?P<args>.*)\)$",
    re.S,
)
JS_ROUTE = re.compile(r"^(?P<obj>[\w$]+)\.(?P<verb>get|post|put|delete|patch|options|head|all)$")
FIRST_STRING = re.compile(r"""^\s*[rbuRBU]?(["'`])(?P<s>[^"'`]*)\1""")
METHODS_KW = re.compile(r"methods\s*=\s*[\[(](?P<m>[^\])]*)[\])]")
PREFIX_KW = re.compile(r"""(?:url_)?prefix\s*[=:]\s*["'`](?P<p>[^"'`]*)["'`]""")
ASSIGN = re.compile(r"^\s*(?:export\s+)?(?:const|let|var)?\s*(?P<name>[\w$]+)\s*(?::\s*[\w.\[\]]+)?\s*=")

PY_ROUTER_FACTORIES = ("APIRouter", "Blueprint", "FastAPI", "Flask")
JS_ROUTER_FACTORIES = ("express", "Router", "express.Router", "fastify", "Fastify", "new Hono", "new Router", "new Koa", "Koa")
JS_DEFAULT_NAMES = frozenset({"app", "router", "server", "api", "fastify", "routes", "route"})
JS_WEB_PACKAGES = frozenset({"express", "fastify", "koa", "@koa/router", "koa-router", "hono"})
NEXT_FILE = re.compile(r"(?:^|/)(?:src/)?app/(?P<dir>(?:.*/)?)(?P<kind>route|page)\.(?:ts|tsx|js|jsx|mjs)$")
NEXT_PAGES_API = re.compile(r"(?:^|/)(?:src/)?pages/(?P<p>api/.*)\.(?:ts|tsx|js|jsx)$")


@dataclass
class Route:
    method: str
    path: str
    framework: str
    file: str
    line: int
    handler: str | None = None
    obj: str | None = None  # objeto onde foi declarada (app, router, ...)


def _join(prefix: str, path: str) -> str:
    """"/chat" + "/" -> "/chat/", "/chat" + "/models" -> "/chat/models"."""
    if not prefix:
        return path or "/"
    if not path:
        return prefix
    return prefix.rstrip("/") + "/" + path.lstrip("/")


def _assigned_name(project: Project, path: str, line: int) -> str | None:
    lines = project.lines(path)
    if 0 < line <= len(lines):
        match = ASSIGN.match(lines[line - 1])
        if match:
            return match.group("name")
    return None


# ----------------------------------------------------------------------- Python


def _python_routes(project: Project, index: CodeIndex, path: str, facts: FileFacts) -> list[Route]:
    modules = {imp.module.split(".")[0] for imp in facts.imports}
    framework = "FastAPI" if "fastapi" in modules else "Flask" if "flask" in modules else None
    if framework is None:
        return []

    prefixes: dict[str, str] = {}
    for call in facts.calls:
        if call.callee.split(".")[-1] in PY_ROUTER_FACTORIES:
            name = _assigned_name(project, path, call.line)
            match = PREFIX_KW.search(" ".join(call.args))
            if name:
                prefixes[name] = match.group("p") if match else ""

    routes = []
    for deco in facts.decorators:
        match = PY_ROUTE.match(deco.text)
        if not match:
            continue
        string = FIRST_STRING.match(match.group("args"))
        if not string:
            continue
        verb, obj = match.group("verb"), match.group("obj")
        if verb in ("route", "api_route"):
            methods_kw = METHODS_KW.search(match.group("args"))
            methods = re.findall(r"[\"'](\w+)[\"']", methods_kw.group("m")) if methods_kw else ["GET"]
        elif verb == "websocket":
            methods = ["WS"]
        else:
            methods = [verb]
        route_path = _join(prefixes.get(obj, ""), string.group("s"))
        for method in methods:
            routes.append(Route(method.upper(), route_path, framework, path, deco.line, deco.target, obj))
    return routes


# ----------------------------------------------------------------------- JS / TS


def _js_routes(project: Project, index: CodeIndex, path: str, facts: FileFacts) -> list[Route]:
    packages = {index.external_package(facts, imp) for imp in facts.imports}
    web = packages & JS_WEB_PACKAGES
    routers = set()
    for call in facts.calls:
        if call.callee in JS_ROUTER_FACTORIES:
            name = _assigned_name(project, path, call.line)
            if name:
                routers.add(name)
    if not routers and not web:
        return []
    framework = next(
        (n for p, n in (("express", "Express"), ("fastify", "Fastify"), ("hono", "Hono"), ("koa", "Koa"), ("@koa/router", "Koa"), ("koa-router", "Koa")) if p in web),
        "Express",
    )
    routes = []
    for call in facts.calls:
        match = JS_ROUTE.match(call.callee)
        if not match or call.first_string is None:
            continue
        obj = match.group("obj")
        if obj not in routers and not (web and obj in JS_DEFAULT_NAMES):
            continue
        if not (call.first_string.startswith("/") or call.first_string == "*"):
            continue
        method = "ANY" if match.group("verb") == "all" else match.group("verb").upper()
        routes.append(Route(method, call.first_string, framework, path, call.line, None, obj))
    return routes


# ----------------------------------------------------------------------- Next.js


def _next_routes(index: CodeIndex, project: Project) -> list[Route]:
    routes = []
    for path in sorted(project.paths):
        match = NEXT_FILE.search(path)
        if match:
            segments = [s for s in match.group("dir").split("/") if s and not (s.startswith("(") and s.endswith(")")) and not s.startswith("@")]
            url = "/" + "/".join(segments)
            facts = index.files.get(path)
            if match.group("kind") == "page":
                routes.append(Route("PAGE", url, "Next.js", path, 1))
            elif facts:
                for fn in facts.functions:
                    if fn.exported and fn.name.lower() in HTTP_METHODS:
                        routes.append(Route(fn.name.upper(), url, "Next.js", path, fn.line, fn.name))
            continue
        match = NEXT_PAGES_API.search(path)
        if match:
            url = "/" + re.sub(r"/index$", "", match.group("p"))
            routes.append(Route("ANY", url, "Next.js", path, 1))
    return routes


# ----------------------------------------------------------------------- montagens


def _apply_mounts(project: Project, index: CodeIndex, routes: list[Route]) -> None:
    """`app.use('/notes', notesRouter)` -> prefixa as rotas do ficheiro importado."""
    by_file: dict[str, list[Route]] = {}
    for r in routes:
        by_file.setdefault(r.file, []).append(r)

    for path, facts in index.files.items():
        imported = {}
        for imp in facts.imports:
            target = index.resolve(path, imp)
            if target:
                for name in imp.names:
                    imported[name] = target
        for call in facts.calls:
            verb = call.callee.split(".")[-1]
            prefix = None
            ident = None
            if verb == "use" and call.first_string and call.first_string.startswith("/") and len(call.args) >= 2:
                prefix, ident = call.first_string, call.args[1]
            elif verb in ("include_router", "register_blueprint", "register") and call.args:
                match = PREFIX_KW.search(" ".join(call.args[1:]))
                prefix, ident = (match.group("p") if match else None), call.args[0]
            if not prefix or not ident:
                continue
            target = imported.get(ident.split(".")[0])
            for route in by_file.get(target or "", []):
                if route.obj not in ("app",):
                    route.path = _join(prefix, route.path)


# ----------------------------------------------------------------------- detetor


def find_routes(project: Project) -> list[Route]:
    if "routes" in project.cache:
        return project.cache["routes"]
    index = code_index(project)
    routes: list[Route] = []
    for path, facts in index.files.items():
        if in_non_product_dir(path):
            continue
        if facts.language == "python":
            routes.extend(_python_routes(project, index, path, facts))
        else:
            routes.extend(_js_routes(project, index, path, facts))
    _apply_mounts(project, index, routes)
    has_next = any(d.name == "next" for m in parse_manifests(project) for d in m.dependencies)
    if has_next:
        routes.extend(_next_routes(index, project))
    project.cache["routes"] = routes
    return routes


@register
class RoutesDetector(Detector):
    name = "routes"

    def detect(self, project: Project) -> list[Claim]:
        claims: dict[str, Claim] = {}
        for route in find_routes(project):
            cid = f"route.{route.method} {route.path}"
            ev = project.evidence(route.file, route.line, "code")
            if cid in claims:
                claims[cid].evidence.append(ev)
                continue
            claims[cid] = self.claim(
                project,
                id=cid,
                category="route",
                label=f"{route.method} {route.path}",
                value={
                    "method": route.method,
                    "path": route.path,
                    "framework": route.framework,
                    "handler": route.handler,
                    "file": route.file,
                },
                status="confirmed",
                evidence=[ev],
            )
        return sorted(claims.values(), key=lambda c: (c.value["path"], c.value["method"]))


def route_files(project: Project) -> dict[str, int]:
    counts: dict[str, int] = {}
    for route in find_routes(project):
        counts[route.file] = counts.get(route.file, 0) + 1
    return counts


__all__ = ["RoutesDetector", "Route", "find_routes", "route_files"]
