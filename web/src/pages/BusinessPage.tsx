import { useState, useEffect } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ProductCard } from '../components/ProductCard';
import { useBusiness, useUpdateBusiness } from '../hooks/useBusinesses';
import { useProducts, useCreateProduct, useUpdateProduct } from '../hooks/useProducts';
import type { BusinessUpdate, Product, ProductCreate, ProductUpdate } from '../types';

type BusinessFormMode = 'view' | 'edit';
type ProductFormMode =
  | { kind: 'closed' }
  | { kind: 'create' }
  | { kind: 'edit'; product: Product };

type ProductFormState = { name: string; git_url: string; description: string };

const EMPTY_PRODUCT_FORM: ProductFormState = { name: '', git_url: '', description: '' };

function productToForm(product: Product): ProductFormState {
  return {
    name: product.name,
    git_url: product.git_url ?? '',
    description: product.description ?? '',
  };
}

export function BusinessPage() {
  const { businessId } = useParams<{ businessId: string }>();
  const id = businessId ?? '';

  const { data: business, isLoading, error } = useBusiness(id);
  const updateBusiness = useUpdateBusiness();

  const { data: products } = useProducts(id);
  const createProduct = useCreateProduct();
  const updateProduct = useUpdateProduct();

  const [businessFormMode, setBusinessFormMode] = useState<BusinessFormMode>('view');
  const [businessForm, setBusinessForm] = useState({ name: '', description: '' });

  const [productFormMode, setProductFormMode] = useState<ProductFormMode>({ kind: 'closed' });
  const [productForm, setProductForm] = useState<ProductFormState>(EMPTY_PRODUCT_FORM);

  useEffect(() => {
    setBusinessFormMode('view');
    setBusinessForm({ name: '', description: '' });
    setProductFormMode({ kind: 'closed' });
    setProductForm(EMPTY_PRODUCT_FORM);
  }, [id]);

  function openBusinessEdit() {
    if (!business) return;
    setBusinessForm({ name: business.name, description: business.description ?? '' });
    setBusinessFormMode('edit');
  }

  function handleBusinessSave(e: React.FormEvent) {
    e.preventDefault();
    const data: BusinessUpdate = {
      name: businessForm.name,
      description: businessForm.description || undefined,
    };
    updateBusiness.mutate({ id, data }, {
      onSuccess: () => setBusinessFormMode('view'),
    });
  }

  function openProductCreate() {
    setProductForm(EMPTY_PRODUCT_FORM);
    setProductFormMode({ kind: 'create' });
  }

  function openProductEdit(product: Product) {
    setProductForm(productToForm(product));
    setProductFormMode({ kind: 'edit', product });
  }

  function closeProductForm() {
    setProductFormMode({ kind: 'closed' });
    setProductForm(EMPTY_PRODUCT_FORM);
  }

  function handleProductSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (productFormMode.kind === 'create') {
      const data: ProductCreate = {
        name: productForm.name,
        business_id: id,
        git_url: productForm.git_url || undefined,
        description: productForm.description || undefined,
      };
      createProduct.mutate(data, { onSuccess: closeProductForm });
    } else if (productFormMode.kind === 'edit') {
      const data: ProductUpdate = {
        name: productForm.name,
        git_url: productForm.git_url || undefined,
        description: productForm.description || undefined,
      };
      updateProduct.mutate({ id: productFormMode.product.id, data }, { onSuccess: closeProductForm });
    }
  }

  if (isLoading) return <p className="text-gray-500">Загрузка...</p>;
  if (error || !business) {
    return <p className="text-red-600">Ошибка: {error?.message ?? 'Бизнес не найден'}</p>;
  }

  const activeProductMutation =
    productFormMode.kind === 'edit' ? updateProduct : createProduct;

  return (
    <div>
      <Link to="/businesses" className="text-blue-600 hover:underline text-sm mb-4 inline-block">
        ← Назад к бизнесам
      </Link>

      {businessFormMode === 'view' ? (
        <div className="flex items-start justify-between mb-6">
          <div>
            <h1 className="text-xl font-bold text-gray-900">Business: "{business.name}"</h1>
            {business.description && (
              <p className="text-gray-500 mt-1">{business.description}</p>
            )}
          </div>
          <button
            onClick={openBusinessEdit}
            className="text-sm text-gray-500 hover:text-gray-800 border px-3 py-1.5 rounded"
          >
            Редактировать
          </button>
        </div>
      ) : (
        <form onSubmit={handleBusinessSave} className="mb-6 p-4 border rounded bg-gray-50 flex flex-col gap-3">
          <h2 className="text-sm font-semibold text-gray-700">Редактировать бизнес</h2>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Название *</label>
            <input
              type="text"
              required
              value={businessForm.name}
              onChange={(e) => setBusinessForm((s) => ({ ...s, name: e.target.value }))}
              className="w-full border rounded px-3 py-1.5 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Описание</label>
            <input
              type="text"
              value={businessForm.description}
              onChange={(e) => setBusinessForm((s) => ({ ...s, description: e.target.value }))}
              className="w-full border rounded px-3 py-1.5 text-sm"
            />
          </div>
          {updateBusiness.error && (
            <p className="text-sm text-red-600">{updateBusiness.error.message}</p>
          )}
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={updateBusiness.isPending}
              className="bg-blue-600 text-white px-4 py-1.5 rounded text-sm hover:bg-blue-700 disabled:opacity-50"
            >
              {updateBusiness.isPending ? 'Сохранение...' : 'Сохранить'}
            </button>
            <button
              type="button"
              onClick={() => setBusinessFormMode('view')}
              className="border px-4 py-1.5 rounded text-sm hover:bg-gray-100"
            >
              Отмена
            </button>
          </div>
        </form>
      )}

      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Продукты</h2>
        {productFormMode.kind === 'closed' && (
          <button
            onClick={openProductCreate}
            className="bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700"
          >
            + Добавить продукт
          </button>
        )}
      </div>

      {productFormMode.kind !== 'closed' && (
        <form
          onSubmit={handleProductSubmit}
          className="mb-6 p-4 border rounded bg-gray-50 flex flex-col gap-3"
        >
          <h3 className="text-sm font-semibold text-gray-700">
            {productFormMode.kind === 'create' ? 'Новый продукт' : 'Редактировать продукт'}
          </h3>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Название *</label>
            <input
              type="text"
              required
              placeholder="SaaS App"
              value={productForm.name}
              onChange={(e) => setProductForm((s) => ({ ...s, name: e.target.value }))}
              className="w-full border rounded px-3 py-1.5 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Git URL <span className="font-normal text-gray-400">(опционально)</span>
            </label>
            <input
              type="text"
              placeholder="https://github.com/org/repo"
              value={productForm.git_url}
              onChange={(e) => setProductForm((s) => ({ ...s, git_url: e.target.value }))}
              className="w-full border rounded px-3 py-1.5 text-sm font-mono"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Описание <span className="font-normal text-gray-400">(опционально)</span>
            </label>
            <input
              type="text"
              value={productForm.description}
              onChange={(e) => setProductForm((s) => ({ ...s, description: e.target.value }))}
              className="w-full border rounded px-3 py-1.5 text-sm"
            />
          </div>
          {activeProductMutation.error && (
            <p className="text-sm text-red-600">{activeProductMutation.error.message}</p>
          )}
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={activeProductMutation.isPending}
              className="bg-blue-600 text-white px-4 py-1.5 rounded text-sm hover:bg-blue-700 disabled:opacity-50"
            >
              {activeProductMutation.isPending
                ? productFormMode.kind === 'create' ? 'Создание...' : 'Сохранение...'
                : productFormMode.kind === 'create' ? 'Создать' : 'Сохранить'}
            </button>
            <button
              type="button"
              onClick={closeProductForm}
              className="border px-4 py-1.5 rounded text-sm hover:bg-gray-100"
            >
              Отмена
            </button>
          </div>
        </form>
      )}

      {products && products.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {products.map((product) => (
            <ProductCard
              key={product.id}
              product={product}
              onEdit={openProductEdit}
              onDeleted={() => {}}
            />
          ))}
        </div>
      ) : (
        <p className="text-gray-500">Нет продуктов. Добавьте первый.</p>
      )}
    </div>
  );
}
