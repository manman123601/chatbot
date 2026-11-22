import json
import os
from typing import Any, TypedDict

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langgraph.graph import END, START, StateGraph


def embeddings() -> OllamaEmbeddings:
    return OllamaEmbeddings(
        model=os.getenv("EMBEDDING_MODEL", "embeddinggemma-2:740m"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    )


def vector_store() -> Chroma:
    return Chroma(
        collection_name="pdf_chunks",
        embedding_function=embeddings(),
        persist_directory=os.getenv("DATA_DIR", "./data") + "/chroma",
    )


class ChatState(TypedDict, total=False):
    question: str
    document_id: str
    retrieved: list[Document]
    result: dict[str, Any]


def answer_question(question: str, document_id: str) -> dict[str, Any]:
    store = vector_store()
    model = ChatOllama(
        model=os.getenv("CHAT_MODEL", "gemma4:e2b-it-qat"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        temperature=0,
    )

    def retrieve(state: ChatState) -> dict[str, Any]:
        docs = store.similarity_search(
            state["question"], k=5, filter={"document_id": state["document_id"]}
        )
        return {"retrieved": docs}

    def respond(state: ChatState) -> dict[str, Any]:
        docs = state.get("retrieved", [])
        if not docs:
            return {
                "result": {
                    "answer": "I couldn't find supporting information in this document.",
                    "citations": [],
                }
            }
        context = [
            {
                "chunk_id": doc.metadata["chunk_id"],
                "page_number": doc.metadata["page_number"],
                "text": doc.page_content,
            }
            for doc in docs
        ]
        prompt = (
            "Answer using only the supplied PDF passages. If they do not contain the "
            "answer, say so and return no citations. Return only valid JSON with "
            'shape {"answer":"...", "citations":[{"chunk_id":"...",'
            '"quote":"exact copied passage"}]}. Cite every factual answer with an '
            "exact quote from a supplied passage. Do not invent quotes or page numbers.\n"
            f"Question: {state['question']}\nPassages: {json.dumps(context, ensure_ascii=False)}"
        )
        content = model.invoke(prompt).content
        if not isinstance(content, str):
            raise ValueError("The chat model returned an unsupported response.")
        start, end = content.find("{"), content.rfind("}")
        if start < 0 or end < start:
            raise ValueError("The chat model did not return valid JSON. Please retry.")
        try:
            data = json.loads(content[start : end + 1])
        except json.JSONDecodeError as error:
            raise ValueError("The chat model did not return valid JSON. Please retry.") from error
        if not isinstance(data, dict) or not isinstance(data.get("answer"), str):
            raise ValueError("The chat model returned an invalid answer.")
        citations = data.get("citations")
        if not isinstance(citations, list):
            raise ValueError("The chat model returned invalid citation data.")
        return {"result": {"answer": data["answer"], "raw_citations": citations}}

    graph = StateGraph(ChatState)
    graph.add_node("retrieve", retrieve)
    graph.add_node("respond", respond)
    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "respond")
    graph.add_edge("respond", END)
    final = graph.compile().invoke({"question": question, "document_id": document_id})
    result = final["result"]
    if "raw_citations" in result:
        from app.core import validate_citations

        result["citations"] = validate_citations(
            result.pop("raw_citations"), final.get("retrieved", []), document_id
        )
        if not result["citations"]:
            result["answer"] = "I couldn't verify a supporting passage in this document."
    return result
