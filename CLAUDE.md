# LocalAlibiScan

Ferramenta local que diz o que cada projeto é, como está e o que mudou, e prova cada afirmação com ficheiro e linha. A especificação completa, por fases, está em `SPEC.md`. **Implementar uma fase de cada vez**; não começar a seguinte sem pedido.

## Regras invariáveis (SPEC.md, secção 2)

- **Só leitura.** A ferramenta nunca modifica, apaga ou move ficheiros do projeto analisado.
- **Única escrita permitida:** dentro de `<projeto>/.localalibi/` (e na pasta de configuração do utilizador, `~/.localalibi/`).
- **Nunca executa código do projeto analisado** (nem scripts, nem testes, nem `npm install`).
- **Sem rede**, exceto chamadas para o Ollama em `localhost` (a partir da Fase 6).
- **Nenhuma afirmação sem estado.** Tudo o que é mostrado ao utilizador é um `Claim` com estado e, sempre que possível, evidências.
- **A LLM nunca cria factos.** Só pode redigir texto a partir de `Claim`s existentes e tem de citar os seus identificadores.
- **Determinismo primeiro.** Se uma regra ou parser resolve, não se usa LLM.
- **Respeitar `.gitignore`** e ignorar sempre `node_modules`, `.venv`, `venv`, `dist`, `build`, `.git`, `__pycache__`, `.next`, `target`.
- **Ficheiros grandes ou binários** são registados mas não lidos (limite configurável, por omissão 1 MB).

## Como o código cumpre as regras

- `src/localalibiscan/fs.py` é a **única** camada que escreve ou lê conteúdo de ficheiros do projeto analisado (os detetores leem via `Project.text()`/`lines()`). Nenhum outro módulo usa `open()`, `Path.write_*`, `os.remove`, `shutil` sobre o projeto. Escrever fora das pastas permitidas lança `ReadOnlyViolation`. (Exceção: ler os nossos próprios ficheiros em `.localalibi/`.)
- Detetores: `src/localalibiscan/detectors/`. Cada um é uma classe com `detect(project) -> list[Claim]`, decorada com `@register` e importada em `detectors/__init__.py` (a ordem de importação é a ordem de execução). Dados partilhados entre detetores vivem em funções com cache em `project.cache` (ex.: `parse_manifests`), nunca em chamadas diretas a outro detetor.
- `detectors/project_kind.py` decide o veredito da pasta e corre antes de tudo (fora do REGISTRY). O painel (Fase 3) reutiliza `classify`/`find_subprojects`.
- Detetores podem ler os Claims já produzidos (`project.claims`), por categoria/id — é o contrato estável — mas nunca chamar outro detetor.
- Código: `code/parser.py` (tree-sitter → `FileFacts`) e `code/index.py` (`code_index(project)`, resolução de imports locais, grafo de imports). Nunca se executa código analisado.
- Tecnologias: tabela única em `tech.py` (dependências, imports, strings, env vars, ficheiros de config, nomes em docs). Regra de promoção em `detectors/technologies.py`. Para suportar uma nova tecnologia basta acrescentar uma linha a `TECHS`.
- Painel: `dashboard.py` usa `discover_projects` de `project_kind` (sem lógica própria de descoberta) e `scan(..., use_cache=True)`. A cache compara a impressão digital (caminho+mtime+tamanho de cada ficheiro, HEAD do git, versão) guardada em `project.json`. HTML em `html_report.py`: autónomo, sem recursos externos, todo o conteúdo passa por `html.escape`.
- Git: só através de `git.py` (lista branca `rev-parse`/`log`/`status`, `GIT_OPTIONAL_LOCKS=0`).
- Código em pastas de testes/exemplos/playgrounds/templates (`knowledge.NON_PRODUCT_DIRS`) nunca é evidência de tecnologias, rotas, dependências ou componentes.
- Literais de texto só provam uso se forem URL/connection string completos (o fragmento sozinho, ex. `"postgres://"`, é uma menção).
- Mudanças na lógica de deteção: subir `__version__` (faz parte da impressão digital da cache).
- Configuração do utilizador: `~/.localalibi/config.toml` (`config.load_config`); os testes isolam-na com `LOCALALIBI_CONFIG` (fixture autouse em `conftest.py`).
- Qualquer pasta com `pyvenv.cfg` (virtualenv com outro nome) ou chamada `site-packages` é ignorada.
- Documentação vs código: `doc_mentions.py` (extrator) + `detectors/docs_vs_code.py`. Limitações em `docs/limitacoes.md` — atualizar quando se muda uma heurística.
- Histórico: `history.py` (`history.db`: snapshot por análise real com Claims + hash de ficheiros; `diff_snapshots` traduz para "+/-/~/⚠"). Uma análise vinda da cache não cria snapshot.
- LLM (opcional): `llm.py` (cliente Ollama, só aceita localhost) e `drafting.py`. A LLM recebe só Claims (id, rótulo, valor, estado, nota) — nunca código. Pede-se JSON `{"text", "ids"}` (modelos pequenos não citam bem em texto livre) e tudo passa pelo `validate`, que remove frases sem citação ou com ids inexistentes. Exemplos no prompt só com marcadores (um exemplo real é copiado). Testes usam modelos falsos; nenhum teste depende do Ollama.
- Perguntas: `ask.py` — procura determinista (Claims, ficheiros, funções, imports, rotas; sinónimos em `SYNONYM_GROUPS`; termos da pergunta valem mais que sinónimos), excertos com contexto, LLM só com os excertos e validação por `ficheiro:linha` dentro dos excertos. Sem evidências → não se chama a LLM.
- SQLite: `storage.py`; os caminhos passam por `ProjectFS.writable_path`.
- Todo o claim que não é `unknown` tem pelo menos uma `Evidence` (há teste para isso).
- Git só via `subprocess` com comandos de leitura (`log`, `status`, `rev-parse`).
- Constantes e limiares vivem em `src/localalibiscan/config.py`.
- Línguas (Fase 9): todo o texto mostrado ao utilizador passa por `i18n.t`/`tn` com chaves em `locales/en.py` (obrigatório) e `locales/pt.py`. Os detetores nunca escrevem texto solto: usam `label_key`/`value_key`/`note_key` + `params` em `Detector.claim` e `gen_evidence` para excertos gerados; grava-se o texto em inglês e traduz-se só ao mostrar (`claim_label`, `claim_note`, `claim_text_value`, `evidence_snippet`). A língua não entra na impressão digital da cache. `tests/test_i18n.py` falha se uma chave usada faltar em `en`.
- Interface gráfica (Fase 10): `ui.py` (Streamlit, extra opcional `[ui]`), só apresentação — chama o núcleo, sem lógica própria. `las ui` (`cli.ui_command`) fixa na linha de comandos `127.0.0.1` e `gatherUsageStats=false` e corre com `cwd=~/.localalibi`. Texto do projeto analisado nunca vai para Markdown sem `ui.md()` (escapa tudo; nada de `unsafe_allow_html`). Chaves de texto em `gui.*`. Testes em `tests/test_ui.py` com `streamlit.testing`.
- Capturas do README/manual e página de exemplo: `scripts/gen_captures.py` (refazer quando muda um texto que aparece nelas).

## Desenvolvimento

```bash
uv venv -p 3.12 .venv && uv pip install -p .venv -e '.[dev]'
.venv/bin/pytest
.venv/bin/las --help
```

- Fixtures em `tests/fixtures/` (ver SPEC.md secção 6). Uma pasta `.git` não pode ser guardada dentro deste repositório: os testes que precisam de git usam a fixture `fixture_copy` de `tests/conftest.py`, que copia para uma pasta temporária e faz `git init` onde está definido em `GIT_PROJECTS`.
- `tests/fixtures/.localalibi-ceiling` trava a procura de raiz para cima: sem ele, as fixtures seriam vistas como subpastas deste repositório.
- `empty_project` só tem um README; à mão dá `not_a_project`, nos testes recebe `git init` e é um `project` que mostra `?`.
- Usar a fixture `config` (pasta pessoal isolada em tmp) nos testes que chamam `classify`/`scan`.
- Testes que analisam fixtures devem confirmar só leitura com `tree_hash` antes/depois.
- Depois de cada fase: rever, commit com a etiqueta `fase-N`.
- README: imagens e links sempre com URLs absolutos (site de docs / GitHub) — o README é também a página do PyPI, onde caminhos relativos não funcionam.
- CI (`.github/workflows/ci.yml`): pytest em Linux/macOS/Windows e instalação limpa com pipx. Os ficheiros de saída do produto indicam sempre `encoding="utf-8"`.
- Manual: `site/` (VitePress, inglês), publicado no GitHub Pages por `.github/workflows/pages.yml`. `site/reference/commands.md` e `technologies.md` são gerados por `scripts/gen_reference.py` (há um teste que falha se estiverem desatualizados: depois de mudar a CLI ou `tech.py`, correr o script).
- Marca: `site/public/brand/` (logótipo e ícone, versões clara/escura); favicons e `og.png` derivados; ícones de 64 px em `src/localalibiscan/assets/` (embutidos no relatório HTML).
- Página de exemplo: `site/public/example/index.html`. Capturas SVG em `docs/img/`.
- Vídeo e GIF de demonstração: `scripts/demo-video.sh` (VHS em Docker + Ollama local), guião em `docs/video/PLANO.md`. Se mudar um texto que uma cena mostra, refazer o vídeo.
- Publicação no PyPI: `.github/workflows/publish.yml` (trusted publishing ao publicar uma release). Licença: MIT.
