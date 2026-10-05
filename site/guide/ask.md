# Ask a question

```bash
las ask ~/code/shop "Where is authentication done?"
las ask ~/code/shop "Onde usamos OpenAI?" --brief      # one line per evidence
las ask ~/code/shop "..." --no-llm                     # evidence only
```

Evidence comes first, the model second:

1. **Deterministic search** in claims, file names, function and class names, imports and routes — using the words of your question (accents and stop-words ignored) plus simple synonyms: *authentication* also looks for `login`, `jwt`, `token`, `password`, `session`…; *payment* for `stripe`, `checkout`, `billing`…
2. **Excerpts**: a few lines around each hit, best first. Product code ranks above tests and examples.
3. **The model answers only from the excerpts**, in the language of the question, citing `file:line`.
4. **The validator** removes every sentence that doesn't cite a line inside the excerpts.

```text
≈ Resposta redigida pela IA a partir das evidências (modelo qwen2.5-coder:7b)
  ≈ Authentication is done in the login routes. [backend/app/api/routes/login.py:23]
  ≈ The verification of passwords is handled in the security module. [backend/app/core/security.py:30]
```

**If nothing is found, the answer is "Não encontrei evidências sobre isto"** — with terms that do exist in the project as suggestions — and the model is never called. Asking about Stripe in a project without Stripe cannot produce an invented answer.

Without Ollama you get the list of evidence.
