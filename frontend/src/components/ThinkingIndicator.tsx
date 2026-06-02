export function ThinkingIndicator() {
  return (
    <div className="flex items-center gap-1 px-4 py-3">
      <span className="text-xs text-mst-cyan/60 mr-2 font-mono">MST Buddy is thinking</span>
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="w-1.5 h-1.5 rounded-full bg-mst-cyan animate-bounce"
          style={{ animationDelay: `${i * 0.15}s` }}
        />
      ))}
    </div>
  );
}
