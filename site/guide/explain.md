# Explain this project

```bash
las explain ~/code/shop
las explain ~/code/shop --no-llm         # facts only
las explain ~/code/shop --model qwen3:8b
```

`las explain` answers a fixed set of questions, always from facts:

1. What does this project do?
2. How does it start?
3. Where is the interface?
4. Where is the backend?
5. Where is the data?
6. Which external APIs does it use?
7. Which files matter most?
8. How do the components talk to each other?
9. What changed recently?
10. Does the documentation match the code?
11. What could not be determined?

For each question it selects the relevant claims deterministically. **If there are no facts, the answer is `?`** and the model is not even asked — an empty project produces mostly `?`, not invented text. "What does it do?" also shows the first paragraph of the README, marked as its source.

## With a local model

If [Ollama](https://ollama.com) is running on `localhost:11434` with the configured model (default `qwen2.5-coder:7b`), each answer also gets one to three sentences written by the model, marked ≈:

```text
Where is the data?
  ≈ The data is stored in an SQLite database. [db.sqlite]
  ✓ Database: SQLite  ← package.json:13
```

The rules that keep it honest:

- The model receives **claims only** — id, label, value, status, note. Never your code.
- Every sentence must end with the ids of the claims it is based on.
- A **validator** removes every sentence without a citation, or citing an id that doesn't exist (or that belongs to another question). The count of removed sentences is shown.
- Everything the model writes is marked **≈ redigido pela IA a partir de factos**.

`las explain` also writes `.localalibi/overview.md`: a short AI summary (same rules) followed by every question with its facts and citations.

Without Ollama, everything works and the header says the AI drafting is off.
