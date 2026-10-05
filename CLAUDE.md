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

- `src/localalibiscan/fs.py` é a **única** camada de acesso a ficheiros do projeto analisado. Nenhum outro módulo usa `open()`, `Path.write_*`, `os.remove`, `shutil` sobre o projeto. Escrever fora das pastas permitidas lança `ReadOnlyViolation`.
- Git só via `subprocess` com comandos de leitura (`log`, `status`, `rev-parse`).
- Constantes e limiares vivem em `src/localalibiscan/config.py`.

## Desenvolvimento

```bash
uv venv -p 3.12 .venv && uv pip install -p .venv -e '.[dev]'
.venv/bin/pytest
.venv/bin/las --help
```

- Fixtures em `tests/fixtures/` (ver SPEC.md secção 6). Uma pasta `.git` não pode ser guardada dentro deste repositório: os testes que precisam de git usam a fixture `fixture_copy` de `tests/conftest.py`, que copia para uma pasta temporária e faz `git init` onde está definido em `GIT_PROJECTS`.
- Testes que analisam fixtures devem confirmar só leitura com `tree_hash` antes/depois.
- Depois de cada fase: rever, commit com a etiqueta `fase-N`.
