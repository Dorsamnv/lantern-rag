import { useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from "react";
import {
  ChatMessage,
  DocItem,
  Source,
  chatStream,
  clearDocuments,
  deleteDocument,
  getDocuments,
  getHealth,
  seedDocuments,
  transcribeAudio,
  uploadDocuments,
} from "./api";
import {
  micRecordSupported,
  speakText,
  speechSupported,
  startMicRecording,
  stopSpeaking,
  type MicRecorder,
} from "./voice";

const SUGGESTIONS = [
  "What is few-shot learning?",
  "What challenges exist in Visual Question Answering?",
  "How does Lantern generate answers?",
  "What is self-attention in Transformers?",
  "Explain Retrieval-Augmented Generation in one paragraph.",
  "What is the difference between precision and recall?",
];

function uid() {
  return crypto.randomUUID();
}

function scoreTone(score: number) {
  if (score >= 0.72) return "high";
  if (score >= 0.55) return "mid";
  return "low";
}

/** Lightweight markdown-ish renderer (bold, code, lists, citations). */
function renderAnswer(text: string, onCiteClick?: (sourceId: string) => void): ReactNode[] {
  const lines = text.split("\n");
  const nodes: ReactNode[] = [];

  lines.forEach((line, li) => {
    const bullet = line.match(/^[-*]\s+(.*)$/);
    const content = bullet ? bullet[1] : line;
    const parts = content.split(/(`[^`]+`|\*\*[^*]+\*\*|\[\s*S\d+\s*\])/g).filter(Boolean);
    const rendered = parts.map((part, i) => {
      if (part.startsWith("`") && part.endsWith("`")) {
        return (
          <code key={`${li}-${i}`} className="inline-code">
            {part.slice(1, -1)}
          </code>
        );
      }
      if (part.startsWith("**") && part.endsWith("**")) {
        return <strong key={`${li}-${i}`}>{part.slice(2, -2)}</strong>;
      }
      const cite = part.match(/^\[\s*(S\d+)\s*\]$/i);
      if (cite) {
        const sourceId = cite[1].toUpperCase();
        return (
          <button
            key={`${li}-${i}`}
            type="button"
            className="cite-chip"
            title={`Open ${sourceId}`}
            onClick={() => onCiteClick?.(sourceId)}
          >
            {sourceId}
          </button>
        );
      }
      return <span key={`${li}-${i}`}>{part}</span>;
    });

    if (bullet) {
      nodes.push(
        <li key={`l-${li}`} className="md-li">
          {rendered}
        </li>
      );
    } else if (line.trim() === "") {
      nodes.push(<div key={`b-${li}`} className="md-break" />);
    } else {
      nodes.push(
        <p key={`p-${li}`} className="md-p">
          {rendered}
        </p>
      );
    }
  });

  const out: ReactNode[] = [];
  let bucket: ReactNode[] = [];
  const flush = () => {
    if (bucket.length) {
      out.push(
        <ul key={`ul-${out.length}`} className="md-ul">
          {bucket}
        </ul>
      );
      bucket = [];
    }
  };
  nodes.forEach((n) => {
    if (typeof n === "object" && n && "props" in n && (n as { props?: { className?: string } }).props?.className === "md-li") {
      bucket.push(n);
    } else {
      flush();
      out.push(n);
    }
  });
  flush();
  return out;
}

function SourceCard({
  source,
  open,
  highlighted,
  onToggle,
  cardRef,
}: {
  source: Source;
  open: boolean;
  highlighted: boolean;
  onToggle: () => void;
  cardRef?: (el: HTMLElement | null) => void;
}) {
  return (
    <article
      ref={cardRef}
      className={`source-card tone-${scoreTone(source.score)} ${highlighted ? "highlight" : ""}`}
      id={`source-${source.id}`}
    >
      <button type="button" className="source-head" onClick={onToggle}>
        <span className="source-id">{source.id}</span>
        <span className="source-meta">
          <strong>{source.filename}</strong>
          {source.page ? <em>p. {source.page}</em> : null}
        </span>
        <span className="source-score">{Math.round(source.score * 100)}%</span>
        <span className="chev">{open ? "▾" : "▸"}</span>
      </button>
      {open ? (
        <div className="source-body-wrap">
          <div className="score-bar" style={{ width: `${Math.round(source.score * 100)}%` }} />
          <p className="source-body">{source.text}</p>
        </div>
      ) : null}
    </article>
  );
}

function MessageSources({
  messageId,
  sources,
  focusId,
  onFocused,
}: {
  messageId: string;
  sources: Source[];
  focusId: string | null;
  onFocused: () => void;
}) {
  const [openMap, setOpenMap] = useState<Record<string, boolean>>({});
  const [highlightId, setHighlightId] = useState<string | null>(null);
  const refs = useRef<Record<string, HTMLElement | null>>({});

  useEffect(() => {
    if (!focusId) return;
    setOpenMap((prev) => ({ ...prev, [focusId]: true }));
    setHighlightId(focusId);
    const el = refs.current[focusId];
    window.setTimeout(() => {
      el?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }, 30);
    onFocused();
    const clear = window.setTimeout(() => setHighlightId(null), 1800);
    return () => window.clearTimeout(clear);
    // intentionally only react to focusId changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusId]);

  return (
    <div className="sources" data-message={messageId}>
      <h4>Sources</h4>
      {sources.map((s) => (
        <SourceCard
          key={s.chunk_id}
          source={s}
          open={Boolean(openMap[s.id])}
          highlighted={highlightId === s.id}
          onToggle={() => setOpenMap((prev) => ({ ...prev, [s.id]: !prev[s.id] }))}
          cardRef={(el) => {
            refs.current[s.id] = el;
          }}
        />
      ))}
    </div>
  );
}

export default function App() {
  const [docs, setDocs] = useState<DocItem[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [topK, setTopK] = useState(4);
  const [temperature, setTemperature] = useState(0.2);
  const [minRelevance, setMinRelevance] = useState(0.48);
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [seeding, setSeeding] = useState(false);
  const [status, setStatus] = useState("Connecting…");
  const [provider, setProvider] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [focusCite, setFocusCite] = useState<{ messageId: string; sourceId: string } | null>(null);
  const [aboutOpen, setAboutOpen] = useState(false);
  const [listening, setListening] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [speakingId, setSpeakingId] = useState<string | null>(null);
  const [autoSpeak, setAutoSpeak] = useState(true);
  const [voiceOk] = useState(() => speechSupported());
  const bottomRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const recorderRef = useRef<MicRecorder | null>(null);

  const docCount = docs.length;
  const chunkCount = useMemo(() => docs.reduce((n, d) => n + d.chunks, 0), [docs]);

  async function refresh() {
    try {
      const [health, docRes] = await Promise.all([getHealth(), getDocuments()]);
      setDocs(docRes.documents);
      setProvider(`${health.provider} · ${health.model}`);
      setStatus(health.documents ? `${health.documents} docs indexed` : "Ready — upload documents");
    } catch {
      setStatus("Backend offline — start API on :8000");
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  useEffect(() => {
    if (!toast) return;
    const t = window.setTimeout(() => setToast(null), 3200);
    return () => window.clearTimeout(t);
  }, [toast]);

  useEffect(() => {
    if (!aboutOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setAboutOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [aboutOpen]);

  useEffect(() => {
    return () => {
      void recorderRef.current?.stop().catch(() => undefined);
      stopSpeaking();
    };
  }, []);

  async function stopListening() {
    const recorder = recorderRef.current;
    recorderRef.current = null;
    if (!recorder) {
      setListening(false);
      return;
    }
    setListening(false);
    const elapsed = Date.now() - recorder.startedAt;
    if (elapsed < 1600) {
      try {
        await recorder.stop();
      } catch {
        /* ignore */
      }
      setToast("Too short — speak 2–4 seconds, then Stop.");
      return;
    }
    setTranscribing(true);
    setToast("Transcribing… speak English clearly next time if this looks wrong");
    try {
      const blob = await recorder.stop();
      if (blob.size < 2500) {
        setToast("Audio too small — move closer to mic and retry.");
        return;
      }
      const text = await transcribeAudio(blob, "en");
      setInput(text);
      setToast("Check the text, edit if needed, then press Ask");
      // Do NOT auto-send — bad transcripts used to go straight into chat.
    } catch (err) {
      setToast(err instanceof Error ? err.message : "Transcription failed");
    } finally {
      setTranscribing(false);
    }
  }

  async function startListening() {
    if (!micRecordSupported()) {
      setToast("Microphone recording is not supported in this browser.");
      return;
    }
    stopSpeaking();
    setSpeakingId(null);
    try {
      recorderRef.current = await startMicRecording();
      setListening(true);
      setToast("Recording… speak clearly in English, then click Stop");
    } catch (err) {
      setListening(false);
      const msg = err instanceof Error ? err.message : "Could not start microphone.";
      setToast(msg.toLowerCase().includes("permission") ? "Allow microphone permission and retry." : msg);
    }
  }

  async function onSpeak(messageId: string, text: string) {
    if (speakingId === messageId) {
      stopSpeaking();
      setSpeakingId(null);
      return;
    }
    try {
      setSpeakingId(messageId);
      setToast("Speaking answer…");
      await speakText(text, "en-US");
      setSpeakingId(null);
    } catch (err) {
      setSpeakingId(null);
      setToast(err instanceof Error ? err.message : "Speech failed");
    }
  }

  async function handleUpload(files: FileList | File[] | null) {
    if (!files || files.length === 0) return;
    setUploading(true);
    try {
      const result = await uploadDocuments(files);
      const n = result.uploaded?.length ?? 0;
      const errN = result.errors?.length ?? 0;
      setToast(errN ? `Indexed ${n} file(s), ${errN} failed` : `Indexed ${n} document${n === 1 ? "" : "s"}`);
      await refresh();
    } catch (err) {
      setToast(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function onSeed() {
    setSeeding(true);
    try {
      const result = await seedDocuments();
      const n = result.uploaded?.length ?? 0;
      setToast(`Loaded ${n} sample document${n === 1 ? "" : "s"}`);
      await refresh();
    } catch (err) {
      setToast(err instanceof Error ? err.message : "Seed failed");
    } finally {
      setSeeding(false);
    }
  }

  async function onAsk(question: string) {
    const q = question.trim();
    if (!q || busy) return;
    setBusy(true);
    setInput("");
    const userMsg: ChatMessage = { id: uid(), role: "user", content: q };
    const pendingId = uid();
    setMessages((prev) => [
      ...prev,
      userMsg,
      { id: pendingId, role: "assistant", content: "", pending: true, sources: [] },
    ]);

    try {
      await chatStream(
        q,
        topK,
        temperature,
        {
          onSources: (sources, meta) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === pendingId
                  ? {
                      ...m,
                      sources,
                      meta,
                      content: meta?.abstained
                        ? "Low relevance — abstaining…"
                        : m.content || "Writing grounded answer…",
                    }
                  : m
              )
            );
          },
          onToken: (token) => {
            setMessages((prev) =>
              prev.map((m) => {
                if (m.id !== pendingId) return m;
                const next = (m.content === "Writing grounded answer…" ? "" : m.content) + token;
                return { ...m, content: next, pending: true };
              })
            );
          },
          onFinal: (answer, sources, meta) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === pendingId
                  ? { id: pendingId, role: "assistant", content: answer, sources, meta, pending: false }
                  : m
              )
            );
            if (autoSpeak && answer && !meta?.abstained) {
              void onSpeak(pendingId, answer);
            } else if (autoSpeak && meta?.abstained) {
              void onSpeak(pendingId, "I could not find enough relevant evidence in the documents.");
            }
          },
        },
        minRelevance
      );
    } catch (err) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === pendingId
            ? {
                id: pendingId,
                role: "assistant",
                content: err instanceof Error ? err.message : "Something went wrong.",
                error: true,
                pending: false,
              }
            : m
        )
      );
    } finally {
      setBusy(false);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void onAsk(input);
  }

  async function onDelete(docId: string) {
    await deleteDocument(docId);
    await refresh();
    setToast("Document removed");
  }

  async function onClear() {
    if (!window.confirm("Clear the entire document library?")) return;
    await clearDocuments();
    await refresh();
    setToast("Library cleared");
  }

  async function copyText(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      setToast("Copied to clipboard");
    } catch {
      setToast("Copy failed");
    }
  }

  return (
    <div className="shell">
      <div className="glow glow-a" aria-hidden />
      <div className="glow glow-b" aria-hidden />
      <div className="grid-overlay" aria-hidden />

      <header className="topbar">
        <div className="brand">
          <div className="mark" aria-hidden>
            <span />
          </div>
          <div>
            <p className="eyebrow">English-first RAG research assistant</p>
            <h1>Lantern</h1>
          </div>
        </div>
        <div className="top-actions">
          <button type="button" className="ghost" onClick={() => setAboutOpen(true)}>
            About
          </button>
          <button type="button" className="ghost" onClick={() => setSidebarOpen((v) => !v)}>
            {sidebarOpen ? "Hide library" : "Show library"}
          </button>
          <div className="status-pill">
            <span className={`dot ${status.includes("offline") ? "bad" : "ok"}`} />
            <div>
              <strong>{status}</strong>
              <small>{provider || "waiting for backend"}</small>
            </div>
          </div>
        </div>
      </header>

      <main className={`layout ${sidebarOpen ? "" : "library-collapsed"}`}>
        {sidebarOpen ? (
          <aside className="panel library">
            <div className="panel-head">
              <h2>Library</h2>
              <span>
                {docCount} docs · {chunkCount} chunks
              </span>
            </div>

            <div
              className={`dropzone ${dragOver ? "active" : ""} ${uploading ? "busy" : ""}`}
              onDragEnter={(e) => {
                e.preventDefault();
                setDragOver(true);
              }}
              onDragOver={(e) => e.preventDefault()}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragOver(false);
                void handleUpload(e.dataTransfer.files);
              }}
            >
              <div className="drop-icon" aria-hidden>
                ⇪
              </div>
              <p>Drop English PDF / TXT / Markdown</p>
              <div className="drop-actions">
                <button type="button" onClick={() => fileRef.current?.click()} disabled={uploading}>
                  {uploading ? "Indexing…" : "Browse files"}
                </button>
                <button type="button" className="ghost solid" onClick={() => void onSeed()} disabled={seeding || uploading}>
                  {seeding ? "Seeding…" : "Load samples"}
                </button>
              </div>
              <input
                ref={fileRef}
                type="file"
                hidden
                multiple
                accept=".pdf,.txt,.md,.markdown"
                onChange={(e) => void handleUpload(e.target.files)}
              />
            </div>

            <ul className="doc-list">
              {docs.length === 0 ? (
                <li className="empty">
                  No documents yet. Click <strong>Load samples</strong> or upload your own files.
                </li>
              ) : (
                docs.map((doc, idx) => (
                  <li key={doc.doc_id} style={{ animationDelay: `${idx * 40}ms` }}>
                    <div>
                      <strong>{doc.filename}</strong>
                      <small>
                        {doc.chunks} chunks · {(doc.chars / 1000).toFixed(1)}k chars
                      </small>
                    </div>
                    <button type="button" className="ghost" onClick={() => void onDelete(doc.doc_id)}>
                      Remove
                    </button>
                  </li>
                ))
              )}
            </ul>

            <div className="settings">
              <label>
                <span>Top-K passages</span>
                <input type="range" min={1} max={8} value={topK} onChange={(e) => setTopK(Number(e.target.value))} />
                <em>{topK}</em>
              </label>
              <label>
                <span>Temperature</span>
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.05}
                  value={temperature}
                  onChange={(e) => setTemperature(Number(e.target.value))}
                />
                <em>{temperature.toFixed(2)}</em>
              </label>
              <label>
                <span>Min relevance (abstain below)</span>
                <input
                  type="range"
                  min={0.2}
                  max={0.8}
                  step={0.01}
                  value={minRelevance}
                  onChange={(e) => setMinRelevance(Number(e.target.value))}
                />
                <em>{minRelevance.toFixed(2)}</em>
              </label>
              <label className="check-row">
                <input
                  type="checkbox"
                  checked={autoSpeak}
                  disabled={!voiceOk}
                  onChange={(e) => setAutoSpeak(e.target.checked)}
                />
                <span>Auto-speak answers (English)</span>
              </label>
              <button type="button" className="ghost danger" onClick={() => void onClear()} disabled={!docs.length}>
                Clear library
              </button>
            </div>
          </aside>
        ) : null}

        <section className="panel chat">
          <div className="panel-head">
            <div>
              <h2>Ask with sources</h2>
              <span>Streamed answers grounded in retrieved passages</span>
            </div>
            <div className="head-actions">
              <button type="button" className="ghost" disabled={!messages.length} onClick={() => setMessages([])}>
                New chat
              </button>
            </div>
          </div>

          <div className="transcript">
            {messages.length === 0 ? (
              <div className="hero-empty">
                <div className="hero-orb" aria-hidden />
                <h3>Ask your English documents with citations.</h3>
                <p>
                  Load the sample library, ask a question, and inspect retrieved sources with relevance scores.
                  Lantern is optimized for clean English demos.
                </p>
                <div className="suggestions">
                  {SUGGESTIONS.map((s) => (
                    <button key={s} type="button" onClick={() => void onAsk(s)} disabled={busy}>
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((m) => (
                <article
                  key={m.id}
                  className={`bubble ${m.role} ${m.pending ? "pending" : ""} ${m.error ? "error" : ""}`}
                >
                  <header>
                    <span>{m.role === "user" ? "You" : "Lantern"}</span>
                    {m.role === "assistant" && !m.pending && !m.error ? (
                      <div className="bubble-actions">
                        <button type="button" className="ghost tiny" onClick={() => void copyText(m.content)}>
                          Copy
                        </button>
                        {voiceOk ? (
                          <button
                            type="button"
                            className={`ghost tiny ${speakingId === m.id ? "active-voice" : ""}`}
                            onClick={() => void onSpeak(m.id, m.content)}
                          >
                            {speakingId === m.id ? "Stop" : "Speak"}
                          </button>
                        ) : null}
                      </div>
                    ) : null}
                  </header>
                  {m.role === "assistant" && !m.error ? (
                    <div className="answer-body">
                      {m.pending && !m.content ? (
                        <div className="typing">
                          <i />
                          <i />
                          <i />
                        </div>
                      ) : (
                        renderAnswer(m.content, (sourceId) => setFocusCite({ messageId: m.id, sourceId }))
                      )}
                      {m.pending && m.content ? <span className="caret" aria-hidden /> : null}
                    </div>
                  ) : (
                    <p>{m.content}</p>
                  )}
                  {m.meta?.abstained ? (
                    <div className="abstain-banner">
                      Abstained — best match {m.meta.best_score != null ? `${Math.round(m.meta.best_score * 100)}%` : "n/a"}
                      {m.meta.min_relevance != null ? ` (threshold ${Math.round(m.meta.min_relevance * 100)}%)` : ""}
                    </div>
                  ) : null}
                  {m.meta && (m.meta.total_ms || m.meta.retrieve_ms) ? (
                    <div className="meta-row">
                      {m.meta.retrieve_ms != null ? <span>retrieve {m.meta.retrieve_ms}ms</span> : null}
                      {m.meta.llm_ms != null ? <span>llm {m.meta.llm_ms}ms</span> : null}
                      {m.meta.total_ms != null ? <span>total {m.meta.total_ms}ms</span> : null}
                      {m.meta.model ? <span>{m.meta.model}</span> : null}
                      {m.meta.abstained ? <span>abstained</span> : null}
                    </div>
                  ) : null}
                  {m.sources && m.sources.length > 0 ? (
                    <MessageSources
                      messageId={m.id}
                      sources={m.sources}
                      focusId={focusCite?.messageId === m.id ? focusCite.sourceId : null}
                      onFocused={() => setFocusCite(null)}
                    />
                  ) : null}
                </article>
              ))
            )}
            <div ref={bottomRef} />
          </div>

          <form className="composer" onSubmit={onSubmit}>
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={
                listening
                  ? "Recording… click Mic again to stop"
                  : transcribing
                    ? "Transcribing with Whisper…"
                    : "Ask in English about your uploaded documents…"
              }
              rows={2}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void onAsk(input);
                }
              }}
            />
            <div className="composer-actions">
              {voiceOk ? (
                <button
                  type="button"
                  className={`ghost mic ${listening ? "listening" : ""}`}
                  onClick={() => void (listening ? stopListening() : startListening())}
                  disabled={busy || transcribing}
                  title="Hold/record English question, click again to stop"
                >
                  {transcribing ? "…" : listening ? "Stop" : "Mic"}
                </button>
              ) : null}
              <button type="submit" disabled={busy || !input.trim()}>
                {busy ? "Streaming…" : "Ask"}
              </button>
            </div>
          </form>
        </section>
      </main>

      {toast ? <div className="toast">{toast}</div> : null}

      {aboutOpen ? (
        <div className="modal-backdrop" onClick={() => setAboutOpen(false)} role="presentation">
          <div
            className="about-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="about-title"
            onClick={(e) => e.stopPropagation()}
          >
            <header className="about-head">
              <div>
                <p className="eyebrow">How Lantern works</p>
                <h2 id="about-title">About this RAG assistant</h2>
              </div>
              <button type="button" className="ghost" onClick={() => setAboutOpen(false)}>
                Close
              </button>
            </header>
            <div className="about-body">
              <section>
                <h3>Pipeline</h3>
                <ol>
                  <li>Upload English PDF / TXT / Markdown files</li>
                  <li>Split by headings + paragraphs, then embed chunks locally</li>
                  <li>Retrieve top-k passages for each question</li>
                  <li>Stream an LLM answer grounded only in those passages</li>
                </ol>
              </section>
              <section>
                <h3>Trust features</h3>
                <ul>
                  <li>
                    <strong>Clickable citations</strong> — tap <code>[S1]</code> to open the matching source card
                  </li>
                  <li>
                    <strong>Relevance abstain</strong> — if the best match is below the threshold, Lantern refuses to invent an answer
                  </li>
                  <li>
                    <strong>Retrieval eval</strong> — sample corpus scored with hit@4 = 10/10
                  </li>
                </ul>
              </section>
              <section>
                <h3>Voice (English)</h3>
                <ul>
                  <li>
                    <strong>Mic</strong> — record a question, then Whisper (Groq) transcribes it
                  </li>
                  <li>
                    <strong>Speak</strong> — hear the answer aloud in the browser
                  </li>
                  <li>Uses your Groq API key (avoids Chrome Google STT “network” errors)</li>
                </ul>
              </section>
              <section>
                <h3>Best demo tips</h3>
                <p>Ask in English. Try “What is few-shot learning?” or “What is self-attention in Transformers?”</p>
                <p className="about-note">English-first by design. Non-English PDFs may retrieve weakly depending on extraction quality.</p>
              </section>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
