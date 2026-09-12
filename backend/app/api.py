from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.config import SAMPLE_DIR, UPLOAD_DIR, get_settings
from app.rag.qa import answer_question, stream_answer
from app.rag.store import clear_all, delete_document, ingest_file, list_documents
from app.rag.transcribe import transcribe_audio

router = APIRouter()


class ChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=4000)
    top_k: int | None = Field(default=None, ge=1, le=12)
    temperature: float | None = Field(default=None, ge=0, le=1)
    min_relevance: float | None = Field(default=None, ge=0, le=1)


@router.get("/health")
def health():
    settings = get_settings()
    key = settings.groq_api_key.strip()
    key_ok = bool(key) and key not in {"your_groq_key_here", "your_key_here"}
    return {
        "status": "ok",
        "app": settings.app_name,
        "provider": settings.llm_provider,
        "model": settings.llm_model if settings.llm_provider != "ollama" else settings.ollama_model,
        "documents": len(list_documents()),
        "groq_key_configured": key_ok if settings.llm_provider == "groq" else None,
    }


@router.get("/documents")
def get_documents():
    docs = list_documents()
    return {
        "documents": [
            {
                "doc_id": d.doc_id,
                "filename": d.filename,
                "chunks": d.chunks,
                "chars": d.chars,
                "uploaded_at": d.uploaded_at,
            }
            for d in docs
        ]
    }


def _ingest_upload(path: Path, original_name: str) -> dict:
    info = ingest_file(path, original_name=original_name)
    return {
        "doc_id": info.doc_id,
        "filename": info.filename,
        "chunks": info.chunks,
        "chars": info.chars,
        "uploaded_at": info.uploaded_at,
    }


@router.post("/documents/upload")
async def upload_documents(files: list[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    saved = []
    errors = []
    for file in files:
        name = file.filename or "upload.bin"
        suffix = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        if suffix not in {"pdf", "txt", "md", "markdown"}:
            errors.append({"filename": name, "error": "Unsupported type"})
            continue

        target = UPLOAD_DIR / name
        if target.exists():
            stem = target.stem
            target = UPLOAD_DIR / f"{stem}-{len(list(UPLOAD_DIR.glob('*')))}{target.suffix}"

        content = await file.read()
        if not content:
            errors.append({"filename": name, "error": "Empty file"})
            continue
        target.write_bytes(content)

        try:
            saved.append(_ingest_upload(target, name))
        except Exception as exc:  # noqa: BLE001
            errors.append({"filename": name, "error": str(exc)})
            if target.exists():
                target.unlink(missing_ok=True)

    if not saved and errors:
        raise HTTPException(status_code=400, detail=errors)

    return {"uploaded": saved, "errors": errors}


@router.post("/documents/seed")
def seed_sample_documents():
    """Index bundled demo markdown notes from data/sample_docs."""
    files = sorted(SAMPLE_DIR.glob("*"))
    files = [f for f in files if f.suffix.lower() in {".md", ".txt", ".markdown", ".pdf"}]
    if not files:
        raise HTTPException(status_code=404, detail="No sample documents found in data/sample_docs.")

    saved = []
    errors = []
    for src in files:
        target = UPLOAD_DIR / src.name
        if target.exists():
            stem = target.stem
            target = UPLOAD_DIR / f"{stem}-sample-{len(list(UPLOAD_DIR.glob('*')))}{target.suffix}"
        target.write_bytes(src.read_bytes())
        try:
            saved.append(_ingest_upload(target, src.name))
        except Exception as exc:  # noqa: BLE001
            errors.append({"filename": src.name, "error": str(exc)})
            target.unlink(missing_ok=True)

    if not saved:
        raise HTTPException(status_code=400, detail=errors or "Seeding failed.")
    return {"uploaded": saved, "errors": errors}


@router.delete("/documents/{doc_id}")
def remove_document(doc_id: str):
    ok = delete_document(doc_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"deleted": doc_id}


@router.delete("/documents")
def remove_all_documents():
    clear_all()
    return {"cleared": True}


@router.post("/chat")
def chat(body: ChatRequest):
    try:
        return answer_question(
            question=body.question.strip(),
            top_k=body.top_k,
            temperature=body.temperature,
            min_relevance=body.min_relevance,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Chat failed: {exc}") from exc


@router.post("/chat/stream")
def chat_stream(body: ChatRequest):
    from app.rag.qa import _client_and_model

    # Validate provider credentials before opening the SSE stream (unless library empty).
    if list_documents():
        try:
            _client_and_model()
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    generator = stream_answer(
        question=body.question.strip(),
        top_k=body.top_k,
        temperature=body.temperature,
        min_relevance=body.min_relevance,
    )
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/transcribe")
async def transcribe(file: UploadFile = File(...), language: str = "en"):
    """Speech-to-text via Groq Whisper (avoids Chrome Google STT network errors)."""
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty audio file.")
    name = file.filename or "audio.webm"
    try:
        text = transcribe_audio(data, filename=name, language=language or "en")
        return {"text": text}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Transcription failed: {exc}") from exc
