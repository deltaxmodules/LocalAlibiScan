# Limitações conhecidas

## Documentação vs código (Fase 4)

O extrator de afirmações da documentação é determinista: procura nomes de
tecnologias (tabela `tech.py`) linha a linha. Não interpreta frases.

O que é tratado:

- **Frases de migração** ("Migrámos de PostgreSQL para SQLite", "We moved from
  MongoDB to …", "anteriormente", "legacy"…): a menção é marcada como ambígua e
  nunca gera `⚠`; aparece como `≈ Só na documentação` com nota.
- **Negações próximas** ("no Redis", "sem PostgreSQL", "instead of MySQL").
- **Comparações**: uma linha que nomeia também a tecnologia rival confirmada
  (ex.: tabelas "| SQLite | PostgreSQL |") não prova contradição.
- **Palavras comuns** ("Express", "Click", "React"…): só contam com a
  capitalização exata e nunca no início de uma frase normal (contam em listas
  e títulos, onde se costuma descrever a stack).
- Só os **README** provam contradições; outros `.md` (raiz e `docs/`) só geram
  `≈ Só na documentação`. Pastas ocultas (`.claude/`, `.planning/`…) e ficheiros
  de instruções para agentes (`CLAUDE.md`, `AGENTS.md`…) não são lidos.

O que **não** é resolvido:

- Negações longas ou indiretas ("O projeto não precisa, nesta fase, de um
  PostgreSQL") — a negação só é detetada até duas palavras antes do nome.
- Frases condicionais ou de futuro ("Vamos usar PostgreSQL em produção").
- Ironia, citações e exemplos que não estão em blocos identificáveis.
- Tecnologias fora da tabela `tech.py` (não são detetadas nem no código nem na
  documentação).
- Grupos exclusivos são fixos (`EXCLUSIVE_GROUPS`): um projeto que usa
  legitimamente duas BDs relacionais pode ter `⚠` se só uma tiver sinais no código.

A interpretação de frases com LLM fica para a Fase 6 (opcional).

## Análise de código (Fase 2)

- Rotas: prefixos de routers só são resolvidos no mesmo ficheiro ou quando o
  router é montado a partir de um import local (`include_router`,
  `register_blueprint`, `app.use`, `fastify.register`). Rotas geradas
  dinamicamente (ciclos, strings construídas) não são detetadas.
- Notebooks (`.ipynb`) contam para a linguagem mas o seu código não é analisado.
- Só Python, JavaScript e TypeScript são analisados com tree-sitter.

## Interface e línguas (Fase 9)

- Só inglês (por omissão) e português. Outra língua cai para o inglês, chave a chave.
- Perfis e histórico gravados pela 0.1.x não têm chaves de tradução: mostram o
  texto em português com que foram gravados até à análise seguinte.
- A ajuda (`--help`) escolhe a língua quando o programa arranca: `--lang-ui`
  tem de vir antes do comando (`las --lang-ui pt scan --help`).
- As frases que tornam uma menção ambígua (migração, negação, comparação) só
  são reconhecidas em inglês e português; os nomes das tecnologias são
  procurados em qualquer língua.
- A LLM recebe os pedidos em inglês e é-lhe pedido que escreva na língua da
  interface; modelos pequenos às vezes respondem noutra língua (o validador
  só verifica as citações, não a língua).
