import { useState, useCallback, useRef, useEffect } from "react";
import { v4 as uuidv4 } from "uuid";
import { streamChat } from "../api/client";
import type { Message, SourceChunk } from "../types";

const SESSION_KEY = "mst_session_id";
const HISTORY_KEY = "mst_chat_history";
const MAX_STORED = 20;

function getSessionId(): string {
  let id = localStorage.getItem(SESSION_KEY);
  if (!id) {
    id = uuidv4();
    localStorage.setItem(SESSION_KEY, id);
  }
  return id;
}

function loadHistory(): Message[] {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveHistory(messages: Message[]): void {
  const recent = messages.slice(-MAX_STORED);
  localStorage.setItem(HISTORY_KEY, JSON.stringify(recent));
}

export function useChat() {
  const [messages, setMessages] = useState<Message[]>(loadHistory);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const sessionId = useRef(getSessionId());
  useEffect(() => {
    saveHistory(messages);
  }, [messages]);

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || isLoading) return;

    setError(null);
    const userMsg: Message = {
      id: uuidv4(),
      role: "user",
      content: text.trim(),
      timestamp: Date.now(),
    };

    const assistantId = uuidv4();
    const assistantMsg: Message = {
      id: assistantId,
      role: "assistant",
      content: "",
      isStreaming: true,
      timestamp: Date.now(),
    };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setIsLoading(true);

    const history = messages
      .filter((m) => !m.isStreaming)
      .map((m) => ({ role: m.role, content: m.content }));

    try {
      const stream = streamChat({
        message: text.trim(),
        session_id: sessionId.current,
        history,
      });

      let sources: SourceChunk[] = [];
      let strategy = "qdrant";
      let fullContent = "";

      for await (const event of stream) {
        if (event.type === "sources") {
          sources = event.sources ?? [];
          strategy = event.strategy ?? "qdrant";
        } else if (event.type === "token") {
          fullContent += event.content ?? "";
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, content: fullContent } : m
            )
          );
        } else if (event.type === "error") {
          fullContent = event.content ?? "The AI model returned an error. Please try again.";
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, content: fullContent } : m
            )
          );
        } else if (event.type === "done") {
          break;
        }
      }

      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? { ...m, content: fullContent, sources, strategy, isStreaming: false }
            : m
        )
      );
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Unknown error";
      setError(msg);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? { ...m, content: `Error: ${msg}`, isStreaming: false }
            : m
        )
      );
    } finally {
      setIsLoading(false);
    }
  }, [messages, isLoading]);

  const clearHistory = useCallback(() => {
    setMessages([]);
    localStorage.removeItem(HISTORY_KEY);
  }, []);

  return { messages, sendMessage, clearHistory, isLoading, error, sessionId: sessionId.current };
}
