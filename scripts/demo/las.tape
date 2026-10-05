# O vídeo de demonstração do manual — ver docs/video/PLANO.md. Correr: scripts/demo-video.sh
Output site/public/video/localalibiscan-demo.mp4

Set Shell zsh
Set Width 1440
Set Height 900
Set FontSize 17
Set Padding 28
Set Theme "Catppuccin Mocha"
Set TypingSpeed 40ms
Set WaitTimeout 180s
Set WaitPattern /projects \$$/

# O VHS arranca o zsh sem ler o .zshrc: carrega-o (prompt, legendas), escondido.
Hide
Type "source ~/.zshrc && clear" Enter
Sleep 1s
Type "scene 'LocalAlibiScan — every claim has an alibi' 'What every project on your disk is, how it is doing and what changed. Proven with file and line.'" Enter
Show
Sleep 4.5s

# 1. O painel
Hide
Type "scene '1. Every project in a folder, at a glance' 'Stack, database, external services, last change and alerts. Read-only: nothing is modified.'" Enter
Show
Sleep 2s
Type "las dashboard ~/projects" Sleep 500ms Enter
Wait
Sleep 7s

# 2. Afirmações com prova
Hide
Type "scene '2. Every claim has an alibi' '✓ confirmed by dependency and code · ≈ inferred · ⚠ contradiction · ? unknown — never invented.'" Enter
Show
Sleep 2s
Type "las scan notes-api --only db,framework,routes --evidence" Sleep 500ms Enter
Wait
Sleep 7s

# 3. Documentação que mente
Hide
Type "scene '3. Documentation that lies' 'The README says PostgreSQL; the code uses SQLite. Proof from both sides — and the README is never edited.'" Enter
Show
Sleep 2s
Type "las scan notes-api --only docs-vs-code --evidence" Sleep 500ms Enter
Wait
Sleep 8s

# 4. O que mudou
Hide
Type "scene '4. What changed, in architecture terms' 'Someone adds an OpenAI summary service and a DELETE route to notes-api…'" Enter
Show
Sleep 2s
Type "cp -r ~/staged/notes-api/. notes-api/" Sleep 400ms Enter
Wait
Sleep 1s
Type "las refresh notes-api" Sleep 500ms Enter
Wait
Sleep 8s

# 5. Perguntas
Hide
Type "scene '5. Ask: evidence first' 'Deterministic search; a local model (Ollama) answers only from what was found, citing file:line.'" Enter
Show
Sleep 2s
Type `las ask full-stack-fastapi-template "Where is authentication done?" --brief` Sleep 500ms Enter
Wait
Sleep 9s

# 6. É sequer um projeto?
Hide
Type "scene '6. Is it even a project?' 'Folders of photos, subfolders of a project, loose scripts — each gets an honest verdict.'" Enter
Show
Sleep 2s
Type "las check holiday-photos" Sleep 400ms Enter
Wait
Sleep 3s
Type "las check notes-api/src" Sleep 400ms Enter
Wait
Sleep 4s

# Cartão final
Hide
Type "scene 'Local · read-only · open source' 'pipx install git+https://github.com/deltaxmodules/LocalAlibiScan'" Enter
Type "print -P '  %F{250}Manual: https://deltaxmodules.github.io/LocalAlibiScan/%f'" Enter
Show
Sleep 6s
