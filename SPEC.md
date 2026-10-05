# LocalAlibiScan — Especificação por fases

> **Every claim has an alibi.**
> Ferramenta local que diz o que cada projeto no teu computador é, como está e o que mudou, e prova cada afirmação com o ficheiro e a linha de onde a tirou.

Este documento serve de guia para construir o LocalAlibiScan com o Claude Code, **uma fase de cada vez**. Cada fase tem um objetivo, o que deve ser entregue, os critérios de verificação e o que fica fora dela. Só se avança para a fase seguinte quando todos os critérios da anterior estiverem cumpridos.

### Estado (2026-10-05)

| Fase | Estado | Etiqueta |
|---|---|---|
| 0 a 9 | Feitas | `fase-0` … `fase-9` |
| 10 | Feita | `fase-10` |

Publicado: PyPI `localalibiscan` 0.1.2 (MIT); a 0.2.0 traz a Fase 9. Feito para além do pedido nas fases: comando `las config`, manual em inglês (`site/`, VitePress, no GitHub Pages) com a referência gerada a partir do código, vídeo e GIF de demonstração (`scripts/demo-video.sh`), marca (logótipo e ícones) e CI em Linux/macOS/Windows.

---

## 1. Proposta de valor (o que nos distingue)

1. **Factos com prova.** O código extrai os factos; a LLM só os redige. Cada afirmação tem estado e evidência.
2. **O disco inteiro, não um repositório.** Um painel com todos os projetos de uma pasta.
3. **Deteção de documentação que mente.** README vs código, com prova, sem corrigir nada.
4. **Mudanças em linguagem de arquitetura.** "Apareceu um serviço OpenAI", não "+42 linhas".
5. **Funciona sem LLM.** Tudo o que é essencial é determinista. A LLM (Ollama) é um extra.

**Não competimos em:** chat genérico com o código e wikis bonitas.

---

## 2. Regras invariáveis (valem para todas as fases)

Estas regras devem ser copiadas para o `CLAUDE.md` do repositório.

- **Só leitura.** A ferramenta nunca modifica, apaga ou move ficheiros do projeto analisado.
- **Única escrita permitida:** dentro de `<projeto>/.localalibi/` (e na pasta de configuração do utilizador).
- **Nunca executa código do projeto analisado** (nem scripts, nem testes, nem `npm install`).
- **Sem rede**, exceto chamadas para o Ollama em `localhost` (a partir da Fase 6).
- **Nenhuma afirmação sem estado.** Tudo o que é mostrado ao utilizador é um `Claim` com estado e, sempre que possível, evidências.
- **A LLM nunca cria factos.** Só pode redigir texto a partir de `Claim`s existentes e tem de citar os seus identificadores.
- **Determinismo primeiro.** Se uma regra ou parser resolve, não se usa LLM.
- **Respeitar `.gitignore`** e ignorar sempre `node_modules`, `.venv`, `venv`, `dist`, `build`, `.git`, `__pycache__`, `.next`, `target`.
- **Ficheiros grandes ou binários** são registados mas não lidos (limite configurável, por omissão 1 MB).

---

## 3. Stack técnica

| Peça | Escolha |
|---|---|
| Linguagem | Python 3.11+ |
| CLI | Typer |
| Saída no terminal | Rich |
| Modelos de dados | Pydantic v2 |
| Armazenamento | SQLite (módulo `sqlite3`) + JSON/Markdown |
| Análise de código | tree-sitter (`tree-sitter-language-pack`) |
| Git | `git` via subprocess, só comandos de leitura (`log`, `status`, `rev-parse`) |
| LLM | Ollama em `localhost:11434` (opcional) |
| Testes | pytest |
| Distribuição | `pipx install localalibiscan` |

Comando principal: `localalibiscan`, com o atalho `las`.

---

## 4. Modelo central: `Claim`

Tudo gira à volta deste objeto. É definido na Fase 1 e nunca mais muda de forma incompatível.

```json
{
  "id": "db.engine",
  "category": "database",
  "label": "Base de dados",
  "value": "SQLite",
  "status": "confirmed",
  "evidence": [
    {"file": "package.json", "line": 14, "snippet": "\"better-sqlite3\": \"^9.4.0\"", "kind": "dependency"},
    {"file": "src/db/database.ts", "line": 3, "snippet": "new Database('app.db')", "kind": "code"}
  ],
  "source": "detector:database",
  "detected_at": "2026-10-05T15:20:00Z"
}
```

**Estados possíveis:**

| Estado | Símbolo | Significado |
|---|---|---|
| `confirmed` | ✓ | Provado por pelo menos uma evidência forte (dependência **e** uso no código, ou código explícito) |
| `inferred` | ≈ | Indício fraco (só dependência, só nome de ficheiro, ou texto gerado pela LLM a partir de factos) |
| `contradiction` | ⚠ | Duas fontes dizem coisas diferentes |
| `unknown` | ? | Não foi possível determinar |

**Tradução (Fase 9):** `Claim` tem ainda os campos opcionais `label_key`, `value_key`, `note_key` e `params`, e `Evidence` tem `snippet_key` e `params`, para o texto gerado pela ferramenta. Esse texto grava-se em inglês e traduz-se só na apresentação; os campos vazios não se gravam, por isso o JSON acima continua válido.

**Regra de promoção:** dependência declarada sozinha → `inferred`. Dependência + uso no código → `confirmed`. Uso no código sem dependência declarada → `confirmed` com nota.

---

## 5. Estrutura da pasta `.localalibi/`

```
.localalibi/
    project.json      # perfil atual (lista de Claims)
    overview.md       # resumo legível (Fase 6)
    evidence.db       # Claims e evidências, por análise
    history.db        # snapshots de análises anteriores (Fase 5)
    .gitignore        # contém "*" para não poluir o repositório
```

---

## 6. Projetos de teste (fixtures)

Criados na Fase 0 em `tests/fixtures/`. Todas as fases são verificadas contra eles.

| Fixture | Conteúdo | Para testar |
|---|---|---|
| `node_sqlite_lying_readme` | Node/TS, `better-sqlite3`, README diz "PostgreSQL" | Deteção de BD + contradição |
| `python_fastapi_openai` | FastAPI, `openai` em requirements e usado em `services/ai.py` | Framework, rotas, serviço externo |
| `python_dep_unused` | `redis` em requirements mas nunca importado | Estado `inferred` |
| `empty_project` | Só um README | Estados `unknown` |
| `monorepo_mixed` | `frontend/` React + `backend/` Python | Vários componentes |
| `projects_root/` | Pasta com 4 projetos dentro, 1 sem git | Painel multi-projeto + veredito "raiz" |
| `not_a_project` | Fotos, PDFs e documentos, nenhum código | Veredito "não é projeto" |
| `loose_scripts` | 3 ficheiros `.py` e um notebook, sem manifesto nem git | Veredito "provável projeto" |

A fixture `node_sqlite_lying_readme` serve também para testar o caso "subpasta" (apontar para `node_sqlite_lying_readme/src`).

---

## FASE 0 — Esqueleto

**Objetivo:** projeto instalável, CLI a responder, fixtures criadas, garantia de só leitura testada.

**Entregar:**
- `pyproject.toml` com entry points `localalibiscan` e `las`.
- Estrutura: `src/localalibiscan/{cli.py, config.py, fs.py, models.py}`, `tests/`.
- `fs.py`: única camada de acesso a ficheiros. Leitura livre; escrita só permitida dentro de `.localalibi/` (qualquer outra tentativa lança exceção).
- Percorrer a pasta respeitando `.gitignore` e as exclusões fixas.
- Comando `las files <pasta>` que lista os ficheiros que seriam analisados, com extensão e tamanho.
- `CLAUDE.md` com as regras da secção 2.
- Todas as fixtures da secção 6.

**Verificação:**
- [x] `pipx install -e .` funciona e `las --help` mostra os comandos.
- [x] `las files tests/fixtures/node_sqlite_lying_readme` não lista `node_modules`.
- [x] Teste que tenta escrever fora de `.localalibi/` através de `fs.py` falha com exceção.
- [x] `pytest` passa.

**Fora desta fase:** qualquer deteção, SQLite, tree-sitter.

---

## FASE 1 — Veredito da pasta, inventário determinista e modelo `Claim`

**Objetivo:** perceber primeiro que tipo de pasta foi recebida e, se for um projeto, criar o primeiro perfil baseado só em manifestos e estrutura.

**Entregar:**
- Modelos Pydantic `Claim` e `Evidence` (secção 4).
- **Detetor `project_kind` (corre sempre primeiro).** Classifica a pasta num de cinco vereditos, cada um com estado e evidências:

  | Veredito | Critério | Comportamento |
  |---|---|---|
  | `project` ✓ | `.git` ou manifesto conhecido na própria pasta | Continua a análise |
  | `root` | Não é projeto, mas contém 2 ou mais subpastas que são projetos | Não analisa; sugere `las dashboard <pasta>` e lista os projetos encontrados |
  | `subfolder` | Não é projeto, mas uma pasta acima tem `.git` ou manifesto | Não analisa; mostra a raiz encontrada e sugere `las scan <raiz>` |
  | `probable_project` ≈ | Sem `.git` nem manifesto, mas pelo menos 3 ficheiros de código ou notebooks | Continua a análise, com aviso no topo do perfil |
  | `not_a_project` ✗ | Nenhum dos anteriores | Para; mostra as evidências (n.º de manifestos, presença de `.git`, percentagem de ficheiros de código) |

  - A procura de raiz (caso `subfolder`) sobe no máximo 5 níveis e nunca ultrapassa a pasta pessoal do utilizador.
  - A procura de subprojetos (caso `root`) desce no máximo 2 níveis.
  - Os limiares (3 ficheiros, 2 subprojetos, 5 níveis) ficam em `config.py`.
  - Opção `--force` para analisar mesmo assim nos casos `root`, `subfolder` e `not_a_project`.
- Comando `las check <pasta>`: mostra só o veredito e as suas evidências, sem análise.
- Arquitetura de **detetores**: cada detetor é uma classe com `detect(project) -> list[Claim]`, registada numa lista. Adicionar um detetor nunca obriga a mexer nos outros.
- Detetores iniciais (só correm se o veredito for `project` ou `probable_project`):
  - `languages`: linguagens por contagem de ficheiros.
  - `manifests`: lê `package.json`, `requirements.txt`, `pyproject.toml`, `go.mod`, `Cargo.toml`, `composer.json`. Regista dependências e scripts com linha de origem.
  - `project_type`: Node/TS, Python, monorepo, etc.
  - `entry_points`: `main` / `bin` / `scripts.start` no package.json, `[project.scripts]` no pyproject, `main.py`/`app.py`/`manage.py`, `if __name__ == "__main__"`.
  - `structure`: pastas principais (primeiro e segundo nível com mais código).
  - `docs`: README e ficheiros `.md`/`.txt` encontrados.
- Escrita de `.localalibi/project.json`.
- Comando `las scan <pasta>`: corre os detetores e mostra o perfil no terminal, com símbolo de estado e evidência por baixo de cada linha.

**Verificação:**
- [x] `las check tests/fixtures/not_a_project` → `✗ não é um projeto de software`, com evidências, e `las scan` na mesma pasta para sem analisar.
- [x] `las check tests/fixtures/projects_root` → `root`, com os 4 projetos listados e sugestão de `las dashboard`.
- [x] `las check tests/fixtures/node_sqlite_lying_readme/src` → `subfolder`, apontando para `node_sqlite_lying_readme`.
- [x] `las check tests/fixtures/loose_scripts` → `≈ provável projeto`, e `las scan` analisa com aviso.
- [x] `las scan` em `python_fastapi_openai` mostra Python, dependências com número de linha e ponto de entrada.
- [x] `empty_project` mostra estados `?` em vez de inventar valores.
- [x] Cada `Claim` em `project.json` tem estado; os que não são `unknown` têm pelo menos uma evidência.
- [x] Testes por detetor contra as fixtures.

**Fora desta fase:** leitura de código-fonte com tree-sitter, BD SQLite, LLM.

---

## FASE 2 — Análise de código e promoção de evidências

**Objetivo:** ler o código para confirmar (ou não) o que os manifestos dizem.

**Entregar:**
- Parsing com tree-sitter para Python, JavaScript e TypeScript (outras linguagens depois).
- Extração por ficheiro: imports, funções, classes, chamadas relevantes.
- Novos detetores:
  - `database`: SQLite, PostgreSQL, MySQL, MongoDB, Redis, Supabase, Prisma, SQLAlchemy… (dependência + padrão no código).
  - `frameworks`: React, Next.js, Express, Fastify, FastAPI, Flask, Django, Vite…
  - `external_services`: OpenAI, Anthropic, Ollama, Stripe, GitHub API, Supabase, AWS… (imports, URLs conhecidos, nomes de variáveis de ambiente em `.env.example`).
  - `routes`: rotas HTTP (Express/Fastify/FastAPI/Flask/Next.js App Router) com ficheiro e linha.
- Aplicação da regra de promoção (`inferred` → `confirmed`).
- **Ranking de ficheiros importantes:** pontuação simples (ponto de entrada, número de importações recebidas, presença de rotas/BD, manifestos e README). Top 10 com uma frase determinista ("Ponto de entrada", "Acesso à base de dados", "Define 6 rotas").
- Guardar tudo em `.localalibi/evidence.db`.
- Opção `las scan --evidence` para mostrar todas as evidências; sem ela, mostra só a primeira de cada `Claim`.

**Verificação:**
- [x] `node_sqlite_lying_readme` → BD SQLite `✓` com evidência no `package.json` **e** em `src/db/database.ts`.
- [x] `python_dep_unused` → Redis `≈` (declarado, não usado).
- [x] `python_fastapi_openai` → OpenAI `✓` e rotas listadas com linha.
- [x] Análise de um projeto real médio (~500 ficheiros) em menos de 30 segundos.
- [x] Nenhum ficheiro fora de `.localalibi/` foi alterado (verificar com hash antes/depois nos testes).

**Fora desta fase:** README vs código, histórico, LLM.

---

## FASE 3 — Painel de todos os projetos

**Objetivo:** a "visão imediata" do disco inteiro. **Fim do MVP.**

**Entregar:**
- Descoberta de projetos dentro de uma pasta raiz **reutilizando o detetor `project_kind` da Fase 1** (sem lógica própria). Entram no painel as subpastas com veredito `project` ou `probable_project` (estas últimas marcadas com ≈). Não descer dentro de um projeto já encontrado (exceto monorepos, tratados como um só).
- Se `las dashboard` receber uma pasta que é ela própria um projeto, mostra o perfil desse projeto e sugere `las scan`.
- Cache: se nada mudou desde a última análise (data de modificação e, quando houver, `HEAD` do git), reutilizar `.localalibi/project.json`.
- Comando `las dashboard <pasta_raiz>` com uma tabela: nome, tipo, stack principal, BD, serviços externos, última alteração (git ou ficheiros), alertas (`⚠` e `?`).
- Comando `las dashboard <pasta_raiz> --html`: gera um relatório HTML estático e autónomo em `~/.localalibi/dashboard.html` (sem servidor, sem dependências externas). Cada projeto expande para o perfil completo com evidências.
- Ordenação por última alteração; filtro por linguagem.

**Verificação:**
- [x] `las dashboard tests/fixtures/projects_root` encontra os 4 projetos, incluindo o que não tem git.
- [x] Segunda execução sem alterações é pelo menos 5× mais rápida (cache).
- [x] O HTML abre no browser sem internet.
- [ ] Teste manual na pasta real de projetos do utilizador. *(Sem registo de que foi feito: confirmar à mão.)*

**Fora desta fase:** contradições, histórico, LLM.

---

## FASE 4 — Documentação que mente

**Objetivo:** detetar quando a documentação contradiz o código.

**Entregar:**
- Extrator determinista de afirmações da documentação: procura nomes de tecnologias conhecidas (a mesma tabela usada pelos detetores) em README e `.md`, guardando ficheiro, linha e frase.
- Comparação com os `Claim`s confirmados:
  - Documentação menciona X, código confirma Y da mesma categoria → `contradiction` com as duas evidências.
  - Código confirma X, documentação não o menciona → aviso "não documentado" (só para BD, frameworks e serviços externos).
  - Documentação menciona X, código não tem qualquer sinal → `inferred` "mencionado só na documentação".
- Secção "Documentação vs código" no `las scan` e no painel.
- **Nunca** editar a documentação.

**Verificação:**
- [x] `node_sqlite_lying_readme` → `⚠` com `README.md:linha` ("PostgreSQL") e `src/db/database.ts:linha` (SQLite).
- [x] `python_fastapi_openai` sem falsos positivos.
- [x] Testes com frases ambíguas ("migrámos de PostgreSQL para SQLite") documentados como limitação conhecida se não forem resolvidos.

**Fora desta fase:** interpretação com LLM das frases do README (fica para a Fase 6, opcional).

---

## FASE 5 — Histórico e `refresh`

**Objetivo:** contar a evolução do projeto em linguagem de arquitetura.

**Entregar:**
- `history.db`: cada `scan` guarda um snapshot (data, `HEAD` do git se existir, lista de `Claim`s, lista de ficheiros com hash).
- Comando `las refresh <pasta>`: nova análise + comparação com o snapshot anterior:
  - `+` novos `Claim`s (nova rota, novo serviço externo, nova dependência relevante).
  - `-` `Claim`s que desapareceram, ficheiros importantes removidos.
  - `~` componentes alterados (agrupar ficheiros modificados pela categoria do `Claim` a que pertencem: "Autenticação alterada, 4 ficheiros").
  - `⚠` novas contradições ("README ainda não menciona a nova API").
- Comando `las history <pasta>`: lista de snapshots com resumo de uma linha.
- Coluna "Mudou desde a última vez" no painel.

**Verificação:**
- [x] Teste que copia uma fixture para pasta temporária, faz scan, acrescenta `services/openai.ts` e uma rota, faz refresh → aparece `+ Serviço OpenAI` e `+ Nova rota` com ficheiro.
- [x] Remover um ficheiro importante aparece como `-`.
- [x] Funciona em projetos sem git (só por hash de ficheiros).

**Fora desta fase:** LLM.

---

## FASE 6 — Redação com LLM local (opcional, nunca obrigatória)

**Objetivo:** texto legível para humanos, sem inventar nada.

**Entregar:**
- Cliente Ollama mínimo (HTTP para `localhost:11434`), modelo configurável (por omissão um modelo de código pequeno, ex. `qwen2.5-coder:7b`).
- Se o Ollama não estiver disponível, tudo continua a funcionar e a ferramenta diz que a redação está desligada.
- Geração de `overview.md`: a LLM recebe **apenas** a lista de `Claim`s (não o código) e escreve um resumo em que cada frase termina com os ids citados, ex.: `Usa SQLite para guardar dados [db.engine].`
- **Validador:** cada frase gerada tem de citar pelo menos um id existente; frases sem citação ou com ids inexistentes são removidas. O texto resultante é marcado como `≈ redigido pela IA a partir de factos`.
- Comando `las explain <pasta>`: modo "Explique-me este projeto", com as perguntas fixas (O que faz? Como arranca? Onde está a interface? Onde está o backend? Onde estão os dados? Que APIs externas usa? Ficheiros mais importantes? Como comunicam os componentes? O que mudou recentemente? A documentação corresponde ao código? O que não foi possível determinar?). Respostas sem factos disponíveis mostram `?` em vez de texto da LLM.
- A pergunta "O que faz este projeto?" pode usar o README como contexto adicional, marcado como fonte.

**Verificação:**
- [x] Sem Ollama a correr, `las explain` funciona e mostra só factos.
- [x] Com Ollama, todas as frases do `overview.md` têm citações válidas (teste do validador com respostas falsas da LLM contendo ids inventados).
- [x] `empty_project` produz sobretudo `?`, não texto inventado.

**Fora desta fase:** perguntas livres.

---

## FASE 7 — Perguntas sobre o projeto

**Objetivo:** responder a perguntas livres procurando primeiro evidências.

**Entregar:**
- Comando `las ask <pasta> "Onde é feita a autenticação?"`.
- Pipeline: 1) procura determinista nos `Claim`s, nomes de ficheiros, funções, imports e rotas (palavras-chave + sinónimos simples); 2) junta os excertos encontrados; 3) a LLM responde **só** com base nesses excertos, citando `ficheiro:linha`; 4) o validador remove afirmações sem citação.
- Sem resultados na procura → resposta "Não encontrei evidências sobre isto" e sugestões de termos, sem chamar a LLM.
- Sem Ollama → mostrar só a lista de evidências encontradas.

**Verificação:**
- [x] "Onde usamos OpenAI?" em `python_fastapi_openai` cita `services/ai.py` com linha.
- [x] Pergunta sobre algo inexistente ("Onde está o pagamento Stripe?") não inventa resposta.

**Fora desta fase:** embeddings/RAG vetorial (só se a procura determinista se mostrar insuficiente).

---

## FASE 8 — Publicação

**Objetivo:** pronto para outros developers.

**Entregar:**
- README em inglês com a proposta de valor, GIF/captura do painel e do `⚠`.
- Página de exemplo com o painel HTML de projetos open source conhecidos.
- Publicação no PyPI (`localalibiscan`), licença MIT.
- Ficheiro de configuração `~/.localalibi/config.toml` (pastas a ignorar, modelo Ollama, limite de tamanho).

**Verificação:**
- [x] `pipx install localalibiscan` numa máquina limpa (Mac, Linux, Windows) e `las dashboard` funciona. *(Verificado no CI: `.github/workflows/ci.yml` instala o wheel com pipx em Linux, macOS e Windows e corre `las dashboard`.)*

---

## FASE 9 — Interface em inglês (internacionalização)

**Objetivo:** o README e o manual estão em inglês, mas a ferramenta fala português. Pôr a ferramenta a falar inglês por omissão, mantendo o português, sem mudar nenhum facto nem quebrar dados já guardados.

**Entregar:**
- Catálogos de mensagens em `src/localalibiscan/locales/` (`en` e `pt`), um ficheiro por língua, com chaves estáveis (ex. `verdict.not_a_project`). Sem dependências novas: um módulo `i18n.py` com `t(key, **params)`.
- Escolha da língua, por esta ordem: opção `--lang-ui` (ou nome equivalente que não colida com o `--lang` do painel), variável `LOCALALIBI_LANG`, `language` em `~/.localalibi/config.toml`, e por omissão `en`. Uma chave que falte numa língua cai para `en` e nunca rebenta.
- **Os factos não dependem da língua.** O `Claim` ganha campos opcionais `label_key`, `value_key`, `note_key` e `params`, e a `Evidence` ganha `snippet_key` e `params` para excertos gerados ("ficheiro de configuração"); é uma alteração compatível, a secção 4 não muda de forma incompatível. Os detetores passam a preencher as chaves; `label`, `note` e `snippet` continuam a ser gravados (na língua por omissão) para compatibilidade.
- A tradução faz-se **só na apresentação** (terminal, HTML, `overview.md`). `project.json`, `evidence.db` e `history.db` antigos, sem chaves, continuam a mostrar-se com o texto gravado.
- A língua **não** entra na impressão digital da cache: mudar de língua não obriga a reanalisar.
- Traduzir: ajuda da CLI (Typer), vereditos, perfil do `scan`, painel e relatório HTML, `refresh`/`history` (os textos "+/-/~/⚠"), perguntas fixas do `explain`, mensagens do `ask` ("Não encontrei evidências…") e avisos (Ollama desligado, `--force`, etc.).
- LLM: o prompt pede a resposta na língua escolhida; o validador não muda (continua a trabalhar com ids e `ficheiro:linha`, que não dependem da língua).
- Documentação vs código e `ask`: a deteção de tecnologias na documentação já é por nomes próprios; confirmar que funciona em README em inglês e em português. Os sinónimos do `ask` (`SYNONYM_GROUPS`) já são bilingues; acrescentar os termos em falta.
- Manual: retirar o aviso "the output is in Portuguese" do README e do `site/`, refazer capturas (`docs/img/`), página de exemplo e vídeo/GIF em inglês. `scripts/gen_reference.py` gera a referência em inglês.
- Teste que percorre todas as chaves usadas no código (procura de `t("…")`) e falha se alguma faltar em `en`; aviso (não falha) se faltar em `pt`.
- Subir `__version__` (os detetores mudam).

**Verificação:**
- [x] `las scan tests/fixtures/python_fastapi_openai` sem configuração mostra o perfil em inglês; com `LOCALALIBI_LANG=pt` mostra-o em português, com os mesmos estados, valores e evidências.
- [x] `las check tests/fixtures/not_a_project` em inglês → `✗ not a software project`, com as mesmas evidências.
- [x] `project.json` de duas análises (uma em cada língua) tem os mesmos `id`, `status`, `value` e evidências.
- [x] Um `project.json`/`history.db` criado pela versão 0.1.x (sem chaves) é lido e mostrado sem erros.
- [x] Mudar de língua e voltar a correr `las dashboard` usa a cache (sem reanalisar).
- [x] `las ask` "Where do we use OpenAI?" e "Onde usamos OpenAI?" citam o mesmo `services/ai.py:linha`.
- [x] Teste de chaves em falta passa; `pytest` passa; README e manual sem aviso de português.

**Fora desta fase:** outras línguas além de `en` e `pt` (o mecanismo tem de as permitir, mas não se traduzem agora); tradução de texto da documentação do projeto analisado.

---

## FASE 10 — Interface gráfica local (Streamlit, opcional)

**Objetivo:** quem não vive no terminal consegue ver o painel, cada projeto com as suas provas, o que mudou, a explicação e as perguntas numa interface no browser, **sem que a ferramenta deixe de cumprir nenhuma regra da secção 2**.

**Entregar:**
- Comando `las ui [pasta]` que arranca uma interface Streamlit e abre o browser. Opções `--port` (por omissão 8501) e `--no-browser`.
- Streamlit é um **extra opcional**: `pipx install 'localalibiscan[ui]'`. A instalação base não muda. Sem o extra, `las ui` explica como o instalar e sai com código 2.
- Um único módulo `ui.py`, **só apresentação**: chama `classify`, `build_dashboard`, `scan(..., use_cache=True)`, `list_snapshots`/`diff_snapshots`, `drafting.explain` e `ask.ask`. Nenhuma lógica de deteção nova.
- Ecrãs: painel (tabela com filtro por texto e linguagem, escolha de um projeto), perfil (secções, estado de cada afirmação, filtro por estado, evidências com excerto do ficheiro à volta da linha), histórico (análises anteriores e diferenças), explicação e perguntas (LLM opcional, com as mesmas validações da CLI). Botão para reanalisar.
- Regras fixadas pelo comando, na linha de comandos do Streamlit (ganha a qualquer ficheiro de configuração): `server.address=127.0.0.1`, `browser.gatherUsageStats=false`, `server.headless=true`, `server.fileWatcherType=none`, `server.runOnSave=false`. O processo corre com a pasta de trabalho em `~/.localalibi/`, para não ler um `.streamlit/config.toml` do projeto analisado.
- Texto vindo do projeto analisado (rótulos, valores, excertos, respostas da LLM) nunca é interpretado como Markdown/HTML: vai em blocos de código, tabelas ou Markdown escapado (uma imagem em Markdown faria um pedido de rede).
- Línguas: textos novos em `locales/` (chaves `gui.*`), escolha de língua na própria interface.

**Verificação:**
- [x] `las ui tests/fixtures/projects_root` mostra os 4 projetos; escolher um mostra o perfil com evidências.
- [x] O servidor só escuta em `127.0.0.1` e não envia estatísticas (argumentos verificados em teste).
- [x] Sem Streamlit instalado, `las ui` mostra como instalar o extra e sai com código 2; o resto da CLI funciona.
- [x] Teste da app com `streamlit.testing` (sem browser) num projeto e numa raiz, com `tree_hash` igual antes e depois.
- [x] Nenhum `unsafe_allow_html` no código; texto do projeto escapado.
- [x] `pytest` passa; manual com página da interface; referência de comandos gerada de novo.

**Fora desta fase:** editar a configuração na interface, acesso remoto (outra máquina), autenticação, vários utilizadores.

---

## 7. Como trabalhar com o Claude Code

Colocar este ficheiro na raiz do repositório como `SPEC.md`. Para cada fase, usar um pedido deste género:

```
Lê o SPEC.md e o CLAUDE.md. Implementa apenas a FASE N.
Não comeces a fase seguinte.
No fim, corre o pytest, verifica cada item da lista de verificação da FASE N
e mostra-me quais estão cumpridos e quais não, com a evidência (comando e resultado).
```

Depois de cada fase: rever, fazer commit com a etiqueta `fase-N` e só então pedir a seguinte.

**MVP = Fases 0 a 3.** É aí que já existe o diferenciador: factos com prova e o painel de todos os projetos.
