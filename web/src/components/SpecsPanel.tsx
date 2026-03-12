import { useState } from 'react';
import {
  useSpecs,
  useCreateSpec,
  useUpdateSpec,
  useDeleteSpec,
  useSpecVersions,
  useRollbackSpec,
} from '../hooks/useSpecs';
import type { Spec, SpecCreate, SpecUpdate } from '../types';

interface SpecsPanelProps {
  productId: string;
}

type ViewMode =
  | { kind: 'list' }
  | { kind: 'create' }
  | { kind: 'view'; spec: Spec }
  | { kind: 'edit'; spec: Spec };

export function SpecsPanel({ productId }: SpecsPanelProps) {
  const { data: specs, isLoading } = useSpecs(productId);
  const createSpec = useCreateSpec();
  const updateSpec = useUpdateSpec();
  const deleteSpec = useDeleteSpec();

  const [mode, setMode] = useState<ViewMode>({ kind: 'list' });
  const [form, setForm] = useState({ feature: '', title: '', content: '' });

  function openCreate() {
    setForm({ feature: '', title: '', content: '' });
    setMode({ kind: 'create' });
  }

  function openEdit(spec: Spec) {
    setForm({ feature: spec.feature, title: spec.title, content: spec.content });
    setMode({ kind: 'edit', spec });
  }

  function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    const data: SpecCreate = { feature: form.feature, title: form.title, content: form.content };
    createSpec.mutate({ productId, data }, {
      onSuccess: () => setMode({ kind: 'list' }),
    });
  }

  function handleUpdate(e: React.FormEvent) {
    e.preventDefault();
    if (mode.kind !== 'edit') return;
    const data: SpecUpdate = {
      feature: form.feature,
      title: form.title,
      content: form.content,
      summary: 'Updated via UI',
    };
    updateSpec.mutate({ id: mode.spec.id, data }, {
      onSuccess: (updated) => setMode({ kind: 'view', spec: updated }),
    });
  }

  function handleDelete(spec: Spec) {
    if (!window.confirm(`Удалить спецификацию "${spec.title}"?`)) return;
    deleteSpec.mutate(spec.id, {
      onSuccess: () => setMode({ kind: 'list' }),
    });
  }

  if (isLoading) return <p className="text-sm text-gray-400">Загрузка спеков...</p>;

  // ── Spec viewer with versions ──
  if (mode.kind === 'view') {
    return (
      <SpecViewer
        spec={mode.spec}
        onBack={() => setMode({ kind: 'list' })}
        onEdit={() => openEdit(mode.spec)}
        onDelete={() => handleDelete(mode.spec)}
      />
    );
  }

  // ── Create / Edit form ──
  if (mode.kind === 'create' || mode.kind === 'edit') {
    const isEdit = mode.kind === 'edit';
    const mutation = isEdit ? updateSpec : createSpec;
    return (
      <form
        onSubmit={isEdit ? handleUpdate : handleCreate}
        className="flex flex-col gap-3 p-3 border rounded bg-gray-50"
      >
        <div className="flex items-center justify-between">
          <h4 className="text-sm font-semibold text-gray-700">
            {isEdit ? 'Редактировать спецификацию' : 'Новая спецификация'}
          </h4>
          <button
            type="button"
            onClick={() => setMode({ kind: 'list' })}
            className="text-xs text-gray-500 hover:text-gray-800"
          >
            ✕
          </button>
        </div>
        <input
          type="text"
          required
          placeholder="Feature (auth, onboarding, dashboard...)"
          value={form.feature}
          onChange={(e) => setForm((s) => ({ ...s, feature: e.target.value }))}
          className="border rounded px-3 py-1.5 text-sm"
        />
        <input
          type="text"
          required
          placeholder="Заголовок спецификации"
          value={form.title}
          onChange={(e) => setForm((s) => ({ ...s, title: e.target.value }))}
          className="border rounded px-3 py-1.5 text-sm"
        />
        <textarea
          placeholder="Содержимое (Annotated Wireframe markdown)"
          value={form.content}
          onChange={(e) => setForm((s) => ({ ...s, content: e.target.value }))}
          rows={10}
          className="border rounded px-3 py-1.5 text-sm font-mono"
        />
        <div className="flex gap-2">
          <button
            type="submit"
            disabled={mutation.isPending}
            className="bg-blue-600 text-white px-4 py-1.5 rounded text-sm hover:bg-blue-700 disabled:opacity-50"
          >
            {mutation.isPending ? 'Сохранение...' : isEdit ? 'Сохранить' : 'Создать'}
          </button>
          <button
            type="button"
            onClick={() => setMode({ kind: 'list' })}
            className="border px-4 py-1.5 rounded text-sm hover:bg-gray-100"
          >
            Отмена
          </button>
        </div>
      </form>
    );
  }

  // ── List ──
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-semibold text-gray-700">
          Спецификации {specs && specs.length > 0 && `(${specs.length})`}
        </h4>
        <button
          onClick={openCreate}
          className="text-xs bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700"
        >
          + Новая
        </button>
      </div>
      {specs && specs.length > 0 ? (
        <div className="flex flex-col gap-1">
          {specs.map((spec) => (
            <button
              key={spec.id}
              onClick={() => setMode({ kind: 'view', spec })}
              className="text-left p-2 border rounded hover:bg-gray-50 flex items-center justify-between"
            >
              <div>
                <span className="text-sm font-medium text-gray-900">{spec.title}</span>
                <span className="text-xs text-gray-400 ml-2">{spec.feature}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className={`text-xs px-1.5 py-0.5 rounded ${
                  spec.status === 'active'
                    ? 'bg-green-100 text-green-700'
                    : 'bg-gray-100 text-gray-500'
                }`}>
                  {spec.status === 'active' ? 'Active' : 'Draft'}
                </span>
                <span className="text-xs text-gray-400">v{spec.version}</span>
              </div>
            </button>
          ))}
        </div>
      ) : (
        <p className="text-xs text-gray-400">Нет спецификаций</p>
      )}
    </div>
  );
}

// ── SpecViewer: показ содержимого + история версий ──

function SpecViewer({
  spec,
  onBack,
  onEdit,
  onDelete,
}: {
  spec: Spec;
  onBack: () => void;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const [showVersions, setShowVersions] = useState(false);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <button onClick={onBack} className="text-xs text-blue-600 hover:underline">
          ← Назад к списку
        </button>
        <div className="flex gap-2">
          <button
            onClick={() => setShowVersions((v) => !v)}
            className="text-xs text-gray-500 hover:text-gray-800 border px-2 py-1 rounded"
          >
            {showVersions ? 'Скрыть историю' : `История (v${spec.version})`}
          </button>
          <button
            onClick={onEdit}
            className="text-xs text-gray-500 hover:text-gray-800 border px-2 py-1 rounded"
          >
            Редактировать
          </button>
          <button
            onClick={onDelete}
            className="text-xs text-red-500 hover:text-red-700 border border-red-200 px-2 py-1 rounded"
          >
            Удалить
          </button>
        </div>
      </div>

      <div>
        <h3 className="font-semibold text-gray-900">{spec.title}</h3>
        <div className="flex gap-2 mt-1">
          <span className="text-xs text-gray-400">{spec.feature}</span>
          <span className={`text-xs px-1.5 py-0.5 rounded ${
            spec.status === 'active'
              ? 'bg-green-100 text-green-700'
              : 'bg-gray-100 text-gray-500'
          }`}>
            {spec.status}
          </span>
          <span className="text-xs text-gray-400">v{spec.version}</span>
        </div>
      </div>

      <pre className="whitespace-pre-wrap text-sm bg-gray-50 border rounded p-3 font-mono max-h-96 overflow-y-auto">
        {spec.content || '(пусто)'}
      </pre>

      {showVersions && <VersionHistory specId={spec.id} />}
    </div>
  );
}

// ── VersionHistory ──

function VersionHistory({ specId }: { specId: string }) {
  const { data: versions, isLoading } = useSpecVersions(specId);
  const rollback = useRollbackSpec();

  function handleRollback(version: number) {
    if (!window.confirm(`Откатить к версии v${version}? Текущее содержимое сохранится как отдельная версия.`)) return;
    rollback.mutate({ specId, version });
  }

  if (isLoading) return <p className="text-xs text-gray-400">Загрузка версий...</p>;
  if (!versions || versions.length === 0) return <p className="text-xs text-gray-400">Нет версий</p>;

  return (
    <div className="border rounded overflow-hidden">
      <div className="bg-gray-100 px-3 py-1.5 text-xs font-semibold text-gray-600">
        История версий
      </div>
      <div className="divide-y max-h-48 overflow-y-auto">
        {versions.map((v) => (
          <div key={v.id} className="px-3 py-2 flex items-center justify-between text-xs">
            <div>
              <span className="font-medium text-gray-700">v{v.version}</span>
              <span className="text-gray-400 ml-2">{v.author}</span>
              {v.summary && <span className="text-gray-400 ml-2">— {v.summary}</span>}
            </div>
            <div className="flex items-center gap-2">
              <span className="text-gray-400">
                {new Date(v.created_at).toLocaleString('ru')}
              </span>
              <button
                onClick={() => handleRollback(v.version)}
                disabled={rollback.isPending}
                className="text-blue-600 hover:underline disabled:opacity-50"
              >
                Откатить
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
