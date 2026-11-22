import { ChangeEvent, FormEvent, useEffect, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import { findCitationSpanRange } from "./citation";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString();

type PdfDocument = {
  id: string;
  name: string;
  page_count: number;
  pdf_url: string;
};

type Citation = {
  document_id: string;
  page_number: number;
  chunk_id: string;
  quote: string;
};

type Message = {
  role: "user" | "assistant";
  text: string;
  citations?: Citation[];
};

const API = "/api";

function App() {
  const [documents, setDocuments] = useState<PdfDocument[]>([]);
  const [selected, setSelected] = useState<PdfDocument | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const [page, setPage] = useState(1);
  const [pageCount, setPageCount] = useState(0);
  const [highlight, setHighlight] = useState("");
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [serviceWarning, setServiceWarning] = useState("");
  const [pdfError, setPdfError] = useState("");
  const [viewerWidth, setViewerWidth] = useState(680);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const pdfStageRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    void loadDocuments();
    void fetch(`${API}/health`)
      .then(async (response) => {
        const status = await response.json();
        if (status.missing_models?.length) {
          setServiceWarning(
            `Missing Ollama model${status.missing_models.length > 1 ? "s" : ""}: ${status.missing_models.join(", ")}. Pull model${status.missing_models.length > 1 ? "s" : ""} on the host to enable chat and ingestion.`,
          );
        } else if (status.ollama === "unavailable") {
          setServiceWarning(status.message);
        }
      })
      .catch(() => setServiceWarning("Backend is unavailable. Start the Docker Compose app."));
    const stage = pdfStageRef.current;
    if (!stage) return;
    const observer = new ResizeObserver(([entry]) => {
      setViewerWidth(Math.max(240, entry.contentRect.width - 42));
    });
    observer.observe(stage);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    if (!selected || !highlight) return;
    const timer = window.setTimeout(() => {
      const layer = document.querySelector(".react-pdf__Page__textContent");
      if (!layer) return;
      const spans = Array.from(layer.querySelectorAll("span"));
      spans.forEach((span) => span.classList.remove("citation-mark"));
      const range = findCitationSpanRange(
        spans.map((span) => span.textContent ?? ""),
        highlight,
      );
      if (range.length) {
        range.forEach((index) => spans[index].classList.add("citation-mark"));
        spans[range[0]].scrollIntoView({ behavior: "smooth", block: "center" });
        return;
      }
      setError("Citation text was not found on the cited page.");
    }, 350);
    return () => window.clearTimeout(timer);
  }, [selected, page, highlight, pageCount]);

  async function loadDocuments() {
    try {
      const response = await fetch(`${API}/documents`);
      if (!response.ok) throw new Error("Could not load documents.");
      const items: PdfDocument[] = await response.json();
      setDocuments(items);
      if (items.length && !selected) selectDocument(items[0]);
    } catch (reason) {
      setServiceWarning(reason instanceof Error ? reason.message : "Backend is unavailable.");
    }
  }

  function selectDocument(item: PdfDocument) {
    setSelected(item);
    setMessages([]);
    setPage(1);
    setPageCount(item.page_count);
    setHighlight("");
    setPdfError("");
    setError("");
  }

  async function uploadFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setUploading(true);
    setError("");
    try {
      const form = new FormData();
      form.append("file", file);
      const response = await fetch(`${API}/documents`, { method: "POST", body: form });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail ?? "Upload failed.");
      setDocuments((current) => [result, ...current]);
      selectDocument(result);
      setServiceWarning("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Upload failed.");
    } finally {
      setUploading(false);
    }
  }

  async function sendQuestion(event: FormEvent) {
    event.preventDefault();
    const prompt = question.trim();
    if (!prompt || !selected || loading) return;
    setQuestion("");
    setError("");
    setMessages((current) => [...current, { role: "user", text: prompt }]);
    setLoading(true);
    try {
      const response = await fetch(`${API}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ document_id: selected.id, question: prompt }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail ?? "Chat request failed.");
      setMessages((current) => [
        ...current,
        { role: "assistant", text: result.answer, citations: result.citations },
      ]);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Chat request failed.");
    } finally {
      setLoading(false);
    }
  }

  function openCitation(citation: Citation) {
    const doc = documents.find((item) => item.id === citation.document_id);
    if (doc && doc.id !== selected?.id) selectDocument(doc);
    setPage(citation.page_number);
    setHighlight(citation.quote);
    setError("");
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="#" aria-label="Papertrail home">
          <span className="brand-icon">P</span>
          <span>papertrail</span>
        </a>
        <div className="topbar-meta">
          <span className="status-dot" />
          <span>Private workspace</span>
          <span className="avatar">A</span>
        </div>
      </header>

      <div className="workspace">
        <section className="viewer-panel" aria-label="PDF document viewer">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">YOUR LIBRARY</p>
              <h1>Documents <span className="count-badge">{documents.length}</span></h1>
            </div>
            <button
              className="upload-button"
              onClick={() => fileInput.current?.click()}
              disabled={uploading}
            >
              <span>{uploading ? "Adding…" : "+ Add PDF"}</span>
            </button>
            <input
              ref={fileInput}
              className="visually-hidden"
              type="file"
              accept="application/pdf,.pdf"
              onChange={uploadFile}
            />
          </div>

          <div className="document-strip">
            {documents.map((doc) => (
              <button
                className={`document-chip ${selected?.id === doc.id ? "active" : ""}`}
                key={doc.id}
                onClick={() => selectDocument(doc)}
                title={doc.name}
              >
                <span className="pdf-icon">PDF</span>
                <span className="chip-name">{doc.name}</span>
              </button>
            ))}
            {!documents.length && <span className="empty-library">Add a PDF to get started</span>}
          </div>

          <div className="viewer-toolbar">
            <div className="file-title">
              <span className="file-glyph">▤</span>
              <span>{selected?.name ?? "No document selected"}</span>
            </div>
            {selected && (
              <div className="page-controls">
                <button
                  aria-label="Previous page"
                  disabled={page <= 1}
                  onClick={() => { setPage((value) => Math.max(1, value - 1)); setHighlight(""); }}
                >
                  ‹
                </button>
                <span><b>{page}</b> / {pageCount}</span>
                <button
                  aria-label="Next page"
                  disabled={page >= pageCount}
                  onClick={() => { setPage((value) => Math.min(pageCount, value + 1)); setHighlight(""); }}
                >
                  ›
                </button>
              </div>
            )}
          </div>

          <div className="pdf-stage" ref={pdfStageRef}>
            {selected ? (
              pdfError ? (
                <div className="viewer-empty"><span className="empty-icon">!</span><p>{pdfError}</p></div>
              ) : (
                <Document
                  file={selected.pdf_url}
                  onLoadSuccess={({ numPages }) => setPageCount(numPages)}
                  onLoadError={(reason) => setPdfError(reason.message)}
                  loading={<div className="viewer-empty">Opening document…</div>}
                  error={<div className="viewer-empty">Could not open this PDF.</div>}
                >
                  <Page pageNumber={page} width={viewerWidth} renderAnnotationLayer renderTextLayer />
                </Document>
              )
            ) : (
              <div className="viewer-empty">
                <span className="empty-icon">▤</span>
                <h2>Your reading space</h2>
                <p>Add a PDF and ask questions about it. Sources open here.</p>
                <button className="text-button" onClick={() => fileInput.current?.click()}>Choose a PDF <span>→</span></button>
              </div>
            )}
          </div>
          <div className="viewer-footer">
            <span>PDF viewer</span>
            {selected && <span>Page {page} of {pageCount}</span>}
          </div>
        </section>

        <section className="chat-panel" aria-label="Document chat">
          <div className="chat-heading">
            <div className="assistant-avatar">✳</div>
            <div className="assistant-title">
              <h2>Papertrail assistant</h2>
              <span><i /> Ready to explore your documents</span>
            </div>
            <button className="more-button" aria-label="More options">···</button>
          </div>

          <div className="chat-content">
            {serviceWarning && <div className="notice warning"><span>!</span>{serviceWarning}</div>}
            {!messages.length ? (
              <div className="welcome">
                <div className="welcome-symbol">✳</div>
                <p className="eyebrow">YOUR DOCUMENT, IN CONTEXT</p>
                <h2>A little less searching.<br /><em>A lot more understanding.</em></h2>
                <p className="welcome-copy">
                  Ask a question about your PDF. I’ll find the answer and show you exactly where it came from.
                </p>
                <div className="suggestions">
                  <button disabled={!selected} onClick={() => setQuestion("Summarize the main points of this document.")}>
                    <span>✦</span> Summarize the main points
                  </button>
                  <button disabled={!selected} onClick={() => setQuestion("What are the key findings?")}>
                    <span>⌕</span> Find the key findings
                  </button>
                  <button disabled={!selected} onClick={() => setQuestion("What evidence supports the main conclusion?")}>
                    <span>↗</span> Explore supporting evidence
                  </button>
                </div>
              </div>
            ) : (
              <div className="message-list">
                {messages.map((message, index) => (
                  <article className={`message ${message.role}`} key={`${index}-${message.text}`}>
                    {message.role === "assistant" && <div className="message-avatar">✳</div>}
                    <div className="message-body">
                      <p className="message-label">{message.role === "assistant" ? "PAPERTRAIL" : "YOU"}</p>
                      <div className="message-text">{message.text}</div>
                      {!!message.citations?.length && (
                        <div className="source-list">
                          <span className="source-label">SOURCES</span>
                          {message.citations.map((citation) => (
                            <button
                              className="source-chip"
                              key={citation.chunk_id}
                              onClick={() => openCitation(citation)}
                              title={citation.quote}
                            >
                              <span>▤</span> Page {citation.page_number} <b>↗</b>
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  </article>
                ))}
                {loading && <div className="thinking"><span /><span /><span /> Finding a grounded answer…</div>}
                <div ref={messagesEndRef} />
              </div>
            )}
          </div>

          {error && <div className="error-banner" role="alert">{error}</div>}
          <div className="composer-wrap">
            <form className="composer" onSubmit={sendQuestion}>
              <textarea
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder={selected ? "Ask anything about your document…" : "Add a PDF to start a conversation"}
                disabled={!selected || loading}
                rows={2}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    void sendQuestion(event);
                  }
                }}
              />
              <div className="composer-tools">
                <span><span className="lock-icon">⌑</span> Answers grounded in your PDF</span>
                <button type="submit" disabled={!selected || !question.trim() || loading} aria-label="Send message">↑</button>
              </div>
            </form>
            <p className="disclaimer">AI can make mistakes. Always check cited sources.</p>
          </div>
        </section>
      </div>
    </main>
  );
}

export default App;
