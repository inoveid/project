import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import ReactMarkdown from 'react-markdown';
import Editor from '@monaco-editor/react';
import { getFileTree, readFile, writeFile } from '../api/products';
import type { FileEntry } from '../api/products';

const SPEC_DIR = '.ai';
const SPEC_FILES = ['SPEC.md', 'ARCHITECTURE.md', 'DECISIONS.md', 'CLAUDE.md'];

interface SpecPanelProps {
  productId: string;
}

export function SpecPanel({ productId }: SpecPanelProps) {
  const queryClient = useQueryClient();
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [editMode, setEditMode] = useState(false);
  const [editContent, setEditContent] = useState('');

  const { data: specFiles } = useQuery({
    queryKey: ['spec-files', productId],
    queryFn: () => getFileTree(productId, SPEC_DIR),
    retry: false,
  });

  const { data: fileContent, isLoading } = useQuery({
    queryKey: ['spec-file', productId, selectedFile],
    queryFn: () => readFile(productId, selectedFile!),
    enabled: !!selectedFile,
  });

  const saveMutation = useMutation({
    mutationFn: (content: string) => writeFile(productId, selectedFile!, content),
    onSuccess: () => {
      setEditMode(false);
      queryClient.invalidateQueries({ queryKey: ['spec-file', productId, selectedFile] });
      queryClient.invalidateQueries({ queryKey: ['product-git', productId] });
    },
  });

  const createFileMutation = useMutation({
    mutationFn: (name: string) => writeFile(productId, `${SPEC_DIR}/${name}`, `# ${name.replace('.md', '')}\n\n`),
    onSuccess: (_, name) => {
      queryClient.invalidateQueries({ queryKey: ['spec-files', productId] });
      queryClient.invalidateQueries({ queryKey: ['product-git', productId] });
      queryClient.invalidateQueries({ queryKey: ['product-changes', productId] });
      setSelectedFile(`${SPEC_DIR}/${name}`);
    },
  });

  const hasSpecDir = specFiles && specFiles.length >= 0;
  const mdFiles = specFiles?.filter(f => f.type === 'file' && f.name.endsWith('.md')) ?? [];

  // Suggest missing standard files
  const existingNames = new Set(mdFiles.map(f => f.name));
  const missingFiles = SPEC_FILES.filter(f => !existingNames.has(f));

  const startEdit = () => {
    setEditContent(fileContent?.content ?? '');
    setEditMode(true);
  };

  return (
    <div className="flex flex-1 min-h-0">
      {/* Spec file list */}
      <div className="w-48 border-r bg-gray-50 flex flex-col shrink-0">
        <div className="px-3 py-2 border-b">
          <p className="text-[11px] font-medium text-gray-500 uppercase tracking-wide">.ai/</p>
        </div>
        <div className="flex-1 overflow-y-auto">
          {mdFiles.map(f => (
            <button
              key={f.path}
              onClick={() => { setSelectedFile(f.path); setEditMode(false); }}
              className={`w-full text-left px-3 py-2 text-xs hover:bg-blue-50 ${
                selectedFile === f.path ? 'bg-blue-100 text-blue-700' : 'text-gray-700'
              }`}
            >
              {f.name}
            </button>
          ))}
          {!hasSpecDir && (
            <p className="px-3 py-4 text-xs text-gray-400">
              Папка .ai/ не найдена
            </p>
          )}
          {missingFiles.length > 0 && (
            <div className="px-3 py-2 border-t">
              <p className="text-[10px] text-gray-400 mb-1">Создать:</p>
              {missingFiles.map(name => (
                <button
                  key={name}
                  onClick={() => createFileMutation.mutate(name)}
                  disabled={createFileMutation.isPending}
                  className="block text-[10px] text-blue-600 hover:underline mb-0.5"
                >
                  + {name}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Content area */}
      <div className="flex-1 flex flex-col min-w-0">
        {selectedFile ? (
          <>
            <div className="px-4 py-2 border-b bg-white flex items-center gap-2 shrink-0">
              <span className="text-xs font-mono text-gray-600 flex-1">{selectedFile}</span>
              {editMode ? (
                <div className="flex gap-1">
                  <button
                    onClick={() => saveMutation.mutate(editContent)}
                    disabled={saveMutation.isPending}
                    className="text-xs px-3 py-1 bg-blue-600 text-white rounded disabled:opacity-50"
                  >
                    {saveMutation.isPending ? '...' : 'Сохранить'}
                  </button>
                  <button
                    onClick={() => setEditMode(false)}
                    className="text-xs px-2 py-1 text-gray-500 hover:text-gray-700"
                  >
                    Отмена
                  </button>
                </div>
              ) : (
                <button
                  onClick={startEdit}
                  className="text-xs px-3 py-1 bg-gray-100 text-gray-700 rounded hover:bg-gray-200"
                >
                  Редактировать
                </button>
              )}
            </div>
            <div className="flex-1 min-h-0 overflow-auto">
              {isLoading ? (
                <p className="text-gray-400 text-sm p-4">Загрузка...</p>
              ) : editMode ? (
                <Editor
                  value={editContent}
                  language="markdown"
                  theme="vs-dark"
                  onChange={(v) => setEditContent(v ?? '')}
                  options={{
                    fontSize: 14,
                    wordWrap: 'on',
                    minimap: { enabled: false },
                    lineNumbers: 'off',
                    padding: { top: 16 },
                    automaticLayout: true,
                  }}
                />
              ) : (
                <div className="p-6 prose prose-sm max-w-none prose-headings:text-gray-900 prose-p:text-gray-700">
                  <ReactMarkdown>{fileContent?.content ?? ''}</ReactMarkdown>
                </div>
              )}
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-gray-400 text-sm">
            Выберите файл спецификации
          </div>
        )}
      </div>
    </div>
  );
}
