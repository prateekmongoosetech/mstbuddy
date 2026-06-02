import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { uploadFiles } from "../api/client";

const ACCEPTED = {
  "application/pdf": [".pdf"],
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
  "text/plain": [".txt"],
  "text/markdown": [".md"],
  "application/json": [".json"],
};

interface UploadResult {
  filename: string;
  status: string;
  chunks_ingested: number;
  error?: string;
}

export function FileUpload() {
  const [results, setResults] = useState<UploadResult[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    if (!acceptedFiles.length) return;
    setUploading(true);
    setError(null);
    setResults([]);
    try {
      const resp = await uploadFiles(acceptedFiles);
      setResults(resp.results);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED,
    multiple: true,
    disabled: uploading,
  });

  return (
    <div className="space-y-3">
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors
          ${isDragActive ? "border-mst-cyan bg-mst-cyan/5" : "border-white/20 hover:border-white/40"}
          ${uploading ? "opacity-50 cursor-not-allowed" : ""}`}
      >
        <input {...getInputProps()} />
        <div className="flex flex-col items-center gap-2">
          <span className="text-3xl">📄</span>
          {uploading ? (
            <p className="text-sm text-mst-cyan font-mono animate-pulse">Ingesting documents…</p>
          ) : isDragActive ? (
            <p className="text-sm text-mst-cyan">Drop files here</p>
          ) : (
            <>
              <p className="text-sm text-white/70">Drag & drop documents or click to select</p>
              <p className="text-xs text-white/40 font-mono">PDF · DOCX · TXT · MD · JSON</p>
            </>
          )}
        </div>
      </div>

      {error && (
        <p className="text-xs text-red-400 font-mono px-1">{error}</p>
      )}

      {results.length > 0 && (
        <ul className="space-y-1">
          {results.map((r) => (
            <li key={r.filename} className="flex items-center gap-2 text-xs font-mono">
              <span>{r.status === "ok" ? "✅" : "❌"}</span>
              <span className="text-white/70 truncate">{r.filename}</span>
              {r.status === "ok" ? (
                <span className="text-mst-cyan ml-auto shrink-0">{r.chunks_ingested} chunks</span>
              ) : (
                <span className="text-red-400 ml-auto shrink-0 truncate max-w-[140px]">{r.error}</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
