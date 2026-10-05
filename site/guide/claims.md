# Claims: statuses and evidence

Everything LocalAlibiScan shows is a **claim**. A claim has an id, a status and — unless it is unknown — evidence: the file, the line and the line's text.

```json
{
  "id": "db.sqlite",
  "category": "database",
  "label": "Base de dados",
  "value": "SQLite",
  "status": "confirmed",
  "evidence": [
    {"file": "package.json", "line": 13, "snippet": "\"better-sqlite3\": \"^9.4.0\"", "kind": "dependency"},
    {"file": "src/db/database.ts", "line": 3, "snippet": "export const db = new Database('app.db');", "kind": "code"}
  ],
  "source": "detector:database"
}
```

## The four statuses

<div class="status-table">

| Status | Symbol | Meaning |
|---|---|---|
| `confirmed` | ✓ | Proven by strong evidence: a dependency **and** its use in the code, or explicit code |
| `inferred` | ≈ | A weak signal: only a declared dependency, only a config hint, or text written by the AI from facts |
| `contradiction` | ⚠ | Two sources disagree — typically the README and the code |
| `unknown` | ? | Could not be determined. LocalAlibiScan shows `?` rather than guess |

</div>

## The promotion rule

| What was found | Status |
|---|---|
| Dependency declared, never imported or used | ≈ inferred — *"declared in the manifest, no use found in the code"* |
| Dependency declared **and** imported / used | ✓ confirmed |
| Used in the code without a declared dependency | ✓ confirmed, with a note |
| Only an environment variable (`.env.example`) or a config file | ≈ inferred — *"only configuration hints"* |

So a `redis` line in `requirements.txt` that nothing imports shows up as **≈ Redis**, not as a database the project uses.

## Kinds of evidence

| Kind | Example |
|---|---|
| `dependency` | `package.json:13  "better-sqlite3": "^9.4.0"` |
| `code` | `src/db/database.ts:3  new Database('app.db')` |
| `config` | `.env.example:1  OPENAI_API_KEY=` · `docker-compose.yml:4  image: postgres:16` |
| `manifest`, `file`, `count`, `git`, `doc` | the manifest itself, a file's existence, a file count, the `.git` folder, a README line |

What does **not** count as evidence: code in tests, examples, playgrounds, templates and docs folders (a SQLite test database doesn't mean the product uses SQLite), and a bare mention such as the string `"postgres://"` — only a full URL or connection string proves use.

## Where claims are stored

Each analysed project gets a `.localalibi/` folder (it contains a `.gitignore` with `*`, so git never sees it):

| File | What |
|---|---|
| `project.json` | the current profile: every claim, plus the cache fingerprint |
| `evidence.db` | SQLite: claims and evidence of the last 20 analyses |
| `history.db` | SQLite: snapshots (claims + file hashes) for [`las refresh`](./refresh) |
| `overview.md` | written by [`las explain`](./explain) |
