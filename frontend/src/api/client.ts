import type { ChatRequest, SSEEvent, SourceChunk } from "../types";

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const API_KEY = import.meta.env.VITE_API_KEY ?? "";

const headers = (): HeadersInit => ({
  "Content-Type": "application/json",
  ...(API_KEY ? { "X-API-Key": API_KEY } : {}),
});

export async function* streamChat(
  req: ChatRequest
): AsyncGenerator<SSEEvent, void, unknown> {
  const resp = await fetch(`${BASE_URL}/chat`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(req),
  });

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ error: resp.statusText }));
    throw new Error(err.error ?? "Chat request failed");
  }

  const reader = resp.body?.getReader();
  if (!reader) throw new Error("No response body");

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        try {
          const event: SSEEvent = JSON.parse(line.slice(6));
          yield event;
        } catch {
          // malformed SSE line — skip
        }
      }
    }
  }
}

export async function uploadFiles(
  files: File[],
  collectionName?: string
): Promise<{ results: Array<{ filename: string; chunks_ingested: number; status: string; error?: string }>; total_chunks: number }> {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  if (collectionName) form.append("collection_name", collectionName);

  const resp = await fetch(`${BASE_URL}/ingest`, {
    method: "POST",
    headers: API_KEY ? { "X-API-Key": API_KEY } : {},
    body: form,
  });

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ error: resp.statusText }));
    throw new Error(err.error ?? "Upload failed");
  }
  return resp.json();
}

export async function fetchHealth(): Promise<Record<string, unknown>> {
  const resp = await fetch(`${BASE_URL}/health`);
  return resp.json();
}

export type { SourceChunk };
