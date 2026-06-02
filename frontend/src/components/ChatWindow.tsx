import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { MessageBubble } from "./MessageBubble";
import { ThinkingIndicator } from "./ThinkingIndicator";
import { FileUpload } from "./FileUpload";
import { useChat } from "../hooks/useChat";

export function ChatWindow() {
  const { messages, sendMessage, clearHistory, isLoading, error } = useChat();
  const [input, setInput] = useState("");
  const [showUpload, setShowUpload] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const handleSubmit = () => {
    const text = input.trim();
    if (!text || isLoading) return;
    setInput("");
    sendMessage(text);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="flex flex-col h-screen bg-mst-dark text-white">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-mst-darker shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-mst-cyan/20 border border-mst-cyan/40 flex items-center justify-center">
            <span className="text-mst-cyan text-sm font-bold">M</span>
          </div>
          <div>
            <h1 className="font-semibold text-white tracking-wide">MST Buddy</h1>
            <p className="text-xs text-white/40 font-mono">MST Blockchain AI Assistant</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowUpload((v) => !v)}
            className="text-xs font-mono px-3 py-1.5 rounded-lg border border-white/20 text-white/60 hover:text-white hover:border-white/40 transition-colors"
          >
            {showUpload ? "← Chat" : "📄 Ingest"}
          </button>
          <button
            onClick={clearHistory}
            className="text-xs font-mono px-3 py-1.5 rounded-lg border border-white/20 text-white/60 hover:text-red-400 hover:border-red-400/40 transition-colors"
          >
            Clear
          </button>
        </div>
      </header>

      {/* Body */}
      <div className="flex-1 overflow-hidden flex">
        {showUpload ? (
          <div className="flex-1 p-6 overflow-y-auto">
            <h2 className="text-sm font-mono text-white/60 mb-4">Ingest MST Documents</h2>
            <FileUpload />
          </div>
        ) : (
          <div className="flex-1 flex flex-col overflow-hidden">
            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-4 md:px-8 py-6 space-y-2">
              {messages.length === 0 && (
                <div className="flex flex-col items-center justify-center h-full gap-4 text-center">
                  <div className="w-16 h-16 rounded-2xl bg-mst-cyan/10 border border-mst-cyan/20 flex items-center justify-center">
                    <span className="text-3xl">⛓️</span>
                  </div>
                  <div>
                    <h2 className="text-xl font-semibold text-white/80 mb-1">Ask MST Buddy</h2>
                    <p className="text-sm text-white/40 font-mono max-w-md">
                      Ask about staking, tokenomics, referral commissions, RapidDex V2, wallet setup, or any MST Blockchain topic.
                    </p>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mt-2 max-w-lg w-full">
                    {[
                      "How do I stake MST tokens?",
                      "What is my referral commission at level 3?",
                      "How do I add MST network to MetaMask?",
                      "What are the MST tokenomics?",
                    ].map((q) => (
                      <button
                        key={q}
                        onClick={() => sendMessage(q)}
                        className="text-xs font-mono text-left px-3 py-2 rounded-lg border border-white/10 text-white/50 hover:text-white hover:border-mst-cyan/40 transition-colors bg-white/5"
                      >
                        {q}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {messages.map((msg) => (
                <MessageBubble key={msg.id} message={msg} />
              ))}

              {isLoading && messages[messages.length - 1]?.role !== "assistant" && (
                <div className="flex justify-start">
                  <div className="bg-white/5 border border-white/10 rounded-2xl rounded-tl-sm">
                    <ThinkingIndicator />
                  </div>
                </div>
              )}

              {error && (
                <p className="text-xs text-red-400 font-mono text-center py-2">{error}</p>
              )}

              <div ref={bottomRef} />
            </div>

            {/* Input bar */}
            <div className="shrink-0 px-4 md:px-8 py-4 border-t border-white/10 bg-mst-darker">
              <div className="flex items-end gap-3 max-w-4xl mx-auto">
                <textarea
                  ref={textareaRef}
                  rows={1}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Ask about MST staking, tokenomics, RapidDex, referral structure…"
                  disabled={isLoading}
                  className="flex-1 resize-none bg-white/5 border border-white/20 rounded-xl px-4 py-3 text-sm font-mono text-white placeholder-white/30 focus:outline-none focus:border-mst-cyan/50 transition-colors min-h-[44px] max-h-32 overflow-y-auto disabled:opacity-50"
                  style={{ fieldSizing: "content" } as React.CSSProperties}
                />
                <button
                  onClick={handleSubmit}
                  disabled={isLoading || !input.trim()}
                  className="shrink-0 px-4 py-3 rounded-xl bg-mst-cyan/20 border border-mst-cyan/40 text-mst-cyan font-mono text-sm hover:bg-mst-cyan/30 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {isLoading ? "…" : "Send"}
                </button>
              </div>
              <p className="text-[10px] text-white/20 font-mono text-center mt-2">
                Enter to send · Shift+Enter for newline · MST Chain ID: 4545
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
