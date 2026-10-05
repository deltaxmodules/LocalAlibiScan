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
