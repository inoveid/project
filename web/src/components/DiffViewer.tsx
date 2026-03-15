import { useState } from "react";
import type { DiffFile } from "../api/products";

interface DiffViewerProps {
  files: DiffFile[];
  totalAdditions: number;
  totalDeletions: number;
}

const STATUS_LABELS: Record<DiffFile["status"], string> = {
  modified: "Modified",
  added: "Added",
  deleted: "Deleted",
  renamed: "Renamed",
  binary: "Binary",
};

const STATUS_COLORS: Record<DiffFile["status"], string> = {
  modified: "text-yellow-600",
  added: "text-green-600",
  deleted: "text-red-600",
  renamed: "text-blue-600",
  binary: "text-gray-500",
};

function StatBar({ additions, deletions }: { additions: number; deletions: number }) {
  const total = additions + deletions;
  if (total === 0) return null;
  const max = 5;
  const addBlocks = Math.round((additions / total) * max);
  const delBlocks = max - addBlocks;
  return (
    <span className="inline-flex gap-px ml-2">
      {Array.from({ length: addBlocks }).map((_, i) => (
        <span key={`a${i}`} className="w-2 h-2 bg-green-500 rounded-sm" />
      ))}
      {Array.from({ length: delBlocks }).map((_, i) => (
        <span key={`d${i}`} className="w-2 h-2 bg-red-500 rounded-sm" />
      ))}
    </span>
  );
}

function FileHeader({
  file,
  expanded,
  onToggle,
}: {
  file: DiffFile;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className="w-full flex items-center gap-2 px-3 py-2 bg-gray-50 border-b hover:bg-gray-100 text-left"
    >
      <span className="text-gray-400 text-xs w-4">{expanded ? "▼" : "▶"}</span>
      <span className={`text-[10px] font-medium uppercase ${STATUS_COLORS[file.status]}`}>
        {STATUS_LABELS[file.status]}
      </span>
      <span className="text-sm font-mono truncate flex-1">{file.path}</span>
      {file.old_path && (
        <span className="text-xs text-gray-400">← {file.old_path}</span>
      )}
      {file.status !== "binary" && (file.additions > 0 || file.deletions > 0) && (
        <span className="text-xs text-gray-500 shrink-0">
          {file.additions > 0 && <span className="text-green-600">+{file.additions}</span>}
          {file.additions > 0 && file.deletions > 0 && " "}
          {file.deletions > 0 && <span className="text-red-600">-{file.deletions}</span>}
          <StatBar additions={file.additions} deletions={file.deletions} />
        </span>
      )}
    </button>
  );
}

function HunkView({ file }: { file: DiffFile }) {
  if (file.status === "binary") {
    return (
      <div className="px-4 py-3 text-sm text-gray-500 italic bg-gray-50">
        Binary file not shown.
      </div>
    );
  }

  if (file.hunks.length === 0) {
    return (
      <div className="px-4 py-3 text-sm text-gray-400 italic">
        No changes.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs font-mono border-collapse">
        <tbody>
          {file.hunks.map((hunk, hi) => (
            <HunkRows key={hi} hunk={hunk} hunkIndex={hi} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function HunkRows({ hunk, hunkIndex }: { hunk: DiffFile["hunks"][0]; hunkIndex: number }) {
  return (
    <>
      <tr className="bg-blue-50">
        <td colSpan={3} className="px-3 py-1 text-blue-700 text-[11px] select-none">
          {hunk.header}
        </td>
      </tr>
      {hunk.lines.map((line, li) => {
        const bgClass =
          line.type === "add"
            ? "bg-green-50"
            : line.type === "delete"
              ? "bg-red-50"
              : "";
        const textClass =
          line.type === "add"
            ? "text-green-800"
            : line.type === "delete"
              ? "text-red-800"
              : "text-gray-700";
        const numClass =
          line.type === "add"
            ? "bg-green-100 text-green-600"
            : line.type === "delete"
              ? "bg-red-100 text-red-600"
              : "bg-white text-gray-400";

        return (
          <tr key={`${hunkIndex}-${li}`} className={bgClass}>
            <td className={`w-[1px] whitespace-nowrap px-2 py-0 text-right select-none border-r ${numClass}`}>
              {line.old_no ?? ""}
            </td>
            <td className={`w-[1px] whitespace-nowrap px-2 py-0 text-right select-none border-r ${numClass}`}>
              {line.new_no ?? ""}
            </td>
            <td className={`px-3 py-0 whitespace-pre ${textClass}`}>
              {line.content}
            </td>
          </tr>
        );
      })}
    </>
  );
}

export function DiffViewer({ files, totalAdditions, totalDeletions }: DiffViewerProps) {
  const [expandedFiles, setExpandedFiles] = useState<Set<string>>(() => {
    const initial = new Set<string>();
    let count = 0;
    for (const f of files) {
      if (f.status !== "binary" && count < 5) {
        initial.add(f.path);
        count++;
      }
    }
    return initial;
  });

  const toggleFile = (path: string) => {
    setExpandedFiles((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  };

  const toggleAll = () => {
    if (expandedFiles.size === files.length) {
      setExpandedFiles(new Set());
    } else {
      setExpandedFiles(new Set(files.map((f) => f.path)));
    }
  };

  if (files.length === 0) {
    return (
      <div className="flex items-center justify-center h-32 text-gray-400 text-sm">
        Нет изменений
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      <div className="flex items-center gap-3 px-3 py-2 bg-white border-b sticky top-0 z-10">
        <span className="text-xs text-gray-600">
          Showing <b>{files.length}</b> changed file{files.length !== 1 ? "s" : ""}
        </span>
        <span className="text-xs">
          <span className="text-green-600 font-medium">+{totalAdditions}</span>
          {" "}
          <span className="text-red-600 font-medium">-{totalDeletions}</span>
        </span>
        <button
          type="button"
          onClick={toggleAll}
          className="ml-auto text-[10px] text-blue-600 hover:text-blue-800"
        >
          {expandedFiles.size === files.length ? "Свернуть все" : "Развернуть все"}
        </button>
      </div>

      <div className="divide-y">
        {files.map((file) => (
          <div key={file.path} className="border-b last:border-b-0">
            <FileHeader
              file={file}
              expanded={expandedFiles.has(file.path)}
              onToggle={() => toggleFile(file.path)}
            />
            {expandedFiles.has(file.path) && <HunkView file={file} />}
          </div>
        ))}
      </div>
    </div>
  );
}
