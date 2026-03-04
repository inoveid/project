interface SummaryCardsProps {
  teamsCount: number;
  agentsCount: number;
  activeSessionsCount: number;
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="bg-white rounded-lg border p-4">
      <p className="text-sm text-gray-500">{label}</p>
      <p className="text-2xl font-bold text-gray-900 mt-1">{value}</p>
    </div>
  );
}

export function SummaryCards({
  teamsCount,
  agentsCount,
  activeSessionsCount,
}: SummaryCardsProps) {
  return (
    <div className="grid gap-4 sm:grid-cols-3 mb-8">
      <StatCard label="Teams" value={teamsCount} />
      <StatCard label="Agents" value={agentsCount} />
      <StatCard label="Active Sessions" value={activeSessionsCount} />
    </div>
  );
}
