# Guarantees and privacy

These rules hold for every command and are enforced by the code, not only by convention.

## Read-only

- A single module (`fs.py`) writes files. It only accepts paths inside `<project>/.localalibi/` and `~/.localalibi/`; anything else raises an exception — including `..` tricks and symbolic links pointing elsewhere. Tests hash every fixture before and after each command.
- `.localalibi/` contains a `.gitignore` with `*`, so it never shows up in `git status`.

## Never runs your code

No scripts, no tests, no `npm install`, no imports of your modules. Code is parsed with tree-sitter. Git is only called with read commands (`rev-parse`, `log`, `status`) and `GIT_OPTIONAL_LOCKS=0`, so it doesn't even write the index.

## No network

The only network call the tool can make is to an Ollama server, and the client refuses any address that isn't `localhost`, `127.0.0.1` or `::1`. The HTML report loads nothing from the internet.

## What the local model sees

- [`las explain`](./explain): claims only (ids, labels, values, statuses) — no code.
- [`las ask`](./ask): the excerpts found by the deterministic search (a few lines around each hit) — no whole files.

## Large and binary files

Files over 1 MB (configurable) and binary files are listed but never read.
