import os
import sqlite3
import uuid
from contextlib import closing
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.core import extract_pdf_pages, make_documents
from app.rag import answer_question, vector_store

DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "documents.sqlite3"
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="PDF Chat API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def connect() -> sqlite3.Connection:
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


with closing(connect()) as db:
    db.execute(
        """CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, file_path TEXT NOT NULL,
            page_count INTEGER NOT NULL, converted_text TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    columns = {row["name"] for row in db.execute("PRAGMA table_info(documents)")}
    if "converted_text" not in columns:
        db.execute(
            "ALTER TABLE documents ADD COLUMN converted_text TEXT NOT NULL DEFAULT ''"
        )
    db.commit()


class ChatRequest(BaseModel):
    document_id: str
    question: str = Field(min_length=1, max_length=4000)


def document_record(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "page_count": row["page_count"],
        "pdf_url": f"/api/documents/{row['id']}/file",
    }


@app.get("/api/health")
def health() -> dict[str, Any]:
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    try:
        response = httpx.get(f"{base_url}/api/tags", timeout=2)
        response.raise_for_status()
        names = {model["name"] for model in response.json().get("models", [])}
        chat_model = os.getenv("CHAT_MODEL", "gemma4:e2b-it-qat")
        embedding_model = os.getenv("EMBEDDING_MODEL", "embeddinggemma-2:740m")
        return {
            "status": "ok",
            "ollama": "connected",
            "chat_model": chat_model,
            "embedding_model": embedding_model,
            "missing_models": [
                name for name in (chat_model, embedding_model) if name not in names
            ],
        }
    except (httpx.HTTPError, ValueError):
        return {
            "status": "degraded",
            "ollama": "unavailable",
            "message": f"Start Ollama and verify it is reachable at {base_url}.",
        }


@app.get("/api/documents")
def list_documents() -> list[dict[str, Any]]:
    with closing(connect()) as db:
        rows = db.execute("SELECT * FROM documents ORDER BY created_at DESC").fetchall()
    return [document_record(row) for row in rows]


@app.post("/api/documents")
async def upload_document(file: UploadFile = File(...)) -> dict[str, Any]:
    if not file.filename or Path(file.filename).suffix.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="Upload a PDF file.")
    max_bytes = int(os.getenv("MAX_UPLOAD_MB", "50")) * 1024 * 1024
    contents = await file.read(max_bytes + 1)
    if len(contents) > max_bytes:
        raise HTTPException(status_code=413, detail="PDF exceeds the upload size limit.")
    if not contents.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="The uploaded file is not a valid PDF.")

    document_id = str(uuid.uuid4())
    path = UPLOAD_DIR / f"{document_id}.pdf"
    path.write_bytes(contents)
    try:
        converted_text, pages = extract_pdf_pages(path)
        documents = make_documents(document_id, pages)
        store = vector_store()
        store.add_documents(documents)
    except ValueError as error:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:
        path.unlink(missing_ok=True)
        message = str(error)
        if "model" in message.lower() or "ollama" in message.lower() or "connection" in message.lower():
            raise HTTPException(
                status_code=503,
                detail=(
                    "Ollama is unavailable or a required model is missing. "
                    "Start Ollama and pull the configured embedding model."
                ),
            ) from error
        raise HTTPException(status_code=500, detail="PDF ingestion failed.") from error

    with closing(connect()) as db:
        db.execute(
            """INSERT INTO documents
            (id, name, file_path, page_count, converted_text) VALUES (?, ?, ?, ?, ?)""",
            (document_id, Path(file.filename).name, str(path), len(pages), converted_text),
        )
        db.commit()
        row = db.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
    return document_record(row)


@app.get("/api/documents/{document_id}/file")
def get_pdf(document_id: str) -> FileResponse:
    with closing(connect()) as db:
        row = db.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return FileResponse(row["file_path"], media_type="application/pdf")


@app.post("/api/chat")
def chat(request: ChatRequest) -> dict[str, Any]:
    with closing(connect()) as db:
        exists = db.execute(
            "SELECT 1 FROM documents WHERE id = ?", (request.document_id,)
        ).fetchone()
    if exists is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    try:
        return answer_question(request.question.strip(), request.document_id)
    except ValueError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=(
                "Chat service failed. Check that Ollama is running and both configured "
                "models are installed."
            ),
        ) from error
