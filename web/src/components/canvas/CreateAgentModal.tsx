import { useState } from "react";

interface CreateAgentModalProps {
  onSubmit: (data: { name: string; system_prompt: string }) => void;
  onClose: () => void;
  defaultName: string;
}

export function CreateAgentModal({ onSubmit, onClose, defaultName }: CreateAgentModalProps) {
  const [name, setName] = useState(defaultName);
  const [systemPrompt, setSystemPrompt] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim() || !systemPrompt.trim()) return;
    onSubmit({ name: name.trim(), system_prompt: systemPrompt.trim() });
  }

  function handleBackdropClick(e: React.MouseEvent) {
    if (e.target === e.currentTarget) onClose();
  }

  const canSubmit = name.trim().length > 0 && systemPrompt.trim().length > 0;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={handleBackdropClick}
      role="presentation"
    >
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-6">
        <h2 className="text-lg font-semibold mb-4">Новый агент</h2>
        <form onSubmit={handleSubmit}>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Имя
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Например: Developer"
            autoFocus
            required
            maxLength={100}
          />

          <label className="block text-sm font-medium text-gray-700 mb-1 mt-3">
            Системный промпт
          </label>
          <textarea
            value={systemPrompt}
            onChange={(e) => setSystemPrompt(e.target.value)}
            className="w-full border border-gray-300 rounded px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500 resize-y"
            placeholder="Инструкции для агента..."
            rows={5}
            required
          />

          <div className="flex justify-end gap-2 mt-4">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm text-gray-700 border border-gray-300 rounded hover:bg-gray-50"
            >
              Отмена
            </button>
            <button
              type="submit"
              className="px-4 py-2 text-sm text-white bg-blue-600 rounded hover:bg-blue-700 disabled:opacity-50"
              disabled={!canSubmit}
            >
              Создать
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
