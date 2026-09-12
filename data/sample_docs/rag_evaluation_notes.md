# Sample RAG Evaluation Notes

This note documents the lightweight retrieval evaluation used for Lantern.

## Goal
Measure whether retrieval returns the right evidence before the LLM writes an answer.

## How it works
Run:

```powershell
.\.venv\Scripts\python scripts\evaluate_retrieval.py --k 4
```

The script:
1. Builds an isolated Chroma index from `data/sample_docs/`
2. Runs the questions in `scripts/eval_cases.json`
3. Scores **hit@k** (expected filename match AND keyword evidence)
4. Writes `data/eval_results.md` and `data/eval_results.json`

## Latest summary
See `data/eval_results.md` and the Evaluation section in the project README.

## Portfolio takeaway
Even a small 10-question checklist shows engineering maturity: Lantern is evaluated as a retrieval system, not only as a chat UI.
