# Retrieval-Augmented Generation (RAG)

RAG combines a retriever with a generator so answers are grounded in external documents.

## Pipeline
1. **Index:** split documents into chunks and store embeddings in a vector database
2. **Retrieve:** embed the user question and fetch top-k similar chunks
3. **Generate:** give those chunks to an LLM and ask it to answer with citations

## Why RAG helps
- Reduces hallucination on private or fresh knowledge
- Lets you update knowledge by re-indexing files, without full model retraining
- Makes answers auditable when sources are shown

## Failure modes
- Bad chunking (too small / too large) hurts retrieval
- Weak embeddings miss paraphrases
- The LLM may ignore retrieved context if the prompt is weak
- Noisy OCR or poorly extracted PDFs poison the index

## Design choices in Lantern
Lantern uses local sentence embeddings, ChromaDB persistence, streaming generation, and source cards with relevance scores so users can verify every claim.
