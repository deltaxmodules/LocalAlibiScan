#!/bin/bash
# Prepara uma máquina de demonstração limpa dentro do contentor e corre o VHS.
# /repo é este repositório; /cache tem os projetos open source clonados pelo
# scripts/demo-video.sh. Nada do computador de quem grava aparece no vídeo.
set -euo pipefail

# O Ollama do anfitrião, visto como localhost (a regra da ferramenta: só localhost).
socat TCP-LISTEN:11434,fork,reuseaddr "TCP:${OLLAMA_HOST_ADDR:-host.docker.internal}:11434" &
for _ in $(seq 50); do curl -fs http://localhost:11434/api/tags >/dev/null && break; sleep 0.2; done

# O LocalAlibiScan do repositório, instalado como um utilizador o faria.
cp -r /repo /tmp/src && rm -rf /tmp/src/.venv /tmp/src/.demo-cache /tmp/src/dist
python3 -m venv /opt/las >/dev/null
/opt/las/bin/pip install -q /tmp/src
mkdir -p ~/.localalibi
printf '[ollama]\nmodel = "%s"\n' "${DEMO_MODEL:-qwen2.5-coder:7b}" > ~/.localalibi/config.toml

# A pasta de projetos da demo: projetos open source conhecidos + exemplos do repositório.
mkdir -p ~/projects
for p in /cache/*; do cp -r "$p" ~/projects/; done
cp -r /repo/tests/fixtures/node_sqlite_lying_readme ~/projects/notes-api
cp -r /repo/tests/fixtures/loose_scripts ~/projects/data-scripts
cp -r /repo/tests/fixtures/not_a_project ~/projects/holiday-photos
find ~/projects -name .localalibi -prune -exec rm -rf {} +
# notes-api é um repositório com história (para o `las refresh`).
(cd ~/projects/notes-api && git init -q && git add -A \
    && git -c user.name=demo -c user.email=demo@example.com commit -q -m "notes api")

# A mudança que a cena 4 aplica: um serviço OpenAI e uma rota nova.
mkdir -p ~/staged/notes-api/src/services ~/staged/notes-api/src/routes
cat > ~/staged/notes-api/src/services/summary.ts <<'TS'
import OpenAI from 'openai';

const client = new OpenAI();

export async function summarize(text: string) {
  const res = await client.chat.completions.create({
    model: 'gpt-4o-mini',
    messages: [{ role: 'user', content: `Summarize: ${text}` }],
  });
  return res.choices[0].message.content;
}
TS
cp ~/projects/notes-api/src/routes/notes.ts ~/staged/notes-api/src/routes/notes.ts
cat >> ~/staged/notes-api/src/routes/notes.ts <<'TS'

notesRouter.delete('/:id', (req, res) => {
  db.prepare('DELETE FROM notes WHERE id = ?').run(req.params.id);
  res.status(204).end();
});
TS

# Um prompt limpo e a legenda que abre cada cena.
cat > ~/.zshrc <<'ZSH'
export PATH="/opt/las/bin:$PATH"
PROMPT='%F{39}~/projects%f %F{245}$%f '
setopt interactive_comments
scene() {
    clear
    print -P "%B%F{214}▌ $1%f%b"
    [[ -n "${2:-}" ]] && print -P "  %F{250}$2%f"
    print
}
cd ~/projects
ZSH

# Primeira análise (a base de comparação do refresh) e o painel em cache, como
# num computador onde a ferramenta já foi usada.
/opt/las/bin/las scan ~/projects/notes-api >/dev/null
/opt/las/bin/las dashboard ~/projects >/dev/null || true
/opt/las/bin/las scan ~/projects/full-stack-fastapi-template >/dev/null

# Carrega o modelo já, para a primeira resposta não ser mais lenta que as outras.
curl -fs http://localhost:11434/api/generate \
    -d "{\"model\": \"${DEMO_MODEL:-qwen2.5-coder:7b}\", \"keep_alive\": \"30m\"}" >/dev/null || true

cd /repo
exec vhs "$@"
