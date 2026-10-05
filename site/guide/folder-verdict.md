# Is it even a project?

Before analysing anything, LocalAlibiScan decides what kind of folder it was given. `las check` shows only that verdict and its evidence:

```bash
las check ~/Downloads
```

| Verdict | Symbol | When | What happens |
|---|---|---|---|
| project | ✓ | `.git` or a known manifest in the folder itself | analysed |
| folder of projects | ▦ | not a project, but 2+ subfolders (up to 2 levels down) are | lists them and suggests `las dashboard` |
| subfolder of a project | ↑ | not a project, but a parent (up to 5 levels up, never above your home folder) is | shows the root and suggests `las scan <root>` |
| probable project | ≈ | no `.git` nor manifest, but 3+ code files or notebooks | analysed, with a warning at the top |
| not a project | ✗ | none of the above | stops, showing the manifest count, `.git` and the share of code files |

Known manifests: `package.json`, `requirements.txt`, `pyproject.toml`, `go.mod`, `Cargo.toml`, `composer.json`, plus `setup.py`, `Pipfile`, `Gemfile`, `pom.xml`, `build.gradle`, `Package.swift`, `pubspec.yaml`, `mix.exs`, `deno.json`.

```text
✗ não é um projeto de software  ~/holiday-photos
  └ .  0 manifestos conhecidos
  └ .  sem pasta .git
  └ .  0 de 6 ficheiros (0%) são código ou notebooks
```

`las scan` refuses the last three verdicts (exit code 2); add `--force` to analyse anyway — the profile then says *"análise forçada"* at the top.

A folder of loose scripts (no git, no manifest) is a **probable project**: it is analysed, its type is *"≈ Scripts Python"*, and the dashboard marks it with ≈.

The thresholds (3 files, 2 subprojects, 5 levels up, 2 levels down) live in `config.py`; the dashboard depth can be changed in the [configuration](../reference/configuration).
