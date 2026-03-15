import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getSecrets, saveSecret, deleteSecret } from '../api/products';

interface SecretsPanelProps {
  productId: string;
}

export function SecretsPanel({ productId }: SecretsPanelProps) {
  const queryClient = useQueryClient();
  const [newKey, setNewKey] = useState('');
  const [newValue, setNewValue] = useState('');
  const [showForm, setShowForm] = useState(false);

  const { data: secrets, isLoading } = useQuery({
    queryKey: ['product-secrets', productId],
    queryFn: () => getSecrets(productId),
  });

  const saveMut = useMutation({
    mutationFn: () => saveSecret(productId, newKey.trim(), newValue),
    onSuccess: () => {
      setNewKey('');
      setNewValue('');
      setShowForm(false);
      queryClient.invalidateQueries({ queryKey: ['product-secrets', productId] });
    },
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => deleteSecret(productId, id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['product-secrets', productId] });
    },
  });

  return (
    <div className="max-w-xl mx-auto p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-sm font-medium text-gray-900">Секреты</h2>
          <p className="text-xs text-gray-500 mt-0.5">
            Переменные окружения для агентов. Значения маскированы.
          </p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="text-xs px-3 py-1.5 bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          + Добавить
        </button>
      </div>

      {showForm && (
        <div className="mb-4 p-3 border rounded bg-gray-50 space-y-2">
          <input
            type="text"
            value={newKey}
            onChange={(e) => setNewKey(e.target.value.toUpperCase().replace(/[^A-Z0-9_]/g, ''))}
            placeholder="KEY_NAME"
            className="w-full text-xs px-3 py-1.5 border rounded font-mono"
          />
          <input
            type="password"
            value={newValue}
            onChange={(e) => setNewValue(e.target.value)}
            placeholder="value"
            className="w-full text-xs px-3 py-1.5 border rounded font-mono"
          />
          <div className="flex gap-2">
            <button
              onClick={() => saveMut.mutate()}
              disabled={!newKey.trim() || !newValue || saveMut.isPending}
              className="text-xs px-3 py-1.5 bg-blue-600 text-white rounded disabled:opacity-50"
            >
              {saveMut.isPending ? '...' : 'Сохранить'}
            </button>
            <button
              onClick={() => { setShowForm(false); setNewKey(''); setNewValue(''); }}
              className="text-xs px-3 py-1.5 text-gray-500 hover:text-gray-700"
            >
              Отмена
            </button>
          </div>
          {saveMut.isError && (
            <p className="text-xs text-red-500">{(saveMut.error as Error).message}</p>
          )}
        </div>
      )}

      {isLoading ? (
        <p className="text-xs text-gray-400">Загрузка...</p>
      ) : secrets && secrets.length > 0 ? (
        <div className="border rounded divide-y">
          {secrets.map(s => (
            <div key={s.id} className="flex items-center px-3 py-2">
              <span className="text-xs font-mono text-gray-900 flex-1">{s.key}</span>
              <span className="text-xs text-gray-400 mr-3">••••••••</span>
              <button
                onClick={() => deleteMut.mutate(s.id)}
                disabled={deleteMut.isPending}
                className="text-xs text-red-500 hover:text-red-700"
              >
                Удалить
              </button>
            </div>
          ))}
        </div>
      ) : (
        <div className="py-8 text-gray-400 text-sm">
          Нет секретов. Добавьте API-ключи и токены для агентов.
        </div>
      )}
    </div>
  );
}
