#!/usr/bin/env bash
# Gera o vídeo de demonstração (site/public/video/localalibiscan-demo.mp4 + capa .jpg)
# e o GIF do README (site/public/img/localalibiscan-demo.gif) — ver docs/video/PLANO.md.
# Precisa de Docker e do Ollama a correr neste computador com o modelo da demo:
#   scripts/demo-video.sh [video|gif]      (ambos por omissão)
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
model="${DEMO_MODEL:-qwen2.5-coder:7b}"
curl -fs http://localhost:11434/api/tags | grep -q "\"${model}\"" \
    || { echo "O Ollama tem de estar a correr aqui com ${model} (ollama pull ${model})" >&2; exit 1; }

# Projetos open source da demo (clonados uma vez; .demo-cache está no .gitignore).
cache="$repo/.demo-cache"
mkdir -p "$cache"
for r in expressjs/express pallets/flask encode/httpx fastapi/full-stack-fastapi-template \
         gothinkster/node-express-realworld-example-app openai/openai-quickstart-node; do
    [[ -d "$cache/${r#*/}" ]] || git clone -q --depth 1 "https://github.com/$r.git" "$cache/${r#*/}"
done

docker build -q -t localalibiscan-demo "$repo/scripts/demo" >/dev/null
mkdir -p "$repo/site/public/video" "$repo/site/public/img"
record() {
    docker run --rm --add-host=host.docker.internal:host-gateway -e DEMO_MODEL="$model" \
        -v "$repo":/repo -v "$cache":/cache:ro localalibiscan-demo "scripts/demo/$1"
}
what="${1:-all}"
if [[ "$what" == all || "$what" == video ]]; then
    record las.tape
    # Capa: um fotograma da cena da documentação que mente.
    ffmpeg -loglevel error -y -ss "${COVER_AT:-34}" -i "$repo/site/public/video/localalibiscan-demo.mp4" \
        -frames:v 1 -q:v 3 "$repo/site/public/video/localalibiscan-demo.jpg"
fi
[[ "$what" == all || "$what" == gif ]] && record readme.tape
ls -lh "$repo"/site/public/video/localalibiscan-demo.* "$repo"/site/public/img/localalibiscan-demo.gif 2>/dev/null
