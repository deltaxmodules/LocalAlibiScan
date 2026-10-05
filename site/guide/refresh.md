# What changed

```bash
las refresh ~/code/notes-api     # analyse again and compare with the previous analysis
las history ~/code/notes-api     # one line per previous analysis
```

Every real analysis (not one served from cache) saves a snapshot in `.localalibi/history.db`: date, git `HEAD` if any, every claim, and every file with its hash. `las refresh` analyses again and translates the difference into architecture language:

```text
Novo
  + Serviço OpenAI  ← src/services/summary.ts:1
  + Nova rota DELETE /notes/:id  ← src/routes/notes.ts:16

Alterado
  ~ Rotas: 1 ficheiro alterado  ← src/routes/notes.ts
  ~ Serviço OpenAI: 1 ficheiro novo  ← src/services/summary.ts

Alertas
  ⚠ README ainda não menciona OpenAI  ← src/services/summary.ts:1
```

| Sign | Meaning |
|---|---|
| `+` | new services, databases, ORMs, frameworks, routes and dependencies |
| `-` | the same, removed — and important files that were deleted |
| `~` | a status changed (*SQLite: ✓ confirmado → ≈ inferido*), and changed files grouped by the component they belong to (*"Base de dados SQLite: 2 ficheiros alterados"*), or by folder |
| `⚠` | new contradictions, and new services/databases the README doesn't mention yet |

It works **without git**: changes are detected from file hashes. In a git repository the `HEAD` is recorded too.

```text
┃ # ┃ Data             ┃ HEAD     ┃ Ficheiros ┃ Mudanças         ┃
│ 1 │ 2026-10-05 17:11 │ 3f2a9c1e │         7 │ primeira análise │
│ 2 │ 2026-10-05 17:40 │ 9b17d04a │         8 │ +2 ~2 ⚠1         │
```

The dashboard's **Mudou** column shows the same summary for each project.
