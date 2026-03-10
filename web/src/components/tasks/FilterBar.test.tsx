import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { FilterBar } from './FilterBar';

const businesses = [
  { id: 'b-1', name: 'Business A' },
  { id: 'b-2', name: 'Business B' },
];

const products = [
  { id: 'p-1', name: 'Product X' },
  { id: 'p-2', name: 'Product Y' },
];

const teams = [
  { id: 't-1', name: 'Team Alpha' },
];

function getSelectByLabel(label: string): HTMLSelectElement {
  const labelEl = screen.getByText(`${label}:`);
  const select = labelEl.closest('label')?.querySelector('select');
  if (!select) throw new Error(`Select for ${label} not found`);
  return select;
}

describe('FilterBar', () => {
  it('renders all three selects', () => {
    render(
      <FilterBar
        businesses={businesses}
        products={products}
        teams={teams}
        filters={{ businessId: null, productId: null, teamId: null }}
        onBusinessChange={vi.fn()}
        onProductChange={vi.fn()}
        onTeamChange={vi.fn()}
      />,
    );
    expect(screen.getByText('Business:')).toBeInTheDocument();
    expect(screen.getByText('Product:')).toBeInTheDocument();
    expect(screen.getByText('Team:')).toBeInTheDocument();
  });

  it('calls onBusinessChange when business selected', () => {
    const onBusinessChange = vi.fn();
    render(
      <FilterBar
        businesses={businesses}
        products={[]}
        teams={[]}
        filters={{ businessId: null, productId: null, teamId: null }}
        onBusinessChange={onBusinessChange}
        onProductChange={vi.fn()}
        onTeamChange={vi.fn()}
      />,
    );
    fireEvent.change(getSelectByLabel('Business'), { target: { value: 'b-1' } });
    expect(onBusinessChange).toHaveBeenCalledWith('b-1');
  });

  it('disables product select when no business selected', () => {
    render(
      <FilterBar
        businesses={businesses}
        products={[]}
        teams={[]}
        filters={{ businessId: null, productId: null, teamId: null }}
        onBusinessChange={vi.fn()}
        onProductChange={vi.fn()}
        onTeamChange={vi.fn()}
      />,
    );
    expect(getSelectByLabel('Product')).toBeDisabled();
  });

  it('enables product select when business is selected', () => {
    render(
      <FilterBar
        businesses={businesses}
        products={products}
        teams={[]}
        filters={{ businessId: 'b-1', productId: null, teamId: null }}
        onBusinessChange={vi.fn()}
        onProductChange={vi.fn()}
        onTeamChange={vi.fn()}
      />,
    );
    expect(getSelectByLabel('Product')).not.toBeDisabled();
  });
});
