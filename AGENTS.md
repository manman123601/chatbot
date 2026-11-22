# Agent instructions

## Project

Papertrail is a local PDF question-answering app. The frontend is React and TypeScript in `frontend/`; the Python FastAPI and LangGraph backend is in `backend/`. Docker Compose runs those two services. Ollama runs on the host and must not be added as a Compose service.

Read `README.md` for setup, API, model, and runtime details before changing behavior.

## Preserve key behavior

- Keep the PDF viewer on the left and chat on the right. Citation clicks must select the cited document, navigate to its source page, and highlight its verified quote when the PDF text layer allows it.
- Convert PDFs with Microsoft's MarkItDown. Preserve document identity, page numbers, stable chunk IDs, and source text through retrieval and citations.
- Treat retrieved PDF passages as the only factual source for answers. Validate citation chunk IDs and quoted text against retrieved passages; do not fabricate citations.
- Keep document uploads and vector data persistent in `data/`. Do not commit uploaded PDFs, database files, model data, or other local runtime data.
- Configure backend-to-host Ollama access with `OLLAMA_BASE_URL`. Compose must not start Ollama or download its models.
- Preserve clear errors for unavailable Ollama or models, invalid PDFs, unsupported scanned PDFs, and unanswerable questions.
- Keep API paths and response shapes consistent with `README.md` and the frontend.

## Code conventions

- Follow existing language and framework patterns. Keep changes focused and update `README.md` when setup, API behavior, model configuration, or limitations change.
- Add focused tests for new behavior and regressions. Avoid unrelated refactors and unnecessary dependencies.
- Validate inputs at API boundaries. Use generated storage names instead of uploaded filenames for paths.
- Do not silently invent fallback answers, page numbers, or citations when a dependency or parsing step fails.
- Keep `.env`, user documents, and generated `data/` contents out of source control.

## Validation

Run relevant checks from the repository root:

```powershell
docker compose run --rm backend pytest -q
Set-Location frontend
npm test
npm run build
npm audit
```

For Docker/runtime changes, also run:

```powershell
Set-Location ..
docker compose config --quiet
docker compose up --build -d
docker compose ps
```

Check `GET /api/health` and `http://localhost:5173` when validating a local run. Do not remove or reset `data/` during testing; it contains persistent user documents and indexes.
