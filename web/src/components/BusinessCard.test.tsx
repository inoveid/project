import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { BusinessCard } from './BusinessCard';
import type { Business } from '../types';

const business: Business = {
  id: 'b-1',
  name: 'My Company',
  description: 'A great company',
  created_at: '2024-01-01T00:00:00Z',
  products_count: 3,
};

describe('BusinessCard', () => {
  it('renders business name and product count', () => {
    render(
      <BusinessCard
        business={business}
        onEdit={vi.fn()}
        onDelete={vi.fn()}
        onOpen={vi.fn()}
      />,
    );
    expect(screen.getByText('My Company')).toBeInTheDocument();
    expect(screen.getByText(/3 продукта/)).toBeInTheDocument();
  });

  it('renders description when present', () => {
    render(
      <BusinessCard business={business} onEdit={vi.fn()} onDelete={vi.fn()} onOpen={vi.fn()} />,
    );
    expect(screen.getByText('A great company')).toBeInTheDocument();
  });

  it('calls onOpen when Открыть button clicked', () => {
    const onOpen = vi.fn();
    render(
      <BusinessCard business={business} onEdit={vi.fn()} onDelete={vi.fn()} onOpen={onOpen} />,
    );
    fireEvent.click(screen.getByText(/Открыть/));
    expect(onOpen).toHaveBeenCalledWith('b-1');
  });

  it('calls onEdit when Edit button clicked', () => {
    const onEdit = vi.fn();
    render(
      <BusinessCard business={business} onEdit={onEdit} onDelete={vi.fn()} onOpen={vi.fn()} />,
    );
    fireEvent.click(screen.getByText('Edit'));
    expect(onEdit).toHaveBeenCalledWith(business);
  });

  it('calls onDelete when delete button clicked', () => {
    const onDelete = vi.fn();
    render(
      <BusinessCard business={business} onEdit={vi.fn()} onDelete={onDelete} onOpen={vi.fn()} />,
    );
    fireEvent.click(screen.getByTitle('Удалить'));
    expect(onDelete).toHaveBeenCalledWith('b-1');
  });
});
