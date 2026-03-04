import type { Agent, AgentLink } from "../types";

interface AgentLinkListProps {
  links: AgentLink[];
  agents: Agent[];
  onDelete: (linkId: string) => void;
}

function agentName(agents: Agent[], agentId: string): string {
  const agent = agents.find((a) => a.id === agentId);
  return agent?.name ?? "Unknown";
}

export function AgentLinkList({ links, agents, onDelete }: AgentLinkListProps) {
  if (links.length === 0) {
    return <p className="text-sm text-gray-500">No links yet.</p>;
  }

  return (
    <div className="border rounded-lg overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-gray-50">
          <tr>
            <th className="text-left px-4 py-2 font-medium text-gray-600">From</th>
            <th className="text-left px-4 py-2 font-medium text-gray-600">To</th>
            <th className="text-left px-4 py-2 font-medium text-gray-600">Type</th>
            <th className="text-right px-4 py-2 font-medium text-gray-600"></th>
          </tr>
        </thead>
        <tbody>
          {links.map((link) => (
            <tr key={link.id} className="border-t">
              <td className="px-4 py-2">{agentName(agents, link.from_agent_id)}</td>
              <td className="px-4 py-2">{agentName(agents, link.to_agent_id)}</td>
              <td className="px-4 py-2">
                <span className="bg-gray-100 text-gray-600 px-2 py-0.5 rounded text-xs">
                  {link.link_type}
                </span>
              </td>
              <td className="px-4 py-2 text-right">
                <button
                  onClick={() => onDelete(link.id)}
                  className="text-gray-400 hover:text-red-500 text-sm"
                >
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
