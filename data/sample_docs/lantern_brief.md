# Lantern Product Brief

Lantern is an English-first Retrieval-Augmented Generation (RAG) assistant for private documents.

## What Lantern does
1. Accepts PDF, TXT, and Markdown uploads
2. Splits documents into overlapping chunks
3. Embeds chunks into a local vector database (ChromaDB)
4. Retrieves the most relevant passages for each question
5. Streams an LLM answer with explicit source citations and relevance scores

## Design goals
- Answers must be grounded in uploaded sources
- Users should inspect relevance scores and passage previews
- The interface should feel like a research tool, not a toy chatbot
- English is the primary demo language for reliability

## How Lantern generates answers
Lantern does **not** answer from general internet knowledge alone for document questions.
It first retrieves top-k passages, then asks the LLM to answer using only those passages, citing them as [S1], [S2], and so on.

## Suggested demo questions
1. What is few-shot learning?
2. What challenges exist in Visual Question Answering?
3. How does Lantern generate answers?
4. What is self-attention in Transformers?
5. Explain Retrieval-Augmented Generation in one paragraph.
6. What is the difference between precision and recall?
7. What metrics are used in the sample RAG evaluation?

## Non-goals (for now)
- Perfect multilingual PDF OCR
- Fully local voice pipeline as a core feature
- Production authentication / multi-tenant cloud hosting
