import type { Business } from '../types';

interface BusinessCardProps {
  business: Business;
  onEdit: (business: Business) => void;
  onDelete: (id: string) => void;
  onOpen: (id: string) => void;
}

export function BusinessCard({ business, onEdit, onDelete, onOpen }: BusinessCardProps) {
  const productWord =
    business.products_count === 1 ? 'продукт' :
    business.products_count >= 2 && business.products_count <= 4 ? 'продукта' : 'продуктов';

  return (
    <div className="border rounded p-4 bg-white flex flex-col gap-3">
      <div className="flex items-start justify-between">
        <h3 className="font-semibold text-gray-900">{business.name}</h3>
        <button
          onClick={() => onEdit(business)}
          className="text-sm text-gray-500 hover:text-gray-800 px-2"
        >
          Edit
        </button>
      </div>
      {business.description && (
        <p className="text-sm text-gray-500 -mt-2">{business.description}</p>
      )}
      <p className="text-sm text-gray-400">
        {business.products_count} {productWord}
      </p>
      <div className="flex gap-2">
        <button
          onClick={() => onOpen(business.id)}
          className="flex-1 bg-blue-600 text-white px-3 py-1.5 rounded text-sm hover:bg-blue-700"
        >
          Открыть →
        </button>
        <button
          onClick={() => onDelete(business.id)}
          className="border px-3 py-1.5 rounded text-sm hover:bg-gray-50 text-gray-600"
          title="Удалить"
        >
          🗑
        </button>
      </div>
    </div>
  );
}
