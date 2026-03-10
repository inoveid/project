import { useState } from "react";
import type { Agent, AgentPrompt, AgentUpdate } from "../../../types";

interface AgentPromptsTabProps {
  agent: Agent;
  onSave: (data: AgentUpdate) => void;
}

export function AgentPromptsTab({ agent, onSave }: AgentPromptsTabProps) {
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editName, setEditName] = useState("");
  const [editContent, setEditContent] = useState("");

  const prompts: AgentPrompt[] = agent.prompts ?? [];

  const startEdit = (index: number) => {
    const prompt = prompts[index];
    if (!prompt) return;
    setEditingIndex(index);
    setEditName(prompt.name);
    setEditContent(prompt.content);
  };

  const startCreate = () => {
    setEditingIndex(-1);
    setEditName("");
    setEditContent("");
  };

  const cancelEdit = () => {
    setEditingIndex(null);
    setEditName("");
    setEditContent("");
  };

  const saveEdit = () => {
    if (!editName.trim()) return;

    const updated = [...prompts];
    const newPrompt: AgentPrompt = { name: editName.trim(), content: editContent };

    if (editingIndex === -1) {
      updated.push(newPrompt);
    } else if (editingIndex !== null) {
      updated[editingIndex] = newPrompt;
    }

    onSave({ prompts: updated });
    cancelEdit();
  };

  const deletePrompt = (index: number) => {
    const updated = prompts.filter((_, i) => i !== index);
    onSave({ prompts: updated });
  };

  return (
    <div className="flex flex-col gap-3">
      {prompts.map((prompt, idx) => (
        <div
          key={`${prompt.name}-${idx}`}
          className="border border-gray-200 rounded p-3"
        >
          {editingIndex === idx ? (
            <PromptEditor
              name={editName}
              content={editContent}
              onNameChange={setEditName}
              onContentChange={setEditContent}
              onSave={saveEdit}
              onCancel={cancelEdit}
            />
          ) : (
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-gray-800">{prompt.name}</span>
              <div className="flex gap-2">
                <button
                  type="button"
                  className="text-xs text-blue-600 hover:text-blue-700"
                  onClick={() => startEdit(idx)}
                >
                  Edit
                </button>
                <button
                  type="button"
                  className="text-xs text-red-600 hover:text-red-700"
                  onClick={() => deletePrompt(idx)}
                >
                  Delete
                </button>
              </div>
            </div>
          )}
        </div>
      ))}

      {editingIndex === -1 ? (
        <div className="border border-gray-200 rounded p-3">
          <PromptEditor
            name={editName}
            content={editContent}
            onNameChange={setEditName}
            onContentChange={setEditContent}
            onSave={saveEdit}
            onCancel={cancelEdit}
          />
        </div>
      ) : (
        <button
          type="button"
          className="text-sm text-blue-600 hover:text-blue-700 text-left"
          onClick={startCreate}
        >
          + Add prompt
        </button>
      )}

      {prompts.length === 0 && editingIndex === null && (
        <p className="text-xs text-gray-400">No prompts yet</p>
      )}
    </div>
  );
}

function PromptEditor({
  name,
  content,
  onNameChange,
  onContentChange,
  onSave,
  onCancel,
}: {
  name: string;
  content: string;
  onNameChange: (v: string) => void;
  onContentChange: (v: string) => void;
  onSave: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="flex flex-col gap-2">
      <input
        type="text"
        placeholder="Prompt name"
        className="border border-gray-200 rounded px-2 py-1 text-sm"
        value={name}
        onChange={(e) => onNameChange(e.target.value)}
      />
      <textarea
        placeholder="Prompt content"
        className="border border-gray-200 rounded px-2 py-1 text-sm resize-y min-h-[80px] font-mono text-xs"
        value={content}
        onChange={(e) => onContentChange(e.target.value)}
      />
      <div className="flex gap-2">
        <button
          type="button"
          className="text-xs bg-blue-600 text-white rounded px-3 py-1 hover:bg-blue-700"
          onClick={onSave}
        >
          Save
        </button>
        <button
          type="button"
          className="text-xs text-gray-500 hover:text-gray-700"
          onClick={onCancel}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
