"""Text extraction, chunking, embeddings, and Chroma persistence."""
from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer

from app.config import CHROMA_DIR, UPLOAD_DIR, get_settings


@dataclass
class DocumentInfo:
    doc_id: str
    filename: str
    path: str
    chunks: int
    uploaded_at: str
    chars: int


@dataclass
class RetrievedChunk:
    text: str
    filename: str
    page: int | None
    score: float
    chunk_id: str


_embedder: SentenceTransformer | None = None
_client: chromadb.PersistentClient | None = None


def _get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        settings = get_settings()
        _embedder = SentenceTransformer(settings.embedding_model)
    return _embedder


def _get_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(
            path=str(CHROMA_DIR),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
    return _client


def _collection():
    return _get_client().get_or_create_collection(
        name="lantern_docs",
        metadata={"hnsw:space": "cosine"},
    )


def _split_by_headings(text: str) -> list[tuple[str, str]]:
    """Split markdown/text into (heading_path, body) sections."""
    lines = text.splitlines()
    sections: list[tuple[str, str]] = []
    current_title = "Introduction"
    buf: list[str] = []
    heading_re = re.compile(r"^(#{1,6})\s+(.+?)\s*$")

    def flush() -> None:
        body = "\n".join(buf).strip()
        if body:
            sections.append((current_title, body))

    for line in lines:
        m = heading_re.match(line)
        if m:
            flush()
            current_title = m.group(2).strip()
            buf = []
        else:
            buf.append(line)
    flush()
    return sections or [("Document", text.strip())]


def _chunk_by_paragraphs(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Pack paragraphs into chunks near chunk_size, with soft overlap."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paras:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    def emit() -> None:
        nonlocal current, current_len
        if not current:
            return
        piece = "\n\n".join(current).strip()
        if piece:
            chunks.append(piece)
        if overlap > 0 and piece:
            # keep tail for overlap continuity
            tail = piece[-overlap:].strip()
            current = [tail] if tail else []
            current_len = len(tail)
        else:
            current = []
            current_len = 0

    for para in paras:
        extra = len(para) + (2 if current else 0)
        if current and current_len + extra > chunk_size:
            emit()
        # if a single paragraph is huge, hard-split it
        if len(para) > chunk_size:
            if current:
                emit()
            start = 0
            while start < len(para):
                end = min(start + chunk_size, len(para))
                if end < len(para):
                    br = para.rfind(" ", start + chunk_size // 2, end)
                    if br != -1:
                        end = br
                chunks.append(para[start:end].strip())
                start = max(end - overlap, start + 1) if end < len(para) else end
            current = []
            current_len = 0
            continue
        current.append(para)
        current_len += extra

    if current:
        piece = "\n\n".join(current).strip()
        if piece:
            chunks.append(piece)
    return chunks


def _chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Heading-aware chunking with paragraph packing fallback."""
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        return []

    chunks: list[str] = []
    for title, body in _split_by_headings(text):
        prefix = f"## {title}\n\n" if title else ""
        parts = _chunk_by_paragraphs(body, max(chunk_size - len(prefix), 200), overlap)
        if not parts:
            continue
        for part in parts:
            chunk = f"{prefix}{part}".strip()
            if chunk:
                chunks.append(chunk)
    return chunks


def extract_pdf_pages(path: Path) -> list[tuple[int, str]]:
    reader = PdfReader(str(path))
    pages: list[tuple[int, str]] = []
    for i, page in enumerate(reader.pages, start=1):
        raw = page.extract_text() or ""
        cleaned = raw.strip()
        if cleaned:
            pages.append((i, cleaned))
    return pages


def extract_text_file(path: Path) -> list[tuple[int | None, str]]:
    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    return [(None, text)] if text else []


def list_documents() -> list[DocumentInfo]:
    col = _collection()
    if col.count() == 0:
        return []

    result = col.get(include=["metadatas"])
    by_doc: dict[str, dict[str, Any]] = {}
    for meta in result.get("metadatas") or []:
        if not meta:
            continue
        doc_id = meta.get("doc_id")
        if not doc_id:
            continue
        entry = by_doc.setdefault(
            doc_id,
            {
                "filename": meta.get("filename", "unknown"),
                "path": meta.get("path", ""),
                "uploaded_at": meta.get("uploaded_at", ""),
                "chars": 0,
                "chunks": 0,
            },
        )
        entry["chunks"] += 1
        entry["chars"] += int(meta.get("chars", 0))

    docs = [
        DocumentInfo(
            doc_id=doc_id,
            filename=data["filename"],
            path=data["path"],
            chunks=data["chunks"],
            uploaded_at=data["uploaded_at"],
            chars=data["chars"],
        )
        for doc_id, data in by_doc.items()
    ]
    docs.sort(key=lambda d: d.uploaded_at, reverse=True)
    return docs


def delete_document(doc_id: str) -> bool:
    col = _collection()
    existing = col.get(where={"doc_id": doc_id}, include=["metadatas"])
    ids = existing.get("ids") or []
    if not ids:
        return False
    col.delete(ids=ids)

    metas = existing.get("metadatas") or []
    paths = {m.get("path") for m in metas if m and m.get("path")}
    for p in paths:
        path = Path(p)
        if path.exists() and UPLOAD_DIR in path.resolve().parents:
            try:
                path.unlink()
            except OSError:
                pass
    return True


def clear_all() -> None:
    client = _get_client()
    try:
        client.delete_collection("lantern_docs")
    except Exception:
        pass
    _collection()
    for path in UPLOAD_DIR.glob("*"):
        if path.is_file():
            try:
                path.unlink()
            except OSError:
                pass


def ingest_file(path: Path, original_name: str | None = None) -> DocumentInfo:
    settings = get_settings()
    filename = original_name or path.name
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        pages = extract_pdf_pages(path)
    elif suffix in {".txt", ".md", ".markdown"}:
        pages = extract_text_file(path)
    else:
        raise ValueError("Unsupported file type. Use PDF, TXT, or Markdown.")

    if not pages:
        raise ValueError("No extractable text found in this file.")

    doc_id = hashlib.sha1(f"{filename}-{uuid.uuid4()}".encode()).hexdigest()[:16]
    uploaded_at = datetime.now(timezone.utc).isoformat()

    chunk_ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict[str, Any]] = []

    for page, page_text in pages:
        for chunk in _chunk_text(page_text, settings.chunk_size, settings.chunk_overlap):
            chunk_ids.append(str(uuid.uuid4()))
            documents.append(chunk)
            metadatas.append(
                {
                    "doc_id": doc_id,
                    "filename": filename,
                    "path": str(path.resolve()),
                    "page": page if page is not None else -1,
                    "uploaded_at": uploaded_at,
                    "chars": len(chunk),
                }
            )

    if not documents:
        raise ValueError("Document produced zero chunks.")

    embeddings = _get_embedder().encode(documents, show_progress_bar=False).tolist()
    _collection().add(
        ids=chunk_ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    return DocumentInfo(
        doc_id=doc_id,
        filename=filename,
        path=str(path.resolve()),
        chunks=len(documents),
        uploaded_at=uploaded_at,
        chars=sum(len(d) for d in documents),
    )


def retrieve(query: str, top_k: int | None = None) -> list[RetrievedChunk]:
    settings = get_settings()
    k = top_k or settings.top_k
    col = _collection()
    if col.count() == 0:
        return []

    q_emb = _get_embedder().encode([query], show_progress_bar=False).tolist()
    result = col.query(
        query_embeddings=q_emb,
        n_results=min(k, col.count()),
        include=["documents", "metadatas", "distances"],
    )

    docs = (result.get("documents") or [[]])[0]
    metas = (result.get("metadatas") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]
    ids = (result.get("ids") or [[]])[0]

    chunks: list[RetrievedChunk] = []
    for text, meta, dist, chunk_id in zip(docs, metas, distances, ids):
        # cosine distance → similarity-ish score in 0..1
        score = max(0.0, min(1.0, 1.0 - float(dist)))
        page_raw = meta.get("page", -1)
        page = None if page_raw in (-1, None) else int(page_raw)
        chunks.append(
            RetrievedChunk(
                text=text,
                filename=meta.get("filename", "unknown"),
                page=page,
                score=round(score, 3),
                chunk_id=chunk_id,
            )
        )
    return chunks
