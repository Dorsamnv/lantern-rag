"""Speech-to-text via Groq Whisper (OpenAI-compatible audio API)."""
from __future__ import annotations

import io
import re

from openai import OpenAI

from app.config import get_settings

EN_PROMPT = (
    "English technical questions about machine learning, RAG, VQA, "
    "few-shot learning, transformers, CNNs, and precision recall."
)


def _groq_client() -> OpenAI:
    settings = get_settings()
    key = settings.groq_api_key.strip()
    if not key or key in {"your_groq_key_here", "your_key_here"}:
        raise RuntimeError(
            "GROQ_API_KEY is missing/invalid. Add a real key to rag-chatbot/.env for voice transcription."
        )
    return OpenAI(api_key=key, base_url="https://api.groq.com/openai/v1")


def _clean_transcript(text: str) -> str:
    text = (text or "").strip()
    text = re.sub(r"\s+", " ", text)
    # Drop obvious Whisper hallucination loops
    text = re.sub(r"(.{8,}?)(\1){2,}", r"\1", text)
    lowered = text.lower()
    junk = (
        "thanks for watching",
        "subscribe",
        "www.",
        "http",
        "♪",
        "🎵",
        "[music]",
        "(music)",
    )
    if any(j in lowered for j in junk) and len(text) < 80:
        return ""
    return text.strip(" \n\t.-")


def transcribe_audio(data: bytes, filename: str = "audio.webm", language: str = "en") -> str:
    if not data:
        raise ValueError("Empty audio upload.")
    if len(data) < 1500:
        raise ValueError("Recording too short. Speak for 2–4 seconds, then press Stop.")

    client = _groq_client()
    bio = io.BytesIO(data)
    bio.name = filename  # type: ignore[attr-defined]

    # Prefer full Whisper over turbo for short noisy mic clips.
    result = client.audio.transcriptions.create(
        model="whisper-large-v3",
        file=(filename, bio, "application/octet-stream"),
        language=language or "en",
        response_format="text",
        temperature=0,
        prompt=EN_PROMPT,
    )
    if isinstance(result, str):
        text = result
    else:
        text = getattr(result, "text", str(result))

    text = _clean_transcript(text)
    if not text:
        raise ValueError("Could not understand speech. Speak clearly in English and try again.")
    return text
