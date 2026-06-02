import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { SourceCard } from "./SourceCard";
import type { Message } from "../types";

interface Props {
  message: Message;
}

export function MessageBubble({ message }: Props) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
      <div className={`max-w-[85%] ${isUser ? "order-1" : "order-2"}`}>
        {isUser ? (
          <div className="bg-mst-cyan/20 border border-mst-cyan/30 rounded-2xl rounded-tr-sm px-4 py-3 text-white font-mono text-sm">
            {message.content}
          </div>
        ) : (
          <div className="space-y-2">
            <div className="bg-white/5 border border-white/10 rounded-2xl rounded-tl-sm px-4 py-3">
              {message.isStreaming && !message.content ? null : (
                <div className="prose prose-invert prose-sm max-w-none
                  prose-code:text-mst-cyan prose-code:bg-white/10 prose-code:px-1 prose-code:rounded
                  prose-pre:bg-white/5 prose-pre:border prose-pre:border-white/10
                  prose-a:text-mst-cyan prose-headings:text-white/90">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {message.content}
                  </ReactMarkdown>
                </div>
              )}
              {message.isStreaming && (
                <span className="inline-block w-2 h-4 bg-mst-cyan animate-pulse ml-0.5 align-middle" />
              )}
            </div>

            {message.sources && message.sources.length > 0 && (
              <div className="space-y-1">
                <p className="text-xs text-white/30 font-mono px-1">
                  {message.sources.length} source{message.sources.length !== 1 ? "s" : ""} retrieved
                  {message.strategy && message.strategy !== "qdrant" && (
                    <span className="ml-2 text-mst-cyan/50">· {message.strategy}</span>
                  )}
                </p>
                {message.sources.map((s, i) => (
                  <SourceCard key={`${s.source}-${i}`} source={s} index={i} />
                ))}
              </div>
            )}
          </div>
        )}

        <p className="text-[10px] text-white/20 font-mono mt-1 px-1 text-right">
          {new Date(message.timestamp).toLocaleTimeString()}
        </p>
      </div>
    </div>
  );
}
