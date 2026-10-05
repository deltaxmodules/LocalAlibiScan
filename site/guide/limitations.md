# Known limitations

## Documentation vs code

The extractor is deterministic and doesn't interpret sentences. It handles migrations, short negations, comparisons and common words (see [Documentation that lies](./docs-vs-code)), but not:

- long or indirect negations (*"at this stage the project does not need a PostgreSQL database"* — the negation is only detected up to two words before the name);
- conditional or future sentences (*"we will use PostgreSQL in production"*);
- technologies missing from the [detection table](../reference/technologies);
- a project that legitimately uses two relational databases where only one has signals in the code.

## Code analysis

- Only Python, JavaScript and TypeScript are parsed; other languages are counted and their manifests read.
- Route prefixes are resolved inside a file and through local imports (`include_router`, `register_blueprint`, `app.use`, `fastify.register`); routes built dynamically are not detected.
- Notebook code is counted, not parsed.

## Interface

The terminal output and the HTML report are in Portuguese.

The full list (in Portuguese) is kept in [`docs/limitacoes.md`](https://github.com/deltaxmodules/LocalAlibiScan/blob/main/docs/limitacoes.md).
