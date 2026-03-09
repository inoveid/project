// Placeholder — full implementation in TASK-043
export function GlobalChatWidget() {
  return (
    <div className="fixed bottom-4 right-4 z-50">
      <button
        className="bg-blue-600 text-white rounded-full w-12 h-12 flex items-center justify-center shadow-lg hover:bg-blue-700 text-xl"
        title="Открыть чат"
        aria-label="Открыть чат"
      >
        💬
      </button>
    </div>
  );
}
