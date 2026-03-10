import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { CreateTaskModal } from './CreateTaskModal';

describe('CreateTaskModal', () => {
  it('renders form with title input', () => {
    render(
      <CreateTaskModal
        productId="p-1"
        onSubmit={vi.fn()}
        onClose={vi.fn()}
        isLoading={false}
      />,
    );
    expect(screen.getByText('Новая задача')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Введите название задачи')).toBeInTheDocument();
  });

  it('calls onSubmit with title and product_id', () => {
    const onSubmit = vi.fn();
    render(
      <CreateTaskModal
        productId="p-1"
        onSubmit={onSubmit}
        onClose={vi.fn()}
        isLoading={false}
      />,
    );
    fireEvent.change(screen.getByPlaceholderText('Введите название задачи'), {
      target: { value: 'New Task' },
    });
    fireEvent.click(screen.getByText('Создать'));
    expect(onSubmit).toHaveBeenCalledWith({ title: 'New Task', product_id: 'p-1' });
  });

  it('does not submit when title is empty', () => {
    const onSubmit = vi.fn();
    render(
      <CreateTaskModal
        productId="p-1"
        onSubmit={onSubmit}
        onClose={vi.fn()}
        isLoading={false}
      />,
    );
    expect(screen.getByText('Создать')).toBeDisabled();
  });

  it('calls onClose when cancel clicked', () => {
    const onClose = vi.fn();
    render(
      <CreateTaskModal
        productId="p-1"
        onSubmit={vi.fn()}
        onClose={onClose}
        isLoading={false}
      />,
    );
    fireEvent.click(screen.getByText('Отмена'));
    expect(onClose).toHaveBeenCalled();
  });

  it('shows loading state', () => {
    render(
      <CreateTaskModal
        productId="p-1"
        onSubmit={vi.fn()}
        onClose={vi.fn()}
        isLoading={true}
      />,
    );
    expect(screen.getByText('Создание...')).toBeInTheDocument();
  });
});
