import { useRef, useCallback } from "react";

export interface PromptVariable {
  label: string;
  value: string; // e.g. "{{task_title}}"
}

interface PromptEditorProps {
  value: string;
  onChange: (value: string) => void;
  onBlur?: () => void;
  variables?: PromptVariable[];
  placeholder?: string;
  rows?: number;
  disabled?: boolean;
}

const DEFAULT_VARIABLES: PromptVariable[] = [
  { label: "Название задачи", value: "{{task_title}}" },
  { label: "Описание задачи", value: "{{task_description}}" },
];

export function PromptEditor({
  value,
  onChange,
  onBlur,
  variables = DEFAULT_VARIABLES,
  placeholder = "Введите промпт...",
  rows = 3,
  disabled = false,
}: PromptEditorProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const insertVariable = useCallback(
    (variable: string) => {
      const textarea = textareaRef.current;
      if (!textarea || disabled) return;

      const start = textarea.selectionStart;
      const end = textarea.selectionEnd;
      const before = value.slice(0, start);
      const after = value.slice(end);
      const newValue = before + variable + after;
      onChange(newValue);

      // Restore cursor position after variable
      requestAnimationFrame(() => {
        const pos = start + variable.length;
        textarea.setSelectionRange(pos, pos);
        textarea.focus();
      });
    },
    [value, onChange, disabled],
  );

  return (
    <div className="space-y-1.5">
      {/* Variable chips */}
      {variables.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {variables.map((v) => (
            <button
              key={v.value}
              type="button"
              onClick={() => insertVariable(v.value)}
              disabled={disabled}
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-blue-50 text-blue-700 border border-blue-200 hover:bg-blue-100 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <span className="text-blue-400">+</span>
              {v.label}
            </button>
          ))}
        </div>
      )}

      {/* Textarea */}
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onBlur={onBlur}
        placeholder={placeholder}
        rows={rows}
        disabled={disabled}
        className="w-full border border-gray-200 rounded px-3 py-2 text-sm resize-y min-h-[60px] font-mono text-xs focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent disabled:opacity-60 disabled:cursor-not-allowed"
      />
    </div>
  );
}
