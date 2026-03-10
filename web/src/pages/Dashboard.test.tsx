import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Dashboard } from './Dashboard';
import * as businessesApi from '../api/businesses';
import * as productsApi from '../api/products';
import * as teamsApi from '../api/teams';
import * as tasksApi from '../api/tasks';
import type { Business, Product, Task } from '../types';

vi.mock('../api/businesses', () => ({
  getBusinesses: vi.fn(),
  getBusiness: vi.fn(),
  createBusiness: vi.fn(),
  updateBusiness: vi.fn(),
  deleteBusiness: vi.fn(),
}));

vi.mock('../api/products', () => ({
  getProducts: vi.fn(),
  getProduct: vi.fn(),
  createProduct: vi.fn(),
  updateProduct: vi.fn(),
  deleteProduct: vi.fn(),
  cloneProduct: vi.fn(),
}));

vi.mock('../api/teams', () => ({
  getTeams: vi.fn(),
  getTeam: vi.fn(),
  createTeam: vi.fn(),
  updateTeam: vi.fn(),
  deleteTeam: vi.fn(),
}));

vi.mock('../api/tasks', () => ({
  getTasks: vi.fn(),
  getTask: vi.fn(),
  createTask: vi.fn(),
  updateTask: vi.fn(),
  deleteTask: vi.fn(),
  updateTaskStatus: vi.fn(),
}));

const businesses: Business[] = [
  { id: 'b-1', name: 'Acme Corp', description: null, created_at: '2024-01-01', products_count: 1 },
];

const products: Product[] = [
  {
    id: 'p-1', business_id: 'b-1', name: 'Web App', description: null,
    git_url: null, workspace_path: '/tmp', status: 'ready', clone_error: null, created_at: '2024-01-01',
  },
];

function makeTasks(): Task[] {
  return [
    { id: 't-1', title: 'Setup DB', description: null, product_id: 'p-1', team_id: null, workflow_id: null, status: 'backlog', created_at: '2024-01-01' },
    { id: 't-2', title: 'Build API', description: null, product_id: 'p-1', team_id: null, workflow_id: null, status: 'in_progress', created_at: '2024-01-02' },
    { id: 't-3', title: 'Deploy', description: null, product_id: 'p-1', team_id: null, workflow_id: null, status: 'done', created_at: '2024-01-03' },
    { id: 't-4', title: 'Fix bug', description: null, product_id: 'p-1', team_id: null, workflow_id: null, status: 'error', created_at: '2024-01-04' },
  ];
}

function setFiltersInStorage(businessId: string, productId: string) {
  localStorage.setItem('dashboard_filters', JSON.stringify({
    businessId, productId, teamId: null,
  }));
}

function renderDashboard() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  vi.mocked(businessesApi.getBusinesses).mockResolvedValue(businesses);
  vi.mocked(productsApi.getProducts).mockResolvedValue(products);
  vi.mocked(teamsApi.getTeams).mockResolvedValue([]);
  vi.mocked(tasksApi.getTasks).mockResolvedValue(makeTasks());
});

describe('Dashboard', () => {
  it('shows hint when no filters selected', () => {
    renderDashboard();
    expect(screen.getByText('Выберите бизнес и продукт, чтобы увидеть задачи')).toBeInTheDocument();
  });

  it('shows kanban columns when filters are pre-set', async () => {
    setFiltersInStorage('b-1', 'p-1');
    renderDashboard();

    // Tasks should load automatically
    expect(await screen.findByText('Setup DB')).toBeInTheDocument();
    expect(screen.getByText('Build API')).toBeInTheDocument();

    // Verify main columns
    expect(screen.getByRole('heading', { level: 3, name: /Backlog/ })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 3, name: /In Progress/ })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 3, name: /Ждёт решения/ })).toBeInTheDocument();
  });

  it('shows error column when error tasks exist', async () => {
    setFiltersInStorage('b-1', 'p-1');
    renderDashboard();

    expect(await screen.findByText('Fix bug')).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 3, name: /Ошибка/ })).toBeInTheDocument();
  });

  it('hides done column by default, shows on toggle', async () => {
    setFiltersInStorage('b-1', 'p-1');
    renderDashboard();

    await screen.findByText('Setup DB');

    // Done column not visible
    expect(screen.queryByText('Deploy')).not.toBeInTheDocument();

    // Toggle
    fireEvent.click(screen.getByLabelText('Показать завершённые'));
    expect(screen.getByText('Deploy')).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 3, name: /Готово/ })).toBeInTheDocument();
  });

  it('restores filters from localStorage and fetches tasks', async () => {
    setFiltersInStorage('b-1', 'p-1');
    renderDashboard();

    await waitFor(() => {
      expect(tasksApi.getTasks).toHaveBeenCalledWith('p-1');
    });
  });

  it('opens create task modal from backlog "+" button', async () => {
    setFiltersInStorage('b-1', 'p-1');
    renderDashboard();

    await screen.findByText('Setup DB');

    fireEvent.click(screen.getByTitle('Создать задачу'));
    expect(screen.getByText('Новая задача')).toBeInTheDocument();
  });

  it('shows "Начать" button on valid backlog tasks', async () => {
    setFiltersInStorage('b-1', 'p-1');
    renderDashboard();

    const startBtn = await screen.findByText('Начать');
    expect(startBtn).toBeInTheDocument();
  });
});
