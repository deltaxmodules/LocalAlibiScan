# Documentation that lies

Every `las scan` compares what the documentation says with what the code proves. It **never edits** the documentation.

```text
Documentação vs código
  ⚠ Documentação vs código: Documentação diz PostgreSQL, código usa SQLite
      Nenhum sinal de PostgreSQL no código (dependências, imports, configuração)
      └ README.md:8  - PostgreSQL for persistence
      └ README.md:17  Set `DATABASE_URL` to your PostgreSQL connection string before starting.
      └ src/db/database.ts:1  import Database from 'better-sqlite3';
      └ package.json:13  "better-sqlite3": "^9.4.0"
  ✓ Não documentado: SQLite
```

## Three kinds of findings

| Finding | Status | When |
|---|---|---|
| **Contradiction** | ⚠ | A README says X, the code confirms Y of the same kind, and X has **no signal at all** in the code |
| **Only in the documentation** | ≈ | The docs mention X and the code has no trace of it |
| **Not documented** | ✓ | The code confirms a database, framework or service the README never mentions |

"The same kind" means mutually exclusive technologies: the main database (SQLite, PostgreSQL, MySQL, MongoDB, DynamoDB), the Python web framework (FastAPI, Flask, Django), the JavaScript server (Express, Fastify, Koa, Hono) and the UI library (React, Vue, Svelte, Angular). Services never contradict each other (a project can use OpenAI *and* Anthropic), and Redis is not a rival database (it's usually a cache).

## What is read

- `README*` files (root and up to two levels down), other Markdown files at the root, and everything under `docs/`.
- **Not** read: hidden folders (`.claude/`, `.planning/`…), agent instruction files (`CLAUDE.md`, `AGENTS.md`…), `CHANGELOG`, `LICENSE`, `CONTRIBUTING`, and test or example folders.
- Only **README** files can prove a contradiction; other files can only produce ≈ findings.

## Sentences that don't count

The extractor is deterministic — it looks for technology names line by line — so it is careful with sentences that mention a technology without claiming the project uses it:

- **Migrations**: *"We moved from MongoDB to SQLite"*, *"Migrámos de PostgreSQL para SQLite"*, *"legacy"*, *"previously"*.
- **Negations**: *"no Redis"*, *"sem PostgreSQL"*, *"instead of MySQL"*.
- **Comparisons**: a line that also names the rival the code uses, such as a table `| SQLite | PostgreSQL |`.
- **Common words**: *Express*, *Click*, *React* only count with that exact capitalisation and not at the start of an ordinary sentence ("Click the button") — they do count in lists and headings, where stacks are usually described.

These become ≈ *"frase ambígua"* at most, never ⚠. More in [Known limitations](./limitations).
