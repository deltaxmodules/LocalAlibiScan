# Configuration

LocalAlibiScan works without any configuration. To change the defaults, create `~/.localalibi/config.toml`:

```bash
las config --init     # writes the file below (never overwrites)
las config            # shows the configuration in use and where it comes from
```

```toml
[ui]
# Interface language: "en" or "pt" (also LOCALALIBI_LANG or las --lang-ui).
language = "en"

[scan]
# Folders to skip in addition to the fixed ones (node_modules, .venv, venv, dist,
# build, .git, __pycache__, .next, target, site-packages, any virtualenv) and
# each project's .gitignore.
ignore = []
# Files larger than this (bytes) are listed but not read.
max_file_size = 1048576

[dashboard]
# How many levels to walk down looking for projects.
depth = 2

[ollama]
# Only localhost is accepted. AI drafting is optional.
url = "http://localhost:11434"
model = "qwen2.5-coder:7b"
timeout = 180
```

## Precedence

Defaults < `config.toml` < environment variables < command-line options:

| Variable | Overrides |
|---|---|
| `LOCALALIBI_LANG` | `[ui] language` (`las --lang-ui` overrides both) |
| `LOCALALIBI_OLLAMA_MODEL` | `[ollama] model` |
| `LOCALALIBI_OLLAMA_URL` | `[ollama] url` (must still be localhost) |
| `LOCALALIBI_CONFIG` | path of the configuration file itself |

An invalid file stops every command with a message naming the file and the problem, instead of being silently ignored.

## Choosing a model

Any model you have in Ollama works (`ollama list`). Small coding models such as `qwen2.5-coder:7b` are a good fit: the model never sees your code in [`las explain`](../guide/explain), only short excerpts in [`las ask`](../guide/ask), and every sentence it writes is checked by the validator.

```bash
ollama pull qwen2.5-coder:7b
las explain . --model qwen3:8b     # one-off
```
