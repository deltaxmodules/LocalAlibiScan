from __future__ import annotations

from localalibiscan.code.parser import parse_source


def test_python_facts() -> None:
    src = b'''import os, numpy as np
from .models import User
from fastapi import APIRouter as R, Depends

router = R(prefix="/users")

@router.get("/{id}")
async def get_user(id: int):
    return os.environ.get("X")

class Repo:
    def save(self):
        pass
'''
    f = parse_source("api.py", src, "python")
    assert [(i.module, i.line, i.names) for i in f.imports] == [
        ("os", 1, ["os"]),
        ("numpy", 1, ["np"]),
        (".models", 2, ["User"]),
        ("fastapi", 3, ["R", "Depends"]),
    ]
    assert [(d.text, d.line, d.target) for d in f.decorators] == [('router.get("/{id}")', 7, "get_user")]
    assert {s.name for s in f.functions} == {"get_user", "save"}
    assert [c.name for c in f.classes] == ["Repo"]
    call = next(c for c in f.calls if c.callee == "R")
    assert call.args == ['prefix="/users"']
    assert any(s.value == "X" and s.line == 9 for s in f.strings)


def test_js_facts() -> None:
    src = b"""import express, { Router as R } from 'express';
import * as path from "node:path";
const { Pool } = require('pg');
export { thing } from './thing';
export async function GET(req) {}
export const POST = async () => {};
const db = new Pool({ connectionString: `postgres://localhost/db` });
"""
    f = parse_source("server.ts", src, "typescript")
    assert [(i.module, i.names) for i in f.imports] == [
        ("express", ["express", "R"]),
        ("node:path", ["path"]),
        ("pg", ["Pool"]),
        ("./thing", []),
    ]
    exported = {s.name for s in f.functions if s.exported}
    assert exported == {"GET", "POST"}
    assert any(c.callee == "new Pool" and c.line == 7 for c in f.calls)
    assert any(s.value == "postgres://localhost/db" for s in f.strings)


def test_tsx_and_syntax_errors_do_not_crash() -> None:
    src = b"export default function App() { return <div>{x}</div> }\nfunction broken( {"
    f = parse_source("App.tsx", src, "tsx")
    assert f.error
    assert f.functions[0].name == "App"
