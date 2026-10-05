<!-- Gerado por scripts/gen_reference.py a partir do código. Não editar à mão. -->

# Commands

Every command is available as `las` and as `localalibiscan`. `FOLDER` defaults to the current folder.

| Command | What it does |
|---|---|
| [`las files`](#las-files) | List the files that would be analysed, with extension and size (respects `.gitignore`; large and binary files are marked). |
| [`las check`](#las-check) | Show only the [folder verdict](../guide/folder-verdict) and its evidence. |
| [`las scan`](#las-scan) | Analyse a project and show its profile: every claim with its status and evidence. |
| [`las dashboard`](#las-dashboard) | [Dashboard](../guide/dashboard) of every project under a folder; `--html` writes `~/.localalibi/dashboard.html`. |
| [`las refresh`](#las-refresh) | Analyse again and show [what changed](../guide/refresh) since the previous analysis. |
| [`las history`](#las-history) | List previous analyses with a one-line summary each. |
| [`las explain`](#las-explain) | [Explain this project](../guide/explain): fixed questions answered with facts (and optional local AI). |
| [`las ask`](#las-ask) | [Ask a question](../guide/ask): deterministic search first; the optional local model answers only from the evidence. |
| [`las config`](#las-config) | Show the configuration in use; `--init` creates `~/.localalibi/config.toml`. |

## Global options

| Option | |
|---|---|
| `--version` | Show the version and exit. |
| `--lang-ui` | Interface language: `en` (default) or `pt`. Goes before the command: `las --lang-ui pt scan .`. Same as `LOCALALIBI_LANG` or `[ui] language` in the [configuration](configuration). |

## las files

```bash
las files FOLDER [OPTIONS]
```

List the files that would be analysed, with extension and size (respects `.gitignore`; large and binary files are marked).

| Option | |
|---|---|
| `--max-size` | Maximum size in bytes for a file to be read. |

## las check

```bash
las check FOLDER [OPTIONS]
```

Show only the [folder verdict](../guide/folder-verdict) and its evidence. No analysis.

## las scan

```bash
las scan FOLDER [OPTIONS]
```

Analyse a project and show its profile: every claim with its status and evidence. Writes `.localalibi/`.

| Option | |
|---|---|
| `--force` | Analyse even if the folder doesn't look like a project. |
| `--evidence` | Show every piece of evidence of each claim (default: the first one). |
| `--only` | Only these sections, comma-separated, e.g. `db,framework,routes,docs-vs-code`. |

## las dashboard

```bash
las dashboard FOLDER [OPTIONS]
```

[Dashboard](../guide/dashboard) of every project under a folder; `--html` writes `~/.localalibi/dashboard.html`.

| Option | |
|---|---|
| `--html` | Also write the self-contained HTML report to `~/.localalibi/dashboard.html`. |
| `--lang` | Only projects that contain this language (e.g. `python`). |
| `--depth` | How many levels to walk down looking for projects (default 2). |
| `--no-cache` | Re-analyse every project. |

## las refresh

```bash
las refresh FOLDER [OPTIONS]
```

Analyse again and show [what changed](../guide/refresh) since the previous analysis.

| Option | |
|---|---|
| `--force` | Analyse even if the folder doesn't look like a project. |

## las history

```bash
las history FOLDER [OPTIONS]
```

List previous analyses with a one-line summary each.

## las explain

```bash
las explain FOLDER [OPTIONS]
```

[Explain this project](../guide/explain): fixed questions answered with facts (and optional local AI). Writes `.localalibi/overview.md`.

| Option | |
|---|---|
| `--no-llm` | Don't use Ollama: facts / evidence only. |
| `--model` | Ollama model to use (default from the configuration). |

## las ask

```bash
las ask FOLDER QUESTION [OPTIONS]
```

[Ask a question](../guide/ask): deterministic search first; the optional local model answers only from the evidence.

| Option | |
|---|---|
| `--no-llm` | Don't use Ollama: facts / evidence only. |
| `--model` | Ollama model to use (default from the configuration). |
| `--brief` | One line per piece of evidence, without code excerpts. |

## las config

```bash
las config  [OPTIONS]
```

Show the configuration in use; `--init` creates `~/.localalibi/config.toml`.

| Option | |
|---|---|
| `--init` | Create `~/.localalibi/config.toml` with the defaults (never overwrites). |

## Exit codes

| Code | Meaning |
|---|---|
| 0 | OK |
| 1 | `las ask` found no evidence · `las config --init` found an existing file |
| 2 | Not analysed: the folder is not a project (use `--force`), no projects found, or no history |
