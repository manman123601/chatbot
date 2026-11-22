import io
import os
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATA_DIR"] = tempfile.mkdtemp()
from app import main

client = TestClient(main.app)


def test_upload_rejects_non_pdf():
    response = client.post(
        "/api/documents",
        files={"file": ("file.txt", io.BytesIO(b"not a pdf"), "text/plain")},
    )

    assert response.status_code == 400


def test_upload_persists_page_mapping_and_pdf(monkeypatch):
    monkeypatch.setattr(main, "extract_pdf_pages", lambda path: ("converted", ["page one"]))
    monkeypatch.setattr(
        main,
        "make_documents",
        lambda document_id, pages: [],
    )

    class Store:
        def add_documents(self, documents):
            assert documents == []

    monkeypatch.setattr(main, "vector_store", lambda: Store())
    response = client.post(
        "/api/documents",
        files={"file": ("source.pdf", io.BytesIO(b"%PDF-1.7\ncontent"), "application/pdf")},
    )

    assert response.status_code == 200
    document = response.json()
    assert document["name"] == "source.pdf"
    assert document["page_count"] == 1
    pdf_response = client.get(document["pdf_url"])
    assert pdf_response.status_code == 200
    assert pdf_response.content.startswith(b"%PDF-")


def test_chat_rejects_unknown_document():
    response = client.post(
        "/api/chat", json={"document_id": "missing", "question": "What is this?"}
    )

    assert response.status_code == 404
