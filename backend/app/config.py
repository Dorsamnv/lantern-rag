"""Application settings."""
from functools import lru_cache
import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
UPLOAD_DIR = Path(os.environ.get("LANTERN_UPLOAD_DIR", str(DATA_DIR / "uploads")))
CHROMA_DIR = Path(os.environ.get("LANTERN_CHROMA_DIR", str(DATA_DIR / "chroma")))
SAMPLE_DIR = DATA_DIR / "sample_docs"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Lantern"
    api_prefix: str = "/api"

    # LLM: openai | groq | ollama
    llm_provider: str = "groq"
    llm_model: str = "llama-3.3-70b-versatile"
    openai_api_key: str = ""
    groq_api_key: str = ""
    ollama_base_url: str = "http://127.0.0.1:11434/v1"
    ollama_model: str = "llama3.2"

    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    chunk_size: int = 800
    chunk_overlap: int = 120
    top_k: int = 4
    temperature: float = 0.2
    # If best retrieved score is below this, abstain instead of calling the LLM.
    min_relevance: float = 0.48
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"


@lru_cache
def get_settings() -> Settings:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
