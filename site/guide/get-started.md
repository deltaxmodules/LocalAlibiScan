# Install and first dashboard

## Install

LocalAlibiScan needs **Python 3.11+** and runs on macOS, Linux and Windows.

```bash
pipx install git+https://github.com/deltaxmodules/LocalAlibiScan
```

(Once it is on PyPI: `pipx install localalibiscan`.) This installs two equivalent commands, `localalibiscan` and the shortcut `las`.

```bash
las --version
```

Nothing else is required. A local model ([Ollama](https://ollama.com)) is optional and only used by [`las explain`](./explain) and [`las ask`](./ask).

## Your first dashboard

Point it at the folder where your projects live:

```bash
las dashboard ~/code
```

It walks down (two levels by default), finds every project — anything with `.git` or a known manifest, plus folders of loose scripts — and shows one line per project: type, main stack, database, external services, last change, what changed since last time, and alerts.

The first run analyses everything; later runs reuse the cached profile of every project that did not change, so they take a fraction of the time.

Want a report you can open in a browser, keep, or send?

```bash
las dashboard ~/code --html
```

It writes a single self-contained file to `~/.localalibi/dashboard.html` — no server, no internet, every project expandable to its full profile with evidence. [See an example built from open-source projects](https://deltaxmodules.github.io/LocalAlibiScan/example/).

## One project in depth

```bash
las scan ~/code/notes-api
```

Every line is a [claim](./claims): a symbol (✓ ≈ ⚠ ?), a statement, and below it the first piece of evidence — `file:line` and the line itself. Add `--evidence` to see all of it, or `--only db,framework,routes` to keep the output short.

## What next

- [What changed since the last scan](./refresh): `las refresh`
- [Does the README tell the truth?](./docs-vs-code)
- [Every command](../reference/commands)
