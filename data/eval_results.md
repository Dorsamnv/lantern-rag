# Lantern Retrieval Evaluation

- Generated: **2026-08-11 12:33 UTC**
- Corpus: `data\sample_docs` (11 files)
- Metric: **hit@4** (expected filename match AND keyword evidence)
- Result: **10/10 = 100%**

| ID | Question | Hit@4 | Notes |
|----|----------|--------|-------|
| Q1 | What is few-shot learning? | PASS | file+text | top: few_shot_learning_notes.md (0.76), few_shot_learning_notes.md (0.63), vqa_overview.md (0.49) |
| Q2 | What is the N-way K-shot protocol? | PASS | file+text | top: few_shot_learning_notes.md (0.64), few_shot_learning_notes.md (0.29), vqa_overview.md (0.28) |
| Q3 | What challenges exist in Visual Question Answering? | PASS | file+text | top: vqa_overview.md (0.73), few_shot_learning_notes.md (0.67), vqa_overview.md (0.64) |
| Q4 | How does Lantern generate answers? | PASS | file+text | top: lantern_brief.md (0.75), rag_basics.md (0.59), lantern_brief.md (0.56) |
| Q5 | What is self-attention in Transformers? | PASS | file+text | top: transformers_attention.md (0.61), transformers_attention.md (0.44), transformers_attention.md (0.41) |
| Q6 | Explain Retrieval-Augmented Generation in one paragraph. | PASS | file+text | top: rag_basics.md (0.59), rag_evaluation_notes.md (0.50), transformers_attention.md (0.48) |
| Q7 | What is the difference between precision and recall? | PASS | file+text | top: ml_metrics.md (0.54), ml_metrics_precision_recall.md (0.54), ml_metrics.md (0.54) |
| Q8 | What are the core building blocks of a CNN? | PASS | file+text | top: cnn_basics.md (0.56), cnn_basics.md (0.54), cnn_basics.md (0.52) |
| Q9 | What prompt engineering rules help grounded RAG assistants? | PASS | file+text | top: prompt_engineering.md (0.56), rag_basics.md (0.40), vqa_overview.md (0.39) |
| Q10 | What belongs on a responsible AI checklist? | PASS | file+text | top: responsible_ai.md (0.78), responsible_ai.md (0.51), responsible_ai.md (0.49) |

## How to re-run
```powershell
cd rag-chatbot
.\.venv\Scripts\python scripts\evaluate_retrieval.py --k 4
```
