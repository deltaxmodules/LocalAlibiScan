---
layout: home

hero:
  name: LocalAlibiScan
  text: Every claim has an alibi.
  tagline: What every project on your disk is, how it is doing and what changed — and the file and line that proves each statement. Local, read-only, no account.
  image:
    light: /brand/icon.png
    dark: /brand/icon-dark.png
    alt: LocalAlibiScan
  actions:
    - theme: brand
      text: Install and first dashboard
      link: /guide/get-started
    - theme: alt
      text: How claims work
      link: /guide/claims
    - theme: alt
      text: Example report
      link: https://deltaxmodules.github.io/LocalAlibiScan/example/

features:
  - title: Facts with proof
    details: Code extracts the facts; an optional local model only writes prose about them. Every line shown is a claim with a status and its evidence.
    link: /guide/claims
  - title: The whole disk, not one repo
    details: One dashboard for every project in a folder — stack, database, external services, last change, alerts. Loose script folders too.
    link: /guide/dashboard
  - title: Documentation that lies
    details: "The README says PostgreSQL, the code uses SQLite: ⚠ with README.md:8 and src/db/database.ts:1. It never edits anything."
    link: /guide/docs-vs-code
  - title: Changes in architecture language
    details: "“+ OpenAI service”, “+ New route DELETE /notes/:id”, “⚠ README doesn't mention OpenAI yet” — not “+42 lines”."
    link: /guide/refresh
  - title: Works without an LLM
    details: Everything essential is deterministic (manifests, tree-sitter, rules). Ollama on localhost is an extra, and every AI sentence must cite a fact.
    link: /guide/explain
  - title: Read-only by construction
    details: It never runs your code, never modifies your files and never goes online. The only writes go to a .localalibi/ folder that ignores itself in git.
    link: /guide/privacy
---

## See it in 90 seconds

<video controls muted playsinline preload="none" poster="/video/localalibiscan-demo.jpg" src="/video/localalibiscan-demo.mp4" style="width:100%;border-radius:8px" aria-label="LocalAlibiScan in a terminal: the dashboard of a projects folder, a scan with file and line evidence, a README that says PostgreSQL while the code uses SQLite, a refresh showing a new OpenAI service and route, a question answered by a local model from cited evidence, and folder verdicts"></video>

A real terminal, real open-source projects and a real local model (`qwen2.5-coder:7b` on Ollama): the dashboard, a scan with evidence, a README that lies, what changed after a commit, a question answered from cited code, and honest folder verdicts. No sound; a caption opens each scene. [How the video is made](https://github.com/deltaxmodules/LocalAlibiScan/blob/main/docs/video/PLANO.md).

## Who is it for?

Anyone with more projects than memory: freelancers with a folder per client, students with years of coursework, teams inheriting a repository, or you, six months from now. Point it at a folder:

```bash
$ las dashboard ~/code
$ las scan ~/code/notes-api --only db,docs-vs-code --evidence
$ las refresh ~/code/notes-api
$ las ask ~/code/shop "Where is authentication done?"
```

::: info English or Portuguese
The interface is in English by default. For Portuguese: `las --lang-ui pt …`, `LOCALALIBI_LANG=pt`, or `language = "pt"` in the [configuration](./reference/configuration). The facts (claims, statuses, evidence) are the same in every language.
:::
