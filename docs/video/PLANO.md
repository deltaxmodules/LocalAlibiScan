# Vídeo de demonstração — plano e guião

**Estado:** decisões tomadas pelo assistente com a autorização do PO (2026-10-05: «faça como entender»). Gerado com `scripts/demo-video.sh`.

Modelo: o vídeo do TuxAide — gerado por script, sem voz, com legendas, refeito com um comando a cada versão.

## Decisões

| # | Pergunta | Decisão |
|---|---|---|
| 1 | Ferramenta | **[VHS](https://github.com/charmbracelet/vhs)** num contentor Docker (imagem oficial + zsh, git, socat, Python). Grava um terminal real a partir de ficheiros `.tape` no repositório (`scripts/demo/`). |
| 2 | Um vídeo ou vários? | **Um vídeo de ~1min30** com 6 cenas, para o manual; **um GIF de 14 s** para o README (painel → documentação que mente). |
| 3 | Narração | **Sem voz, sem música.** Cada cena abre com uma legenda no próprio terminal, em inglês como o manual. A saída da ferramenta é a real (em português). |
| 4 | Projetos mostrados | **Não** a pasta "Projectos 2026" do PO: o vídeo é público e essa pasta tem nomes de clientes e projetos. Em vez disso, projetos open source conhecidos (Express, Flask, httpx, full-stack-fastapi-template, node-express-realworld-example-app, openai-quickstart-node), clonados por `demo-video.sh` para `.demo-cache/`, e três fixtures do repositório com nomes de demo: `notes-api` (o README que mente), `data-scripts` (scripts soltos) e `holiday-photos` (não é projeto). |
| 5 | Modelo | **Real**: `qwen2.5-coder:7b` no Ollama de quem grava, visto de dentro do contentor como `localhost:11434` (um `socat`) — a regra da ferramenta só aceita localhost. As respostas do `las ask` vêm do modelo, por isso variam um pouco entre gravações; as cenas esperam pelo prompt (`Wait`), não por tempos fixos. |
| 6 | Ambiente | O LocalAlibiScan do repositório instalado num venv (`pip install`), `~/projects` com os projetos, uma primeira análise de `notes-api` (para o `refresh` ter com que comparar) e o painel já em cache, como num computador onde a ferramenta já foi usada. Nada privado aparece: o prompt mostra só `~/projects`. |
| 7 | Formato | Vídeo 1440×900 MP4 (H.264) com capa `.jpg` (fotograma da cena 3); GIF 1300×720. Ficheiros em `site/public/video/` e `site/public/img/`. |

## Guião (`scripts/demo/las.tape`)

| # | Legenda | O que acontece |
|---|---|---|
| 0 | **LocalAlibiScan — every claim has an alibi** | título |
| 1 | **1. Every project in a folder, at a glance** | `las dashboard ~/projects` — 8 projetos, tipo, stack, BD, serviços, alertas (⚠ em notes-api) |
| 2 | **2. Every claim has an alibi** | `las scan notes-api --only db,framework,routes --evidence` — SQLite com `package.json:13` e `src/db/database.ts:3`, rotas com linha |
| 3 | **3. Documentation that lies** | `las scan notes-api --only docs-vs-code --evidence` — ⚠ README diz PostgreSQL, código usa SQLite |
| 4 | **4. What changed, in architecture terms** | copia um serviço OpenAI e uma rota DELETE para notes-api → `las refresh notes-api` → `+ Serviço OpenAI`, `+ Nova rota`, `⚠ README ainda não menciona OpenAI` |
| 5 | **5. Ask: evidence first** | `las ask full-stack-fastapi-template "Where is authentication done?" --brief` — resposta do modelo citando `login.py` e `core/security.py` |
| 6 | **6. Is it even a project?** | `las check holiday-photos` (✗) e `las check notes-api/src` (↑ subpasta) |
| 7 | **Local · read-only · open source** + instalação e endereço do manual | cartão final |

## Ajustes ao preparar a gravação (2026-10-05)

- A primeira resposta de `las ask` à pergunta de autenticação citava ficheiros de testes primeiro e vinha em português, repetitiva («A autenticação é feita em…» ×3). Corrigido no produto: código de testes/exemplos passa para depois do código do produto, a resposta vem na língua da pergunta e o prompt pede o que acontece em cada sítio.
- A saída completa de `las scan` e de `las ask` não cabia no ecrã: o produto ganhou `las scan --only <secções>` e `las ask --brief`, úteis também fora do vídeo.

## Refazer

```bash
scripts/demo-video.sh          # vídeo + GIF (precisa de Docker e do Ollama com qwen2.5-coder:7b)
scripts/demo-video.sh gif      # só o GIF
```
