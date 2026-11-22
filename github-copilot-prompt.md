# GitHub Copilot Build Prompt

Build a working web application for chatting with uploaded PDF documents. First inspect the existing repository, identify its framework and conventions, and preserve useful existing work. Then implement the application end to end, including tests and run instructions.

## Product

- Use a split-screen interface: PDF viewer on the left, chatbot on the right.
- Let users upload and select PDF documents.
- Let users ask questions about the selected document and receive answers grounded in its contents.
- Show clickable citations beside the answer's relevant claims.
- On citation click, keep the PDF viewer on the left, open the cited document if needed, navigate to the correct page, and highlight the cited text chunk.
- Clearly show when the document does not contain enough information. Never invent an answer or citation.
- Show useful loading, empty, and error states.

## Required technology

- Frontend: React, TypeScript, and JavaScript tooling appropriate to the existing repository.
- Backend: Python, LangChain, and LangGraph.
- PDF-to-text conversion: Microsoft's `markitdown` library.
- Embeddings: Ollama model `embeddinggemma-2:740m-mxfp8`.
- Chat model: Ollama model `gemma4:e2b-it-qat`.
- Run the frontend and backend in separate Docker containers.
- Ollama already runs on the host. Do not add an Ollama container or download model weights in Docker.

## PDF ingestion and citations

- Convert uploaded PDFs with MarkItDown. Preserve document identity and enough page/source metadata to map retrieved chunks to their original PDF pages.
- Split extracted text into searchable chunks with overlap. Store each chunk with stable document ID, page number, chunk ID, and source text.
- Use an appropriate vector store with persistence across backend restarts. Explain the selection in the README.
- Retrieve relevant chunks for each question and pass them to the chat model as the only factual source.
- Require structured citations containing document ID, page number, chunk ID, and cited text. Validate citations against retrieved chunks before returning them.
- Do not fabricate page numbers or cite text that is absent from the source.
- Use the PDF viewer's text layer to locate and highlight the cited passage. If MarkItDown alone cannot provide reliable page mapping or text highlighting, investigate and add the smallest suitable PDF parsing/viewer support while retaining MarkItDown as the required conversion step. Report any remaining limitations instead of claiming inaccurate highlighting.

## Architecture and runtime

- Keep frontend and backend responsibilities separate. Define and document the API contract.
- Provide Dockerfiles for both services and a Compose configuration to run them together. Compose must not start Ollama.
- Configure the backend container to reach host Ollama through `host.docker.internal`; account for Docker platforms that need an explicit host-gateway mapping.
- Make Ollama's base URL configurable through environment variables. Do not hard-code secrets or assume Ollama is available; return a clear actionable error when it cannot be reached.
- Keep uploaded files and vector data in documented persistent storage. Validate file type and size, use safe generated storage names, and handle malformed PDFs with clear errors.
- Do not add authentication unless the existing project or product requirements call for it.

## Workflow

1. Inspect the repository and report its existing structure and relevant choices.
2. Ask concise questions only when a decision blocks correct implementation. Otherwise use reasonable defaults, document them, and proceed.
3. Implement a minimal usable vertical slice: upload, ingest, chat, citations, page navigation, and highlight.
4. Add focused tests for ingestion metadata, citation validation, API behavior, and citation navigation/highlighting where the existing test setup supports them.
5. Run relevant tests, type checks, and builds. Fix failures caused by the implementation.
6. Document prerequisites, model names, host Ollama setup, commands to run both containers, persistence locations, API behavior, and known limitations.

## Acceptance criteria

- A user can upload a PDF, ask a question, and receive a grounded answer with clickable citations.
- Clicking a citation opens the correct document in the left viewer, navigates to the cited page, and highlights the cited passage when text is available.
- The backend container calls host Ollama using the configured URL; no Ollama container is created.
- Both app containers start through the documented Compose command.
- Missing Ollama, invalid PDFs, and unanswerable questions produce clear, non-misleading responses.
- Automated checks pass, and setup instructions match the implemented project.
