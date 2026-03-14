import { useParams, useNavigate } from 'react-router-dom';
import { useState, useEffect, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getProduct } from '../api/products';
import { getFileTree, readFile, writeFile, getGitInfo } from '../api/products';
import type { FileEntry, GitInfo } from '../api/products';

export function ProductPage() {
  const { productId } = useParams<{ productId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const id = productId ?? '';

  const { data: product } = useQuery({
    queryKey: ['product', id],
    queryFn: () => getProduct(id),
    enabled: !!id,
  });

  const [currentPath, setCurrentPath] = useState('');
  const [openFile, setOpenFile] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState('');
  const [modified, setModified] = useState(false);

  const { data: files } = useQuery({
    queryKey: ['product-files', id, currentPath],
    queryFn: () => getFileTree(id, currentPath),
    enabled: !!id,
  });

  const { data: gitInfo } = useQuery({
    queryKey: ['product-git', id],
    queryFn: () => getGitInfo(id),
    enabled: !!id,
    refetchInterval: 10000,
  });

  const { data: fileData } = useQuery({
    queryKey: ['product-file', id, openFile],
    queryFn: () => readFile(id, openFile!),
    enabled: !!id && !!openFile,
  });

  useEffect(() => {
    if (fileData) {
      setFileContent(fileData.content);
      setModified(false);
    }
  }, [fileData]);

  const saveMutation = useMutation({
    mutationFn: () => writeFile(id, openFile!, fileContent),
    onSuccess: () => {
      setModified(false);
      queryClient.invalidateQueries({ queryKey: ['product-git', id] });
    },
  });

  const handleFileClick = (entry: FileEntry) => {
    if (entry.type === 'dir') {
      setCurrentPath(entry.path);
      setOpenFile(null);
    } else {
      setOpenFile(entry.path);
    }
  };

  const handleSave = useCallback(() => {
    if (openFile && modified) saveMutation.mutate();
  }, [openFile, modified, saveMutation]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 's') {
        e.preventDefault();
        handleSave();
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [handleSave]);

  if (!product) {
    return <p className="text-gray-400 p-4">Загрузка...</p>;
  }

  const pathParts = currentPath ? currentPath.split('/') : [];

  return (
    <div className="flex flex-col h-[calc(100vh-64px)]">
      {/* Top bar */}
      <div className="flex items-center gap-3 px-4 py-2 border-b bg-white">
        <button onClick={() => navigate(-1)} className="text-sm text-blue-600 hover:underline">← Назад</button>
        <span className="text-sm font-medium text-gray-900">{product.name}</span>
        {gitInfo?.initialized && (
          <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded font-mono">
            {gitInfo.branch}
          </span>
        )}
        {gitInfo?.changed_files ? (
          <span className="text-xs text-amber-600">{gitInfo.changed_files} изменений</span>
        ) : null}
        {modified && (
          <button
            onClick={handleSave}
            disabled={saveMutation.isPending}
            className="ml-auto text-xs bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700 disabled:opacity-50"
          >
            {saveMutation.isPending ? 'Сохранение...' : 'Сохранить'}
          </button>
        )}
      </div>

      <div className="flex flex-1 min-h-0">
        {/* File tree */}
        <div className="w-64 border-r bg-gray-50 flex flex-col overflow-hidden">
          {/* Breadcrumb */}
          <div className="px-3 py-2 border-b text-xs flex items-center gap-1 flex-wrap">
            <button
              onClick={() => { setCurrentPath(''); setOpenFile(null); }}
              className="text-blue-600 hover:underline"
            >
              root
            </button>
            {pathParts.map((part, i) => (
              <span key={i} className="flex items-center gap-1">
                <span className="text-gray-400">/</span>
                <button
                  onClick={() => {
                    setCurrentPath(pathParts.slice(0, i + 1).join('/'));
                    setOpenFile(null);
                  }}
                  className="text-blue-600 hover:underline"
                >
                  {part}
                </button>
              </span>
            ))}
          </div>
          {/* File list */}
          <div className="flex-1 overflow-y-auto">
            {currentPath && (
              <button
                onClick={() => {
                  const parent = pathParts.slice(0, -1).join('/');
                  setCurrentPath(parent);
                }}
                className="w-full text-left px-3 py-1.5 text-xs text-gray-500 hover:bg-gray-100"
              >
                ..
              </button>
            )}
            {files?.map((entry) => (
              <button
                key={entry.path}
                onClick={() => handleFileClick(entry)}
                className={`w-full text-left px-3 py-1.5 text-xs hover:bg-blue-50 flex items-center gap-2 ${
                  openFile === entry.path ? 'bg-blue-100 text-blue-700' : 'text-gray-700'
                }`}
              >
                <span className="text-gray-400">{entry.type === 'dir' ? '📁' : '📄'}</span>
                <span className="truncate">{entry.name}</span>
                {entry.type === 'file' && (
                  <span className="ml-auto text-gray-300 text-[10px]">
                    {entry.size > 1024 ? `${Math.round(entry.size / 1024)}K` : `${entry.size}B`}
                  </span>
                )}
              </button>
            ))}
            {files?.length === 0 && (
              <p className="text-xs text-gray-400 px-3 py-4">Пусто</p>
            )}
          </div>
        </div>

        {/* Editor area */}
        <div className="flex-1 flex flex-col min-w-0">
          {openFile ? (
            <>
              <div className="px-3 py-1.5 border-b bg-gray-50 flex items-center gap-2">
                <span className="text-xs text-gray-500 font-mono truncate">{openFile}</span>
                {modified && <span className="text-xs text-amber-500">●</span>}
              </div>
              <div className="flex-1 min-h-0">
                <textarea
                  value={fileContent}
                  onChange={(e) => { setFileContent(e.target.value); setModified(true); }}
                  className="w-full h-full p-4 font-mono text-sm resize-none focus:outline-none"
                  spellCheck={false}
                />
              </div>
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center text-gray-400 text-sm">
              Выберите файл для просмотра
            </div>
          )}
        </div>

        {/* Git panel */}
        {gitInfo?.initialized && (
          <div className="w-72 border-l bg-gray-50 flex flex-col overflow-hidden">
            <div className="px-3 py-2 border-b">
              <p className="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Git</p>
            </div>
            <div className="flex-1 overflow-y-auto">
              {/* Branch */}
              <div className="px-3 py-2 border-b">
                <p className="text-[10px] text-gray-400 mb-1">Ветка</p>
                <p className="text-xs font-mono text-gray-800">{gitInfo.branch}</p>
                {gitInfo.branches && gitInfo.branches.length > 1 && (
                  <p className="text-[10px] text-gray-400 mt-1">
                    {gitInfo.branches.length} веток
                  </p>
                )}
              </div>
              {/* Commits */}
              <div className="px-3 py-2">
                <p className="text-[10px] text-gray-400 mb-2">Последние коммиты</p>
                {gitInfo.commits?.map((c, i) => (
                  <div key={i} className="mb-2 last:mb-0">
                    <div className="flex items-center gap-1.5">
                      <span className="text-[10px] font-mono text-blue-600">{c.hash}</span>
                      <span className="text-[10px] text-gray-400">{c.date}</span>
                    </div>
                    <p className="text-xs text-gray-700 truncate">{c.message}</p>
                    <p className="text-[10px] text-gray-400">{c.author}</p>
                  </div>
                ))}
                {(!gitInfo.commits || gitInfo.commits.length === 0) && (
                  <p className="text-xs text-gray-400">Нет коммитов</p>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
