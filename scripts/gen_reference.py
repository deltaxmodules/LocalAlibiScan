"""Gera as páginas de referência do manual a partir do código.

    python scripts/gen_reference.py          # escreve site/reference/{commands,technologies}.md
    python scripts/gen_reference.py --check  # falha se estiverem desatualizadas (usado nos testes)
"""

from __future__ import annotations

import sys
from pathlib import Path

import typer

from localalibiscan.cli import app
from localalibiscan.i18n import t as tr
from localalibiscan.tech import TECHS

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "site" / "reference"

HEADER = "<!-- Gerado por scripts/gen_reference.py a partir do código. Não editar à mão. -->\n\n"

# Descrições do manual (mais longas do que a ajuda da CLI, e com ligações).
COMMAND_DOCS = {
    "files": "List the files that would be analysed, with extension and size (respects `.gitignore`; large and binary files are marked).",
    "check": "Show only the [folder verdict](../guide/folder-verdict) and its evidence. No analysis.",
    "scan": "Analyse a project and show its profile: every claim with its status and evidence. Writes `.localalibi/`.",
    "dashboard": "[Dashboard](../guide/dashboard) of every project under a folder; `--html` writes `~/.localalibi/dashboard.html`.",
    "refresh": "Analyse again and show [what changed](../guide/refresh) since the previous analysis.",
    "history": "List previous analyses with a one-line summary each.",
    "explain": "[Explain this project](../guide/explain): fixed questions answered with facts (and optional local AI). Writes `.localalibi/overview.md`.",
    "ask": "[Ask a question](../guide/ask): deterministic search first; the optional local model answers only from the evidence.",
    "config": "Show the configuration in use; `--init` creates `~/.localalibi/config.toml`.",
}
OPTION_DOCS = {
    "--force": "Analyse even if the folder doesn't look like a project.",
    "--evidence": "Show every piece of evidence of each claim (default: the first one).",
    "--only": "Only these sections, comma-separated, e.g. `db,framework,routes,docs-vs-code`.",
    "--html": "Also write the self-contained HTML report to `~/.localalibi/dashboard.html`.",
    "--lang": "Only projects that contain this language (e.g. `python`).",
    "--depth": "How many levels to walk down looking for projects (default 2).",
    "--no-cache": "Re-analyse every project.",
    "--no-llm": "Don't use Ollama: facts / evidence only.",
    "--model": "Ollama model to use (default from the configuration).",
    "--brief": "One line per piece of evidence, without code excerpts.",
    "--init": "Create `~/.localalibi/config.toml` with the defaults (never overwrites).",
    "--max-size": "Maximum size in bytes for a file to be read.",
    "--version": "Show the version and exit.",
    "--lang-ui": "Interface language: `en` (default) or `pt`. Goes before the command: `las --lang-ui pt scan .`. Same as `LOCALALIBI_LANG` or `[ui] language` in the [configuration](configuration).",
}


def commands_md() -> str:
    group = typer.main.get_command(app)
    out = [HEADER, "# Commands\n\n",
           "Every command is available as `las` and as `localalibiscan`. "
           "`FOLDER` defaults to the current folder.\n\n"]
    out.append("| Command | What it does |\n|---|---|\n")
    names = list(group.commands)
    for name in names:
        out.append(f"| [`las {name}`](#las-{name}) | {COMMAND_DOCS[name].split('. ')[0].rstrip('.')}. |\n")
    out.append("\n## Global options\n\n| Option | |\n|---|---|\n")
    for p in group.params:
        if p.param_type_name == "option" and p.opts[0] != "--help":
            out.append(f"| `{p.opts[0]}` | {OPTION_DOCS[p.opts[0]]} |\n")
    for name in names:
        cmd = group.commands[name]
        args = " ".join(p.name.upper() for p in cmd.params if p.param_type_name == "argument")
        out.append(f"\n## las {name}\n\n```bash\nlas {name} {args} [OPTIONS]\n```\n\n{COMMAND_DOCS[name]}\n")
        options = [p for p in cmd.params if p.param_type_name == "option" and p.opts[0] != "--help"]
        if options:
            out.append("\n| Option | |\n|---|---|\n")
            for p in options:
                out.append(f"| `{p.opts[0]}` | {OPTION_DOCS[p.opts[0]]} |\n")
    out.append(
        "\n## Exit codes\n\n| Code | Meaning |\n|---|---|\n| 0 | OK |\n"
        "| 1 | `las ask` found no evidence · `las config --init` found an existing file |\n"
        "| 2 | Not analysed: the folder is not a project (use `--force`), no projects found, or no history |\n"
    )
    return "".join(out)


def technologies_md() -> str:
    out = [HEADER, "# Detected technologies\n\n",
           "This table is the single source used by the detectors (code, manifests, configuration) "
           "and by [documentation vs code](../guide/docs-vs-code). A trailing `*` is a prefix.\n"]
    for category in ("database", "orm", "framework", "service"):
        out.append(f"\n## {dict(database='Databases', orm='ORMs', framework='Frameworks', service='External services')[category]}\n\n")
        out.append("| Technology | npm | PyPI | Imports | In strings / URLs | Env vars / config files |\n|---|---|---|---|---|---|\n")
        for t in TECHS:
            if t.category != category:
                continue
            cell = lambda xs: ", ".join(f"`{x}`" for x in xs) or "—"
            extra = list(t.env) + list(t.config_files)
            also = f" (also {', '.join(tr(f"category.{c}", lang="en").lower() for c in t.also)})" if t.also else ""
            out.append(f"| **{t.name}**{also} | {cell(t.npm)} | {cell(t.pypi)} | {cell(t.imports)} | {cell(t.strings)} | {cell(extra)} |\n")
    return "".join(out)


def main() -> int:
    pages = {"commands.md": commands_md(), "technologies.md": technologies_md()}
    if "--check" in sys.argv:
        stale = [n for n, text in pages.items() if not (OUT / n).is_file() or (OUT / n).read_text(encoding="utf-8") != text]
        if stale:
            print(f"Desatualizado: {', '.join(stale)} — corra python scripts/gen_reference.py", file=sys.stderr)
            return 1
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    for name, text in pages.items():
        (OUT / name).write_text(text, encoding="utf-8")
        print(f"escrito site/reference/{name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
