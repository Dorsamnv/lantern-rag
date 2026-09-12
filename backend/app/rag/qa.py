"""LLM answering with retrieved context (sync + streaming)."""
from __future__ import annotations

import json
import time
from collections.abc import Iterator

from openai import OpenAI

from app.config import get_settings
from app.rag.store import RetrievedChunk, retrieve


SYSTEM_PROMPT = """You are Lantern, an English-first research assistant for Retrieval-Augmented Generation.
Answer ONLY using the provided source excerpts.
Rules:
- Default language: clear professional English.
- If the sources are insufficient, say you cannot find enough information in the uploaded documents.
- Be clear and structured. Prefer short paragraphs or bullet points.
- Cite sources inline like [S1], [S2] matching the source list.
- Do not invent facts that are not supported by the sources.
- If the user asks in another language, still prefer English unless the sources themselves require quoting non-English text.
"""

ABSTAIN_MESSAGE = (
    "I could not find enough relevant evidence in the uploaded documents to answer confidently. "
    "Try rephrasing the question, uploading a more relevant file, or lowering the relevance threshold. "
    "The weak matches below are shown for inspection only."
)


def _client_and_model() -> tuple[OpenAI, str]:
    settings = get_settings()
    provider = settings.llm_provider.lower().strip()

    if provider == "groq":
        if not settings.groq_api_key:
            raise RuntimeError(
                "GROQ_API_KEY is missing. Add it to rag-chatbot/.env (free key at console.groq.com)."
            )
        client = OpenAI(api_key=settings.groq_api_key, base_url="https://api.groq.com/openai/v1")
        return client, settings.llm_model

    if provider == "ollama":
        client = OpenAI(api_key="ollama", base_url=settings.ollama_base_url)
        return client, settings.ollama_model

    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is missing. Add it to rag-chatbot/.env.")
    client = OpenAI(api_key=settings.openai_api_key)
    return client, settings.llm_model


def build_context(chunks: list[RetrievedChunk]) -> str:
    blocks: list[str] = []
    for i, chunk in enumerate(chunks, start=1):
        page = f", page {chunk.page}" if chunk.page else ""
        blocks.append(
            f"[S{i}] ({chunk.filename}{page}, relevance={chunk.score:.2f})\n{chunk.text}"
        )
    return "\n\n".join(blocks)


def _sources_payload(chunks: list[RetrievedChunk]) -> list[dict]:
    return [
        {
            "id": f"S{i}",
            "filename": c.filename,
            "page": c.page,
            "score": c.score,
            "text": c.text,
            "chunk_id": c.chunk_id,
        }
        for i, c in enumerate(chunks, start=1)
    ]


def _messages(question: str, context: str) -> list[dict[str, str]]:
    user_prompt = (
        f"Sources:\n{context}\n\n"
        f"Question: {question}\n\n"
        "Write the best answer you can from these sources."
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


def _should_abstain(chunks: list[RetrievedChunk], min_relevance: float) -> bool:
    if not chunks:
        return True
    return max(c.score for c in chunks) < min_relevance


def answer_question(
    question: str,
    top_k: int | None = None,
    temperature: float | None = None,
    min_relevance: float | None = None,
) -> dict:
    settings = get_settings()
    threshold = settings.min_relevance if min_relevance is None else min_relevance
    t0 = time.perf_counter()
    chunks = retrieve(question, top_k=top_k)
    retrieve_ms = int((time.perf_counter() - t0) * 1000)

    if not chunks:
        return {
            "answer": "No documents are indexed yet. Upload PDF/TXT/Markdown files first, then ask again.",
            "sources": [],
            "meta": {
                "retrieve_ms": retrieve_ms,
                "llm_ms": 0,
                "total_ms": retrieve_ms,
                "abstained": True,
                "min_relevance": threshold,
            },
        }

    if _should_abstain(chunks, threshold):
        best = max(c.score for c in chunks)
        return {
            "answer": ABSTAIN_MESSAGE,
            "sources": _sources_payload(chunks),
            "meta": {
                "retrieve_ms": retrieve_ms,
                "llm_ms": 0,
                "total_ms": retrieve_ms,
                "abstained": True,
                "best_score": best,
                "min_relevance": threshold,
            },
        }

    context = build_context(chunks)
    client, model = _client_and_model()
    temp = settings.temperature if temperature is None else temperature

    t1 = time.perf_counter()
    completion = client.chat.completions.create(
        model=model,
        temperature=temp,
        messages=_messages(question, context),
    )
    llm_ms = int((time.perf_counter() - t1) * 1000)
    answer = completion.choices[0].message.content or ""
    total_ms = int((time.perf_counter() - t0) * 1000)

    return {
        "answer": answer,
        "sources": _sources_payload(chunks),
        "meta": {
            "retrieve_ms": retrieve_ms,
            "llm_ms": llm_ms,
            "total_ms": total_ms,
            "model": model,
            "abstained": False,
            "best_score": max(c.score for c in chunks),
            "min_relevance": threshold,
        },
    }


def stream_answer(
    question: str,
    top_k: int | None = None,
    temperature: float | None = None,
    min_relevance: float | None = None,
) -> Iterator[str]:
    """Yield Server-Sent Event lines."""
    settings = get_settings()
    threshold = settings.min_relevance if min_relevance is None else min_relevance
    t0 = time.perf_counter()
    chunks = retrieve(question, top_k=top_k)
    retrieve_ms = int((time.perf_counter() - t0) * 1000)

    if not chunks:
        payload = {
            "type": "final",
            "answer": "No documents are indexed yet. Upload PDF/TXT/Markdown files first, then ask again.",
            "sources": [],
            "meta": {
                "retrieve_ms": retrieve_ms,
                "llm_ms": 0,
                "total_ms": retrieve_ms,
                "abstained": True,
                "min_relevance": threshold,
            },
        }
        yield f"data: {json.dumps(payload)}\n\n"
        return

    sources_payload = _sources_payload(chunks)
    best = max(c.score for c in chunks)
    if _should_abstain(chunks, threshold):
        meta = {
            "retrieve_ms": retrieve_ms,
            "llm_ms": 0,
            "total_ms": retrieve_ms,
            "abstained": True,
            "best_score": best,
            "min_relevance": threshold,
        }
        yield f"data: {json.dumps({'type': 'sources', 'sources': sources_payload, 'meta': meta})}\n\n"
        yield f"data: {json.dumps({'type': 'final', 'answer': ABSTAIN_MESSAGE, 'sources': sources_payload, 'meta': meta})}\n\n"
        return

    yield f"data: {json.dumps({'type': 'sources', 'sources': sources_payload, 'meta': {'retrieve_ms': retrieve_ms, 'min_relevance': threshold, 'best_score': best, 'abstained': False}})}\n\n"

    context = build_context(chunks)
    try:
        client, model = _client_and_model()
    except RuntimeError as exc:
        payload = {
            "type": "error",
            "message": str(exc),
            "sources": _sources_payload(chunks),
            "meta": {"retrieve_ms": retrieve_ms, "llm_ms": 0, "total_ms": retrieve_ms},
        }
        yield f"data: {json.dumps(payload)}\n\n"
        return

    temp = settings.temperature if temperature is None else temperature

    t1 = time.perf_counter()
    try:
        stream = client.chat.completions.create(
            model=model,
            temperature=temp,
            messages=_messages(question, context),
            stream=True,
        )

        answer_parts: list[str] = []
        for event in stream:
            delta = event.choices[0].delta.content or ""
            if not delta:
                continue
            answer_parts.append(delta)
            yield f"data: {json.dumps({'type': 'token', 'token': delta})}\n\n"
    except Exception as exc:  # noqa: BLE001
        payload = {
            "type": "error",
            "message": f"LLM failed: {exc}",
            "sources": _sources_payload(chunks),
            "meta": {
                "retrieve_ms": retrieve_ms,
                "llm_ms": 0,
                "total_ms": int((time.perf_counter() - t0) * 1000),
            },
        }
        yield f"data: {json.dumps(payload)}\n\n"
        return

    llm_ms = int((time.perf_counter() - t1) * 1000)
    total_ms = int((time.perf_counter() - t0) * 1000)
    final = {
        "type": "final",
        "answer": "".join(answer_parts),
        "sources": _sources_payload(chunks),
        "meta": {
            "retrieve_ms": retrieve_ms,
            "llm_ms": llm_ms,
            "total_ms": total_ms,
            "model": model,
            "abstained": False,
            "best_score": max(c.score for c in chunks),
            "min_relevance": threshold,
        },
    }
    yield f"data: {json.dumps(final)}\n\n"
