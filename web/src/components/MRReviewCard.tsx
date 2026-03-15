import { useState, useMemo } from "react";
import type { MRDiffFile, MRReviewData } from "../types";

interface MRReviewCardProps {
  mrData: MRReviewData;
  onApprove: () => void;
  onReject: (comment: string) => void;
}

function FileStatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    A: "bg-green-100 text-green-700",
    M: "bg-blue-100 text-blue-700",
    D: "bg-red-100 text-red-700",
    R: "bg-purple-100 text-purple-700",
  };
  return (
    <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${colors[status] || "bg-gray-100 text-gray-600"}`}>
      {status}
    </span>
  );
}

function DiffBlock({ patch }: { patch: string }) {
  const lines = patch.split("\n");
  const hunkStart = lines.findIndex((l) => l.startsWith("@@"));
  const displayLines = hunkStart >= 0 ? lines.slice(hunkStart) : lines;

  return (
    <pre className="text-[11px] leading-relaxed overflow-x-auto bg-gray-950 rounded-b p-3 max-h-[400px] overflow-y-auto font-mono">
      {displayLines.map((line, i) => {
        let cls = "text-gray-400";
        if (line.startsWith("+") && !line.startsWith("+++")) cls = "text-green-400";
        else if (line.startsWith("-") && !line.startsWith("---")) cls = "text-red-400";
        else if (line.startsWith("@@")) cls = "text-cyan-400";
        return (
          <div key={i} className={cls}>
            {line || " "}
          </div>
        );
      })}
    </pre>
  );
}

function FileItem({
  file,
  expanded,
  onToggle,
}: {
  file: MRDiffFile;
  expanded: boolean;
  onToggle: () => void;
}) {
  const fileName = file.path.split("/").pop() || file.path;
  const dirPath = file.path.includes("/") ? file.path.substring(0, file.path.lastIndexOf("/")) : "";

  return (
    <div className="border border-gray-200 rounded overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-gray-50 transition-colors"
      >
        <span className="text-gray-400 text-xs">{expanded ? "▼" : "▶"}</span>
        <FileStatusBadge status={file.status} />
        <span className="text-xs text-gray-500 truncate">{dirPath}/</span>
        <span className="text-xs font-medium text-gray-900">{fileName}</span>
        <span className="ml-auto flex gap-2 text-[11px] shrink-0">
          {file.additions > 0 && <span className="text-green-600">+{file.additions}</span>}
          {file.deletions > 0 && <span className="text-red-500">-{file.deletions}</span>}
        </span>
      </button>
      {expanded && file.patch && <DiffBlock patch={file.patch} />}
    </div>
  );
}

export function MRReviewCard({ mrData, onApprove, onReject }: MRReviewCardProps) {
  const [comment, setComment] = useState("");
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(new Set());
  const { diffFiles, diffLines } = mrData;

  const allPaths = useMemo(() => diffFiles.map((f) => f.path), [diffFiles]);
  const allExpanded = allPaths.length > 0 && allPaths.every((p) => expandedPaths.has(p));

  const toggleFile = (path: string) => {
    setExpandedPaths((prev) => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  };

  const toggleAll = () => {
    if (allExpanded) {
      setExpandedPaths(new Set());
    } else {
      setExpandedPaths(new Set(allPaths));
    }
  };

  const totalAdditions = diffFiles.reduce((sum, f) => sum + f.additions, 0);
  const totalDeletions = diffFiles.reduce((sum, f) => sum + f.deletions, 0);

  const handleReject = () => {
    const text = comment.trim();
    if (!text) return;
    setComment("");
    onReject(text);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleReject();
    }
  };

  return (
    <div className="border border-indigo-200 bg-indigo-50/50 rounded-lg mx-4 my-3 overflow-hidden flex flex-col max-h-[70vh]">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-indigo-100/60 border-b border-indigo-200 shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-indigo-600 text-sm">⎇</span>
          <span className="text-sm font-semibold text-indigo-900">Merge Request</span>
        </div>
        <div className="flex items-center gap-3 text-xs text-gray-600">
          <span>{diffFiles.length} {diffFiles.length === 1 ? "файл" : diffFiles.length < 5 ? "файла" : "файлов"}</span>
          <span className="text-green-600">+{totalAdditions}</span>
          <span className="text-red-500">-{totalDeletions}</span>
          <span className="text-gray-400">{diffLines} строк</span>
        </div>
      </div>

      {/* File list — scrollable */}
      <div className="px-4 py-3 space-y-1.5 overflow-y-auto min-h-0 flex-1">
        <div className="flex justify-end mb-1">
          <button
            onClick={toggleAll}
            className="text-[11px] text-indigo-600 hover:text-indigo-800"
          >
            {allExpanded ? "Свернуть все" : "Развернуть все"}
          </button>
        </div>
        {diffFiles.map((file) => (
          <FileItem
            key={file.path}
            file={file}
            expanded={expandedPaths.has(file.path)}
            onToggle={() => toggleFile(file.path)}
          />
        ))}
      </div>

      {/* Comment + Actions — fixed at bottom */}
      <div className="shrink-0 border-t border-indigo-200 bg-white">
        <div className="px-4 pt-3 pb-2">
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Комментарий (обязателен для отклонения)..."
            rows={2}
            className="w-full rounded border border-gray-300 px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent"
          />
        </div>
        <div className="flex gap-2 px-4 pb-4">
          <button
            onClick={onApprove}
            className="flex-1 rounded bg-green-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-green-700 transition-colors"
          >
            ✓ Approve & Merge
          </button>
          <button
            onClick={handleReject}
            disabled={!comment.trim()}
            className="flex-1 rounded bg-red-50 border border-red-300 px-4 py-2.5 text-sm font-medium text-red-700 hover:bg-red-100 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            ✗ Reject
          </button>
        </div>
      </div>
    </div>
  );
}
