# O gravador do vídeo de demonstração: VHS + Python para o LocalAlibiScan (ver docs/video/PLANO.md).
FROM ghcr.io/charmbracelet/vhs:latest
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends \
        zsh git socat curl python3 python3-venv \
    && rm -rf /var/lib/apt/lists/*
# UTF-8, ou o zsh mostra ✓ ≈ ⚠ ✗ e acentos como bytes.
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
COPY entrypoint.sh /usr/local/bin/demo-entrypoint
ENTRYPOINT ["/usr/local/bin/demo-entrypoint"]
