# One project in depth

```bash
las scan ~/code/shop                                # profile, first evidence of each claim
las scan ~/code/shop --evidence                     # every piece of evidence
las scan ~/code/shop --only db,framework,routes     # only some sections
```

## What it finds

**From manifests and structure**

- **Languages** by file count, and the main one.
- **Manifests** — `package.json`, `requirements.txt`, `pyproject.toml` (PEP 621 and Poetry), `go.mod`, `Cargo.toml`, `composer.json` — with every dependency and script **and the line it is declared on**.
- **Project type** and, for monorepos, its **components** (`frontend: Node.js/JavaScript`, `backend: Python`).
- **Entry points** — `main`/`bin`/`start` in `package.json`, `[project.scripts]`, `main.py`/`app.py`/`manage.py`, `if __name__ == "__main__"`, `func main()`, `fn main()`.
- **Main folders**, by amount of code.
- **README and docs**.

**From the code** (parsed with tree-sitter: Python, JavaScript, TypeScript, TSX — never executed)

- **Databases and ORMs** — SQLite, PostgreSQL, MySQL, MongoDB, Redis, Supabase, DynamoDB, Prisma, SQLAlchemy, Drizzle… (dependency + import/usage, connection strings, `schema.prisma` providers, `docker-compose` images).
- **Frameworks** — React, Next.js, Vue, Svelte, Express, Fastify, NestJS, FastAPI, Flask, Django, Streamlit…
- **External services** — OpenAI, Anthropic, Gemini, Ollama, Stripe, GitHub, AWS, Firebase, Sentry, Twilio… (imports, known API hosts, variables in `.env.example`).
- **HTTP routes** with file and line — FastAPI/Flask decorators (with router prefixes), Express/Fastify/Koa/Hono calls (with `app.use('/prefix', router)` resolved across files), Next.js App Router `route.ts`/`page.tsx` and `pages/api`.
- **The 10 most important files**, each with a reason: *"Ponto de entrada"*, *"Acesso à base de dados (SQLite)"*, *"Define 6 rotas"*, *"Importado por 4 ficheiros"*.

The full list is in [Detected technologies](../reference/technologies).

## Sections for `--only`

`project`, `language`, `entry` (`entry_point`), `structure`, `db` (`database`), `orm`, `framework`, `service`, `routes`, `docs-vs-code`, `files` (most important), `docs`, `manifest`, `dependencies`, `scripts`. Separate them with commas.

## What is skipped

`.gitignore` (including nested ones and `!` exceptions) is respected, and these are always skipped: `node_modules`, `.venv`, `venv`, `dist`, `build`, `.git`, `__pycache__`, `.next`, `target`, `site-packages` and any virtualenv. Files over 1 MB and binary files are listed but never read. See them with:

```bash
las files ~/code/shop
```

Code in tests, examples, playgrounds, templates and docs folders is read (`las ask` can find it) but never counts as evidence of what the product uses.

## Speed

A project of ~500 files takes well under a second; a medium real project typically 0.01–0.3 s.
