import { useEffect, useState } from 'react';

interface ToastMessage {
  id: number;
  text: string;
  type: 'error' | 'success';
}

let toastId = 0;
let addToastFn: ((msg: Omit<ToastMessage, 'id'>) => void) | null = null;

export function showToast(text: string, type: 'error' | 'success' = 'error') {
  addToastFn?.({ text, type });
}

export function ToastContainer() {
  const [messages, setMessages] = useState<ToastMessage[]>([]);

  useEffect(() => {
    addToastFn = (msg) => {
      const id = ++toastId;
      setMessages((prev) => [...prev, { ...msg, id }]);
      setTimeout(() => {
        setMessages((prev) => prev.filter((m) => m.id !== id));
      }, 3000);
    };
    return () => {
      addToastFn = null;
    };
  }, []);

  if (messages.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 space-y-2">
      {messages.map((msg) => (
        <div
          key={msg.id}
          className={`px-4 py-2 rounded shadow-lg text-sm text-white ${
            msg.type === 'error' ? 'bg-red-600' : 'bg-green-600'
          }`}
        >
          {msg.text}
        </div>
      ))}
    </div>
  );
}
