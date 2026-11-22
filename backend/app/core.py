import re
import uuid
from pathlib import Path
from typing import Any

import pymupdf
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from markitdown import MarkItDown


def extract_pdf_pages(path: Path) -> tuple[str, list[str]]:
    converted_text = MarkItDown().convert(str(path)).text_content
    if not converted_text.strip():
        raise ValueError("MarkItDown could not extract text from this PDF.")

    with pymupdf.open(path) as pdf:
        pages = [page.get_text("text").strip() for page in pdf]
    if not pages or not any(pages):
        raise ValueError(
            "This PDF has no selectable text. Scanned PDFs need OCR before upload."
        )
    return converted_text, pages


def make_documents(document_id: str, pages: list[str]) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150,
        add_start_index=True,
    )
    documents: list[Document] = []
    for page_number, text in enumerate(pages, start=1):
        if not text:
            continue
        page_documents = splitter.create_documents(
            [text],
            metadatas=[{"document_id": document_id, "page_number": page_number}],
        )
        for document in page_documents:
            document.metadata["chunk_id"] = str(uuid.uuid4())
            documents.append(document)
    if not documents:
        raise ValueError("No searchable text was found in this PDF.")
    return documents


def normalize_quote(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def validate_citations(
    raw_citations: Any, retrieved: list[Document], document_id: str
) -> list[dict[str, Any]]:
    if not isinstance(raw_citations, list):
        raise ValueError("The chat model returned invalid citation data.")

    by_chunk_id = {
        doc.metadata["chunk_id"]: doc
        for doc in retrieved
        if doc.metadata.get("document_id") == document_id
    }
    citations: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw_citations:
        if not isinstance(item, dict):
            raise ValueError("The chat model returned an invalid citation.")
        chunk_id, quote = item.get("chunk_id"), item.get("quote")
        if not isinstance(chunk_id, str) or not isinstance(quote, str) or not quote.strip():
            raise ValueError("The chat model returned an incomplete citation.")
        source = by_chunk_id.get(chunk_id)
        if source is None or normalize_quote(quote) not in normalize_quote(source.page_content):
            raise ValueError("The chat model cited text outside the retrieved source.")
        if chunk_id in seen:
            continue
        seen.add(chunk_id)
        citations.append(
            {
                "document_id": document_id,
                "page_number": source.metadata["page_number"],
                "chunk_id": chunk_id,
                "quote": quote.strip(),
            }
        )
    return citations
