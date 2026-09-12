export type Source = {
  id: string;
  filename: string;
  page: number | null;
  score: number;
  text: string;
  chunk_id: string;
};

export type ChatMeta = {
  retrieve_ms?: number;
  llm_ms?: number;
  total_ms?: number;
  model?: string;
  abstained?: boolean;
  best_score?: number;
  min_relevance?: number;
};

export type DocItem = {
  doc_id: string;
  filename: string;
  chunks: number;
  chars: number;
  uploaded_at: string;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  meta?: ChatMeta;
  pending?: boolean;
  error?: boolean;
};

const API = "/api";

async function parseError(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (typeof data.detail === "string") return data.detail;
    return JSON.stringify(data.detail ?? data);
  } catch {
    return res.statusText || "Request failed";
  }
}

export async function getHealth() {
  const res = await fetch(`${API}/health`);
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<{
    status: string;
    app: string;
    provider: string;
    model: string;
    documents: number;
  }>;
}

export async function getDocuments(): Promise<{ documents: DocItem[] }> {
  const res = await fetch(`${API}/documents`);
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function uploadDocuments(files: FileList | File[]) {
  const form = new FormData();
  Array.from(files).forEach((f) => form.append("files", f));
  const res = await fetch(`${API}/documents/upload`, { method: "POST", body: form });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function seedDocuments() {
  const res = await fetch(`${API}/documents/seed`, { method: "POST" });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function deleteDocument(docId: string) {
  const res = await fetch(`${API}/documents/${docId}`, { method: "DELETE" });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function clearDocuments() {
  const res = await fetch(`${API}/documents`, { method: "DELETE" });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function transcribeAudio(blob: Blob, language = "en"): Promise<string> {
  const form = new FormData();
  const ext = blob.type.includes("mp4") ? "mp4" : blob.type.includes("ogg") ? "ogg" : "webm";
  form.append("file", blob, `speech.${ext}`);
  const res = await fetch(`${API}/transcribe?language=${encodeURIComponent(language)}`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(await parseError(res));
  const data = (await res.json()) as { text: string };
  return (data.text || "").trim();
}

type StreamHandlers = {
  onSources?: (sources: Source[], meta?: ChatMeta) => void;
  onToken?: (token: string) => void;
  onFinal?: (answer: string, sources: Source[], meta?: ChatMeta) => void;
};

export async function chatStream(
  question: string,
  topK: number,
  temperature: number,
  handlers: StreamHandlers,
  minRelevance?: number
): Promise<void> {
  const res = await fetch(`${API}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      top_k: topK,
      temperature,
      min_relevance: minRelevance,
    }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  if (!res.body) throw new Error("No stream body from server");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";

    for (const part of parts) {
      const line = part
        .split("\n")
        .map((l) => l.trim())
        .find((l) => l.startsWith("data:"));
      if (!line) continue;
      const raw = line.replace(/^data:\s*/, "");
      if (!raw) continue;
      const event = JSON.parse(raw) as {
        type: string;
        token?: string;
        answer?: string;
        message?: string;
        sources?: Source[];
        meta?: ChatMeta;
      };
      if (event.type === "sources") {
        handlers.onSources?.(event.sources ?? [], event.meta);
      } else if (event.type === "token" && event.token) {
        handlers.onToken?.(event.token);
      } else if (event.type === "error") {
        throw new Error(event.message || "LLM stream failed");
      } else if (event.type === "final") {
        handlers.onFinal?.(event.answer ?? "", event.sources ?? [], event.meta);
      }
    }
  }
}
