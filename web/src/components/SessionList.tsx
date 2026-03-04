import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { getSessions } from "../api/sessions";

export function SessionList() {
  const { data: sessions, isLoading } = useQuery({
    queryKey: ["sessions"],
    queryFn: getSessions,
    refetchInterval: 10_000,
  });

  if (isLoading) {
    return null;
  }

  if (!sessions || sessions.length === 0) {
    return null;
  }

  return (
    <div className="mb-8">
      <h2 className="text-lg font-semibold text-gray-900 mb-3">
        Active Sessions
      </h2>
      <div className="space-y-2">
        {sessions.map((session) => (
          <Link
            key={session.id}
            to={`/chat/${session.id}`}
            className="block rounded border p-3 hover:bg-gray-50 transition-colors"
          >
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-gray-700">
                {session.id.slice(0, 8)}...
              </span>
              <span
                className={`text-xs px-2 py-0.5 rounded ${
                  session.status === "active"
                    ? "bg-green-100 text-green-700"
                    : "bg-gray-100 text-gray-500"
                }`}
              >
                {session.status}
              </span>
            </div>
            <p className="text-xs text-gray-400 mt-1">
              {new Date(session.created_at).toLocaleString()}
            </p>
          </Link>
        ))}
      </div>
    </div>
  );
}
