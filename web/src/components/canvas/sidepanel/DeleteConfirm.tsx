import { useState } from "react";

interface DeleteConfirmProps {
  entityName: string;
  onConfirm: () => void;
  className?: string;
}

export function DeleteConfirm({ entityName, onConfirm, className = "" }: DeleteConfirmProps) {
  const [confirmed, setConfirmed] = useState(false);

  if (!confirmed) {
    return (
      <div className={`pt-4 border-t border-gray-100 ${className}`}>
        <button
          type="button"
          className="text-sm text-red-600 hover:text-red-700"
          onClick={() => setConfirmed(true)}
        >
          Удалить {entityName}
        </button>
      </div>
    );
  }

  return (
    <div className={`p-3 border border-red-200 rounded bg-red-50 space-y-2 ${className}`}>
      <p className="text-sm text-red-700">
        Удалить <b>{entityName}</b>? Это действие необратимо.
      </p>
      <div className="flex gap-2">
        <button
          type="button"
          className="text-sm bg-red-600 text-white rounded px-3 py-1 hover:bg-red-700"
          onClick={onConfirm}
        >
          Да, удалить
        </button>
        <button
          type="button"
          className="text-sm text-gray-500 hover:text-gray-700"
          onClick={() => setConfirmed(false)}
        >
          Отмена
        </button>
      </div>
    </div>
  );
}
