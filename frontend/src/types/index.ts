export type SourceType = "qdrant" | "web_search" | "url_fetch";

export interface SourceChunk {
  source: string;
  chunk_index: number | null;
  score: number;
  snippet: string;
  page: number | null;
  title: string | null;
  source_type: SourceType;
}

export type MessageRole = "user" | "assistant";

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  sources?: SourceChunk[];
  strategy?: string;
  isStreaming?: boolean;
  timestamp: number;
}

export interface ChatRequest {
  message: string;
  session_id: string;
  history: Array<{ role: MessageRole; content: string }>;
}

export interface SSEEvent {
  type: "sources" | "token" | "done";
  content?: string;
  sources?: SourceChunk[];
  strategy?: string;
}
