import type { Product } from '../types';
import { useProduct, useCloneProduct, useDeleteProduct } from '../hooks/useProducts';

interface ProductCardProps {
  product: Product;
  onEdit: (product: Product) => void;
  onDeleted: () => void;
}

export function ProductCard({ product: initialProduct, onEdit, onDeleted }: ProductCardProps) {
  const isPolling = initialProduct.status === 'cloning';
  const { data: polledProduct } = useProduct(initialProduct.id, isPolling);
  const product = polledProduct ?? initialProduct;

  const cloneProduct = useCloneProduct();
  const deleteProduct = useDeleteProduct();

  function handleClone() {
    cloneProduct.mutate(product.id);
  }

  function handleDelete() {
    if (window.confirm(`Удалить продукт "${product.name}"?`)) {
      deleteProduct.mutate(product.id, { onSuccess: onDeleted });
    }
  }

  const canClone = !!product.git_url && product.status !== 'cloning';

  function cloneButtonLabel() {
    if (product.status === 'cloning') return 'Клонирование... ⏳';
    if (product.status === 'error') return 'Повторить клон';
    return 'Клонировать';
  }

  return (
    <div className="border rounded p-4 bg-white flex flex-col gap-2">
      <div className="flex items-start justify-between">
        <h4 className="font-semibold text-gray-900">{product.name}</h4>
        <button
          onClick={() => onEdit(product)}
          className="text-sm text-gray-500 hover:text-gray-800 px-2"
        >
          Edit
        </button>
      </div>

      {product.git_url && (
        <p className="text-sm text-gray-500 font-mono truncate">{product.git_url}</p>
      )}
      <p className="text-xs text-gray-400 font-mono truncate">{product.workspace_path}</p>

      {product.status === 'ready' && (
        <p className="text-sm text-green-600">✓ Готово</p>
      )}
      {product.status === 'error' && product.clone_error && (
        <p className="text-sm text-red-600">✗ Ошибка: {product.clone_error}</p>
      )}

      <div className="flex gap-2 mt-1">
        {product.status !== 'ready' && (
          <button
            onClick={handleClone}
            disabled={!canClone || cloneProduct.isPending}
            title={!product.git_url ? 'Укажите git_url для клонирования' : undefined}
            className="flex-1 bg-blue-600 text-white px-3 py-1.5 rounded text-sm hover:bg-blue-700 disabled:opacity-50"
          >
            {cloneButtonLabel()}
          </button>
        )}
        <button
          onClick={handleDelete}
          disabled={deleteProduct.isPending}
          className="border px-3 py-1.5 rounded text-sm hover:bg-gray-50 text-gray-600 disabled:opacity-50"
        >
          Удалить
        </button>
      </div>
    </div>
  );
}
