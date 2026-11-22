# Papertrail PDF Chat

React + TypeScript frontend and Python FastAPI backend. Microsoft's MarkItDown conversion is stored with each document; page-bounded text is indexed for retrieval. PyMuPDF preserves page metadata so citations can point to the source page; the frontend uses PDF.js text spans to highlight the cited quote.

## Requirements

- Docker Desktop with Docker Compose
- Ollama running on the host
- Host Ollama models:

```powershell
ollama pull gemma4:e2b-it-qat
ollama pull embeddinggemma-2:740m
```

The requested `embeddinggemma-2:740m-mxfp8` requires Apple's MLX runtime and cannot run in this Windows Ollama setup. Use `embeddinggemma-2:740m` instead, or set `EMBEDDING_MODEL` to another host-supported Ollama embedding model. The backend does not install or run Ollama.

## Run

From this directory:

```powershell
docker compose up --build -d
```

Open [http://localhost:5173](http://localhost:5173). API docs are at [http://localhost:8000/docs](http://localhost:8000/docs).

Docker Compose starts only the frontend and backend. The backend uses `host.docker.internal:11434` to reach host Ollama. Override `OLLAMA_BASE_URL`, `CHAT_MODEL`, `EMBEDDING_MODEL`, or `MAX_UPLOAD_MB` in a `.env` file if needed.

Persistent files and Chroma vector data live in `./data` and survive container restarts. Stop the app with `docker compose down`; this keeps persisted data.

## API

- `GET /api/health`: Ollama connectivity and configured model availability.
- `GET /api/documents`: list uploaded PDFs.
- `POST /api/documents`: upload one PDF as multipart field `file`.
- `GET /api/documents/{document_id}/file`: stream PDF bytes.
- `POST /api/chat`: JSON body `{"document_id":"…","question":"…"}`. Returns `{"answer":"…","citations":[{"document_id":"…","page_number":1,"chunk_id":"…","quote":"…"}]}`.

Uploads are limited to 50 MB by default. Scanned PDFs without selectable text need OCR before upload. Page highlights depend on exact selectable text being present in the PDF text layer.

## Tests

Backend: `cd backend; python -m pytest`

Frontend: `cd frontend; npm install; npm test; npm run build`
