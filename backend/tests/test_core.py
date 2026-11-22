from langchain_core.documents import Document

from app.core import make_documents, normalize_quote, validate_citations


def test_make_documents_preserves_page_and_document_metadata():
    docs = make_documents("doc-1", ["Page one text.", "", "Page three text."])

    assert [doc.metadata["page_number"] for doc in docs] == [1, 3]
    assert all(doc.metadata["document_id"] == "doc-1" for doc in docs)
    assert all(doc.metadata["chunk_id"] for doc in docs)


def test_validate_citations_returns_only_verified_source_metadata():
    source = Document(
        page_content="Useful source text.",
        metadata={"document_id": "doc-1", "page_number": 2, "chunk_id": "chunk-1"},
    )

    citations = validate_citations(
        [{"chunk_id": "chunk-1", "quote": "Useful   source text."}],
        [source],
        "doc-1",
    )

    assert citations == [
        {
            "document_id": "doc-1",
            "page_number": 2,
            "chunk_id": "chunk-1",
            "quote": "Useful   source text.",
        }
    ]


def test_validate_citations_rejects_unretrieved_or_invented_quotes():
    source = Document(
        page_content="Verified source.",
        metadata={"document_id": "doc-1", "page_number": 1, "chunk_id": "chunk-1"},
    )

    try:
        validate_citations(
            [{"chunk_id": "chunk-1", "quote": "Invented source."}], [source], "doc-1"
        )
        assert False, "Expected citation validation to fail"
    except ValueError as error:
        assert "outside the retrieved source" in str(error)


def test_quote_normalization_collapses_whitespace():
    assert normalize_quote("A \n b") == "a b"
