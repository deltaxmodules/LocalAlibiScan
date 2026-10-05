# The dashboard

```bash
las dashboard ~/code                  # terminal table
las dashboard ~/code --html           # + ~/.localalibi/dashboard.html
las dashboard ~/code --lang python    # only projects with Python files
las dashboard ~/code --depth 3        # look deeper
las dashboard ~/code --no-cache       # re-analyse everything
```

## Columns

| Column | Content |
|---|---|
| Projeto | path relative to the root; ≈ for a probable project |
| Tipo | project type: `Python`, `Node.js/TypeScript`, `Monorepo (Python + Node.js/TypeScript)`, `≈Scripts Python`… |
| Stack | frameworks (≈ when only declared), or the main language |
| BD | databases (≈ when only declared) |
| Serviços | external services: OpenAI, Anthropic, Stripe, AWS, Supabase… |
| Alterado | last change: the newest of the last commit and the newest file (`git` when it came from git) |
| Mudou | what changed since the previous analysis: `+2 -1 ~3 ⚠1`, `—` (nothing, served from cache) or `novo` |
| Alertas | ⚠ contradictions and ? unknowns |

Rows are sorted by last change, newest first.

## How projects are found

The dashboard uses exactly the same rules as [`las check`](./folder-verdict): it walks down, takes every folder with `.git` or a manifest as a project **and does not look inside it** (a monorepo counts once), and when a folder contains no project at all, it asks for its verdict — loose script folders become ≈ probable projects, and deeper folders of projects are expanded.

Hidden folders, `node_modules`, `.venv` and any virtualenv (a folder with `pyvenv.cfg`, whatever its name) are skipped.

If you point it at a folder that is itself a project, it shows that project's profile and suggests `las scan`.

## Cache

Each project's profile is saved in its `.localalibi/project.json` together with a fingerprint: the path, modification time and size of every file, the git `HEAD`, and the tool version. If the fingerprint matches, the profile is reused; otherwise the project is analysed again. On a folder with 50+ real projects, a cached run takes about a second.

## The HTML report

`--html` writes `~/.localalibi/dashboard.html`: one self-contained file (styles, script and icons inline, no network), with search, a language filter and sorting. Each project expands to its full profile with every piece of evidence. Paths under your home folder are shown as `~/…`, so the file is safe to share.

[Open the example report](https://deltaxmodules.github.io/LocalAlibiScan/example/) — Express, Flask, httpx, Vite, the FastAPI full-stack template and others.
