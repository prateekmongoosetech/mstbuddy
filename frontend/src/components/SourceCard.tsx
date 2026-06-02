import { useState } from "react";
import type { SourceChunk } from "../types";

const FAVICON_URL = (domain: string) =>
  `https://www.google.com/s2/favicons?domain=${domain}&sz=16`;

function getDomain(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}

function ScoreBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color = score >= 0.8 ? "bg-green-500" : score >= 0.6 ? "bg-yellow-500" : "bg-red-400";
  return (
    <div className="flex items-center gap-2 mt-1">
      <div className="flex-1 h-1 bg-white/10 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-mono text-white/50">{pct}%</span>
    </div>
  );
}

function SourceBadge({ type }: { type: SourceChunk["source_type"] }) {
  const styles: Record<SourceChunk["source_type"], string> = {
    qdrant: "bg-teal-900/60 text-teal-300 border-teal-700/50",
    web_search: "bg-blue-900/60 text-blue-300 border-blue-700/50",
    url_fetch: "bg-purple-900/60 text-purple-300 border-purple-700/50",
  };
  const labels: Record<SourceChunk["source_type"], string> = {
    qdrant: "🗂️ Knowledge base",
    web_search: "🌐 Live from web",
    url_fetch: "🔗 Fetched from link",
  };
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded border font-mono ${styles[type]}`}>
      {labels[type]}
    </span>
  );
}

interface Props {
  source: SourceChunk;
  index: number;
}

export function SourceCard({ source, index }: Props) {
  const [expanded, setExpanded] = useState(false);
  const domain = getDomain(source.source);

  return (
    <div className="border border-white/10 rounded-lg bg-white/5 hover:bg-white/8 transition-colors text-sm overflow-hidden">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full text-left px-3 py-2 flex items-start gap-2"
      >
        <span className="text-white/40 font-mono text-xs mt-0.5 shrink-0">[{index + 1}]</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <img
              src={FAVICON_URL(domain)}
              alt=""
              className="w-3 h-3 opacity-70"
              onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
            />
            <span className="font-medium text-white/80 truncate max-w-[200px]">
              {source.title ?? domain}
            </span>
            <SourceBadge type={source.source_type} />
            {source.page && (
              <span className="text-white/40 text-xs font-mono">p.{source.page}</span>
            )}
          </div>
          <p className="text-white/50 text-xs mt-0.5 truncate">{source.source}</p>
          <ScoreBar score={source.score} />
        </div>
        <span className="text-white/30 text-xs mt-0.5 shrink-0">
          {expanded ? "▲" : "▼"}
        </span>
      </button>

      {expanded && (
        <div className="px-3 pb-3 border-t border-white/10">
          <p className="text-white/60 text-xs font-mono leading-relaxed mt-2 whitespace-pre-wrap">
            {source.snippet || "(no snippet)"}
          </p>
        </div>
      )}
    </div>
  );
}
