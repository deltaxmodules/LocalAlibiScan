# What changed

```bash
las refresh ~/code/notes-api     # analyse again and compare with the previous analysis
las history ~/code/notes-api     # one line per previous analysis
```

Every real analysis (not one served from cache) saves a snapshot in `.localalibi/history.db`: date, git `HEAD` if any, every claim, and every file with its hash. `las refresh` analyses again and translates the difference into architecture language:

```text
New
  + Service: OpenAI  ← src/services/summary.ts:1
  + New route DELETE /notes/:id  ← src/routes/notes.ts:16

Changed
  ~ Routes: 1 file changed  ← src/routes/notes.ts
  ~ Service OpenAI: 1 new file  ← src/services/summary.ts

Alerts
  ⚠ README does not mention OpenAI yet  ← src/services/summary.ts:1
```

| Sign | Meaning |
|---|---|
| `+` | new services, databases, ORMs, frameworks, routes and dependencies |
| `-` | the same, removed — and important files that were deleted |
| `~` | a status changed (*SQLite: ✓ confirmado → ≈ inferido*), and changed files grouped by the component they belong to (*"Base de dados SQLite: 2 ficheiros alterados"*), or by folder |
| `⚠` | new contradictions, and new services/databases the README doesn't mention yet |

It works **without git**: changes are detected from file hashes. In a git repository the `HEAD` is recorded too.

```text
┃ # ┃ Date             ┃ HEAD     ┃ Files ┃ Changes        ┃
│ 1 │ 2026-10-05 17:11 │ 3f2a9c1e │     7 │ first analysis │
│ 2 │ 2026-10-05 17:40 │ 9b17d04a │     8 │ +2 ~2 ⚠1       │
```

The dashboard's **Mudou** column shows the same summary for each project.
