import { useParams } from "react-router-dom";

export function TeamPage() {
  const { id } = useParams<{ id: string }>();
  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Team {id}</h1>
      <p className="text-gray-500">Team page — coming soon.</p>
    </div>
  );
}
