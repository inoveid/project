import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getChangedFiles, discardFile } from '../api/products';
import type { DiffFile } from '../api/products';
import { DiffViewer } from './DiffViewer';

interface ChangesPanelProps {
  productId: string;
  onClose: () => void;
}

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  modified: { label: 'M', color: 'text-amber-600' },
  added: { label: 'A', color: 'text-green-600' },
  deleted: { label: 'D', color: 'text-red-600' },
  untracked: { label: 'U', color: 'text-gray-500' },
  renamed: { label: 'R', color: 'text-blue-600' },
};

export function ChangesPanel({ productId, onClose }: ChangesPanelProps) {
  const queryClient = useQueryClient();
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [confirmDiscard, setConfirmDiscard] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['product-changes', productId],
    queryFn: () => getChangedFiles(productId),
  });

  const discardMut = useMutation({
    mutationFn: (path: string) => discardFile(productId, path),
    onSuccess: () => {
      setConfirmDiscard(null);
      setSelectedFile(null);
      queryClient.invalidateQueries({ queryKey: ['product-changes', productId] });
      queryClient.invalidateQueries({ queryKey: ['product-git', productId] });
      queryClient.invalidateQueries({ queryKey: ['product-files', productId] });
      queryClient.invalidateQueries({ queryKey: ['spec-files', productId] });
    },
  });

  const discardAllMut = useMutation({
    mutationFn: async () => {
      if (!data?.files) return;
      for (const f of data.files) {
        await discardFile(productId, f.path);
      }
    },
    onSuccess: () => {
      setConfirmDiscard(null);
      setSelectedFile(null);
      queryClient.invalidateQueries({ queryKey: ['product-changes', productId] });
      queryClient.invalidateQueries({ queryKey: ['product-git', productId] });
      queryClient.invalidateQueries({ queryKey: ['product-files', productId] });
      queryClient.invalidateQueries({ queryKey: ['spec-files', productId] });
    },
  });

  const files = data?.files ?? [];
  const diffFiles = data?.diff_files ?? [];

  const selectedDiff: DiffFile | undefined = selectedFile
    ? diffFiles.find(d => d.path === selectedFile)
    : undefined;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div className="bg-white rounded-lg shadow-xl w-[900px] max-h-[80vh] flex flex-col" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center gap-3 px-4 py-3 border-b shrink-0">
          <h3 className="text-sm font-medium text-gray-900 flex-1">
            Незакоммиченные изменения ({files.length})
          </h3>
          {files.length > 1 && (
            confirmDiscard === '__all__' ? (
              <div className="flex items-center gap-1">
                <span className="text-[10px] text-red-600">Откатить все?</span>
                <button
                  onClick={() => discardAllMut.mutate()}
                  disabled={discardAllMut.isPending}
                  className="text-[10px] px-2 py-0.5 bg-red-600 text-white rounded"
                >
                  {discardAllMut.isPending ? '...' : 'Да'}
                </button>
                <button
                  onClick={() => setConfirmDiscard(null)}
                  className="text-[10px] px-2 py-0.5 text-gray-500"
                >
                  Нет
                </button>
              </div>
            ) : (
              <button
                onClick={() => setConfirmDiscard('__all__')}
                className="text-[10px] px-2 py-1 text-red-500 hover:text-red-700 border border-red-200 rounded"
              >
                Откатить все
              </button>
            )
          )}
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-lg leading-none">×</button>
        </div>

        {/* Content */}
        <div className="flex flex-1 min-h-0">
          {/* File list */}
          <div className="w-64 border-r overflow-y-auto shrink-0">
            {isLoading ? (
              <p className="text-xs text-gray-400 p-3">Загрузка...</p>
            ) : files.length === 0 ? (
              <p className="text-xs text-gray-400 p-3">Нет изменений</p>
            ) : (
              files.map(f => {
                const st = STATUS_LABELS[f.status] ?? STATUS_LABELS.modified;
                const isSelected = selectedFile === f.path;
                return (
                  <div
                    key={f.path}
                    className={`flex items-center gap-2 px-3 py-2 text-xs cursor-pointer hover:bg-gray-50 group ${
                      isSelected ? 'bg-blue-50' : ''
                    }`}
                    onClick={() => setSelectedFile(f.path)}
                  >
                    <span className={`font-mono font-bold w-4 shrink-0 ${st.color}`}>{st.label}</span>
                    <span className="truncate flex-1 text-gray-700">{f.path}</span>
                    {confirmDiscard === f.path ? (
                      <div className="flex items-center gap-1 shrink-0" onClick={e => e.stopPropagation()}>
                        <button
                          onClick={() => discardMut.mutate(f.path)}
                          disabled={discardMut.isPending}
                          className="text-[10px] px-1.5 py-0.5 bg-red-600 text-white rounded"
                        >
                          {discardMut.isPending ? '...' : 'Да'}
                        </button>
                        <button
                          onClick={() => setConfirmDiscard(null)}
                          className="text-[10px] px-1.5 py-0.5 text-gray-500"
                        >
                          Нет
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={(e) => { e.stopPropagation(); setConfirmDiscard(f.path); }}
                        className={`text-[10px] text-red-400 hover:text-red-600 shrink-0 ${isSelected ? '' : 'opacity-0 group-hover:opacity-100'}`}
                        title="Откатить"
                      >
                        ↩
                      </button>
                    )}
                  </div>
                );
              })
            )}
          </div>

          {/* Diff view */}
          <div className="flex-1 min-w-0 overflow-auto">
            {selectedDiff ? (
              <DiffViewer
                files={[selectedDiff]}
                totalAdditions={selectedDiff.additions}
                totalDeletions={selectedDiff.deletions}
              />
            ) : selectedFile ? (
              <div className="p-4">
                {(() => {
                  const f = files.find(ff => ff.path === selectedFile);
                  if (f?.status === 'untracked' && (f as any).content_preview) {
                    return (
                      <pre className="text-xs text-gray-600 whitespace-pre-wrap font-mono bg-gray-50 p-3 rounded">
                        {(f as any).content_preview}
                      </pre>
                    );
                  }
                  return <p className="text-xs text-gray-400">Нет диффа для этого файла</p>;
                })()}
              </div>
            ) : (
              <div className="flex items-center justify-center h-full text-gray-400 text-sm">
                Выберите файл для просмотра изменений
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
