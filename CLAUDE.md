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
- Qualquer pasta com `pyvenv.cfg` (virtualenv com outro nome) ou chamada `site-packages` é ignorada.
- Documentação vs código: `doc_mentions.py` (extrator) + `detectors/docs_vs_code.py`. Limitações em `docs/limitacoes.md` — atualizar quando se muda uma heurística.
- Histórico: `history.py` (`history.db`: snapshot por análise real com Claims + hash de ficheiros; `diff_snapshots` traduz para "+/-/~/⚠"). Uma análise vinda da cache não cria snapshot.
- LLM (opcional): `llm.py` (cliente Ollama, só aceita localhost) e `drafting.py`. A LLM recebe só Claims (id, rótulo, valor, estado, nota) — nunca código. Pede-se JSON `{"text", "ids"}` (modelos pequenos não citam bem em texto livre) e tudo passa pelo `validate`, que remove frases sem citação ou com ids inexistentes. Exemplos no prompt só com marcadores (um exemplo real é copiado). Testes usam modelos falsos; nenhum teste depende do Ollama.
- Perguntas: `ask.py` — procura determinista (Claims, ficheiros, funções, imports, rotas; sinónimos em `SYNONYM_GROUPS`; termos da pergunta valem mais que sinónimos), excertos com contexto, LLM só com os excertos e validação por `ficheiro:linha` dentro dos excertos. Sem evidências → não se chama a LLM.
- SQLite: `storage.py`; os caminhos passam por `ProjectFS.writable_path`.
- Todo o claim que não é `unknown` tem pelo menos uma `Evidence` (há teste para isso).
- Git só via `subprocess` com comandos de leitura (`log`, `status`, `rev-parse`).
- Constantes e limiares vivem em `src/localalibiscan/config.py`.

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
