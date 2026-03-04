import { useParams } from "react-router-dom";

export function ChatPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">
        Chat {sessionId}
      </h1>
      <p className="text-gray-500">Chat page — coming soon.</p>
    </div>
  );
}
