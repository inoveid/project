import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ProductCard } from './ProductCard';
import type { Product } from '../types';

vi.mock('../hooks/useProducts', () => ({
  useProduct: () => ({ data: undefined }),
  useCloneProduct: () => ({ mutate: vi.fn(), isPending: false }),
  useDeleteProduct: () => ({ mutate: vi.fn(), isPending: false }),
}));

function wrapper({ children }: { children: React.ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

const baseProduct: Product = {
  id: 'p-1',
  business_id: 'b-1',
  name: 'SaaS App',
  description: null,
  git_url: 'https://github.com/org/repo',
  workspace_path: '/workspace/products/p-1',
  status: 'pending',
  clone_error: null,
  created_at: '2024-01-01T00:00:00Z',
};

describe('ProductCard', () => {
  it('renders product name and git_url', () => {
    render(<ProductCard product={baseProduct} onEdit={vi.fn()} onDeleted={vi.fn()} />, { wrapper });
    expect(screen.getByText('SaaS App')).toBeInTheDocument();
    expect(screen.getByText('https://github.com/org/repo')).toBeInTheDocument();
  });

  it('shows Клонировать button when status is pending and git_url set', () => {
    render(<ProductCard product={baseProduct} onEdit={vi.fn()} onDeleted={vi.fn()} />, { wrapper });
    expect(screen.getByText('Клонировать')).toBeInTheDocument();
  });

  it('disables clone button when git_url is absent', () => {
    const product = { ...baseProduct, git_url: null };
    render(<ProductCard product={product} onEdit={vi.fn()} onDeleted={vi.fn()} />, { wrapper });
    const btn = screen.getByText('Клонировать');
    expect(btn).toBeDisabled();
  });

  it('shows cloning state when status is cloning', () => {
    const product = { ...baseProduct, status: 'cloning' as const };
    render(<ProductCard product={product} onEdit={vi.fn()} onDeleted={vi.fn()} />, { wrapper });
    expect(screen.getByText(/Клонирование/)).toBeInTheDocument();
    expect(screen.getByText(/Клонирование/)).toBeDisabled();
  });

  it('shows ready state — hides clone button, shows checkmark', () => {
    const product = { ...baseProduct, status: 'ready' as const };
    render(<ProductCard product={product} onEdit={vi.fn()} onDeleted={vi.fn()} />, { wrapper });
    expect(screen.queryByText('Клонировать')).not.toBeInTheDocument();
    expect(screen.getByText(/Готово/)).toBeInTheDocument();
  });

  it('shows error state with error message and retry button', () => {
    const product = { ...baseProduct, status: 'error' as const, clone_error: 'auth failed' };
    render(<ProductCard product={product} onEdit={vi.fn()} onDeleted={vi.fn()} />, { wrapper });
    expect(screen.getByText(/auth failed/)).toBeInTheDocument();
    expect(screen.getByText('Повторить клон')).toBeInTheDocument();
  });
});
