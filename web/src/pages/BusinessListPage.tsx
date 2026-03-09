import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BusinessCard } from '../components/BusinessCard';
import { BusinessConflictError } from '../api/businesses';
import {
  useBusinesses,
  useCreateBusiness,
  useDeleteBusiness,
  useUpdateBusiness,
} from '../hooks/useBusinesses';
import type { Business, BusinessCreate, BusinessUpdate } from '../types';

type FormMode = { kind: 'closed' } | { kind: 'create' } | { kind: 'edit'; business: Business };
type FormState = { name: string; description: string };

const EMPTY_FORM: FormState = { name: '', description: '' };

function businessToForm(business: Business): FormState {
  return { name: business.name, description: business.description ?? '' };
}

export function BusinessListPage() {
  const navigate = useNavigate();
  const { data: businesses, isLoading, error } = useBusinesses();
  const createBusiness = useCreateBusiness();
  const updateBusiness = useUpdateBusiness();
  const deleteBusiness = useDeleteBusiness();

  const [formMode, setFormMode] = useState<FormMode>({ kind: 'closed' });
  const [form, setForm] = useState<FormState>(EMPTY_FORM);

  function openCreate() {
    setForm(EMPTY_FORM);
    setFormMode({ kind: 'create' });
  }

  function openEdit(business: Business) {
    setForm(businessToForm(business));
    setFormMode({ kind: 'edit', business });
  }

  function closeForm() {
    setFormMode({ kind: 'closed' });
    setForm(EMPTY_FORM);
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (formMode.kind === 'create') {
      const data: BusinessCreate = {
        name: form.name,
        description: form.description || undefined,
      };
      createBusiness.mutate(data, { onSuccess: closeForm });
    } else if (formMode.kind === 'edit') {
      const data: BusinessUpdate = {
        name: form.name,
        description: form.description || undefined,
      };
      updateBusiness.mutate({ id: formMode.business.id, data }, { onSuccess: closeForm });
    }
  }

  function handleDelete(id: string) {
    deleteBusiness.mutate({ id }, {
      onError: (err) => {
        if (err instanceof BusinessConflictError) {
          const confirmed = window.confirm(
            `Будет удалено ${err.productsCount} продуктов и их репозитории. Продолжить?`,
          );
          if (confirmed) {
            deleteBusiness.mutate({ id, force: true });
          }
        } else {
          alert(err.message);
        }
      },
    });
  }

  const activeMutation = formMode.kind === 'edit' ? updateBusiness : createBusiness;

  if (isLoading) return <p className="text-gray-500">Загрузка...</p>;
  if (error) return <p className="text-red-600">Ошибка: {error.message}</p>;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-gray-900">Бизнесы</h1>
        {formMode.kind === 'closed' && (
          <button
            onClick={openCreate}
            className="bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700"
          >
            + Создать бизнес
          </button>
        )}
      </div>

      {formMode.kind !== 'closed' && (
        <form
          onSubmit={handleSubmit}
          className="mb-6 p-4 border rounded bg-gray-50 flex flex-col gap-3"
        >
          <h2 className="text-sm font-semibold text-gray-700">
            {formMode.kind === 'create' ? 'Новый бизнес' : 'Редактировать бизнес'}
          </h2>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Название *</label>
            <input
              type="text"
              required
              placeholder="My Company"
              value={form.name}
              onChange={(e) => setForm((s) => ({ ...s, name: e.target.value }))}
              className="w-full border rounded px-3 py-1.5 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Описание <span className="font-normal text-gray-400">(опционально)</span>
            </label>
            <input
              type="text"
              value={form.description}
              onChange={(e) => setForm((s) => ({ ...s, description: e.target.value }))}
              className="w-full border rounded px-3 py-1.5 text-sm"
            />
          </div>
          {activeMutation.error && (
            <p className="text-sm text-red-600">{activeMutation.error.message}</p>
          )}
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={activeMutation.isPending}
              className="bg-blue-600 text-white px-4 py-1.5 rounded text-sm hover:bg-blue-700 disabled:opacity-50"
            >
              {activeMutation.isPending
                ? formMode.kind === 'create' ? 'Создание...' : 'Сохранение...'
                : formMode.kind === 'create' ? 'Создать' : 'Сохранить'}
            </button>
            <button
              type="button"
              onClick={closeForm}
              className="border px-4 py-1.5 rounded text-sm hover:bg-gray-100"
            >
              Отмена
            </button>
          </div>
        </form>
      )}

      {businesses && businesses.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {businesses.map((business) => (
            <BusinessCard
              key={business.id}
              business={business}
              onEdit={openEdit}
              onDelete={handleDelete}
              onOpen={(id) => navigate(`/businesses/${id}`)}
            />
          ))}
        </div>
      ) : (
        <p className="text-gray-500">Нет бизнесов. Создайте первый.</p>
      )}
    </div>
  );
}
