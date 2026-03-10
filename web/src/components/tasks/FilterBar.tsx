interface FilterBarProps {
  businesses: Array<{ id: string; name: string }>;
  products: Array<{ id: string; name: string }>;
  teams: Array<{ id: string; name: string }>;
  filters: {
    businessId: string | null;
    productId: string | null;
    teamId: string | null;
  };
  onBusinessChange: (id: string) => void;
  onProductChange: (id: string) => void;
  onTeamChange: (id: string) => void;
}

export function FilterBar({
  businesses,
  products,
  teams,
  filters,
  onBusinessChange,
  onProductChange,
  onTeamChange,
}: FilterBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-3 px-4 py-3 border-b border-gray-200 bg-white">
      <FilterSelect
        label="Business"
        value={filters.businessId ?? ''}
        options={businesses.map((b) => ({ value: b.id, label: b.name }))}
        onChange={onBusinessChange}
        placeholder="Выбрать..."
      />

      <FilterSelect
        label="Product"
        value={filters.productId ?? ''}
        options={products.map((p) => ({ value: p.id, label: p.name }))}
        onChange={onProductChange}
        placeholder="Выбрать..."
        disabled={!filters.businessId}
      />

      <FilterSelect
        label="Team"
        value={filters.teamId ?? ''}
        options={teams.map((t) => ({ value: t.id, label: t.name }))}
        onChange={onTeamChange}
        placeholder="Все"
      />
    </div>
  );
}

interface FilterSelectProps {
  label: string;
  value: string;
  options: Array<{ value: string; label: string }>;
  onChange: (value: string) => void;
  placeholder: string;
  disabled?: boolean;
}

function FilterSelect({ label, value, options, onChange, placeholder, disabled }: FilterSelectProps) {
  return (
    <label className="flex items-center gap-1.5 text-sm text-gray-600">
      {label}:
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className="border border-gray-300 rounded px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100 disabled:text-gray-400"
      >
        <option value="">{placeholder}</option>
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </label>
  );
}
