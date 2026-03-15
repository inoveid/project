import { useParams, useNavigate } from 'react-router-dom';
import { useState, useEffect, useCallback, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import Editor, { type Monaco } from '@monaco-editor/react';
import { getProduct } from '../api/products';
import { getFileTree, readFile, writeFile, getGitInfo, checkoutBranch, getCommitDetail, getSyncStatus, gitPush, gitPull, addRemote } from '../api/products';
import type { FileEntry, CommitDetail, SyncStatus } from '../api/products';
import { DiffViewer } from '../components/DiffViewer';

// Map file extension to Monaco language
function getLanguage(path: string): string {
  const ext = path.split('.').pop()?.toLowerCase() ?? '';
  const map: Record<string, string> = {
    ts: 'typescript', tsx: 'typescript', js: 'javascript', jsx: 'javascript',
    py: 'python', json: 'json', md: 'markdown', html: 'html', css: 'css',
    scss: 'scss', less: 'less', yaml: 'yaml', yml: 'yaml', xml: 'xml',
    sql: 'sql', sh: 'shell', bash: 'shell', zsh: 'shell', dockerfile: 'dockerfile',
    rs: 'rust', go: 'go', java: 'java', kt: 'kotlin', rb: 'ruby',
    php: 'php', c: 'c', cpp: 'cpp', h: 'c', hpp: 'cpp',
    toml: 'ini', ini: 'ini', env: 'ini', gitignore: 'plaintext',
    svg: 'xml', graphql: 'graphql', gql: 'graphql',
  };
  return map[ext] || 'plaintext';
}

interface OpenTab {
  path: string;
  content: string;
  originalContent: string;
  language: string;
}

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
  const [openTabs, setOpenTabs] = useState<OpenTab[]>([]);
  const [activeTab, setActiveTab] = useState<string | null>(null);
  const [selectedCommit, setSelectedCommit] = useState<CommitDetail | null>(null);
  const editorRef = useRef<any>(null);

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

  const saveMutation = useMutation({
    mutationFn: ({ path, content }: { path: string; content: string }) =>
      writeFile(id, path, content),
    onSuccess: (_, { path, content }) => {
      setOpenTabs(prev => prev.map(t =>
        t.path === path ? { ...t, originalContent: content } : t
      ));
      queryClient.invalidateQueries({ queryKey: ['product-git', id] });
    },
  });

  const checkoutMutation = useMutation({
    mutationFn: (branch: string) => checkoutBranch(id, branch),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['product-git', id] });
      queryClient.invalidateQueries({ queryKey: ['product-files', id] });
      setOpenTabs([]);
      setActiveTab(null);
      setSelectedCommit(null);
    },
  });

  const { data: syncStatus, refetch: refetchSync } = useQuery({
    queryKey: ['product-sync', id],
    queryFn: () => getSyncStatus(id),
    enabled: !!id && !!gitInfo?.initialized,
    refetchOnWindowFocus: true,
  });

  const [remoteUrl, setRemoteUrl] = useState('');
  const [showRemoteInput, setShowRemoteInput] = useState(false);

  const pushMutation = useMutation({
    mutationFn: () => gitPush(id),
    onSuccess: () => {
      refetchSync();
      queryClient.invalidateQueries({ queryKey: ['product-git', id] });
    },
  });

  const pullMutation = useMutation({
    mutationFn: () => gitPull(id),
    onSuccess: () => {
      refetchSync();
      queryClient.invalidateQueries({ queryKey: ['product-git', id] });
      queryClient.invalidateQueries({ queryKey: ['product-files', id] });
    },
  });

  const addRemoteMutation = useMutation({
    mutationFn: (url: string) => addRemote(id, url),
    onSuccess: () => {
      setShowRemoteInput(false);
      setRemoteUrl('');
      refetchSync();
    },
  });

  // Open file in a tab
  const openFileInTab = useCallback(async (entry: FileEntry) => {
    if (entry.type === 'dir') {
      setCurrentPath(entry.path);
      return;
    }

    // Already open? Just switch
    const existing = openTabs.find(t => t.path === entry.path);
    if (existing) {
      setActiveTab(entry.path);
      setSelectedCommit(null);
      return;
    }

    // Load and open
    try {
      const data = await readFile(id, entry.path);
      const tab: OpenTab = {
        path: entry.path,
        content: data.content,
        originalContent: data.content,
        language: getLanguage(entry.path),
      };
      setOpenTabs(prev => [...prev, tab]);
      setActiveTab(entry.path);
      setSelectedCommit(null);
    } catch {
      // ignore
    }
  }, [id, openTabs]);

  // Close tab
  const closeTab = useCallback((path: string, e?: React.MouseEvent) => {
    e?.stopPropagation();
    setOpenTabs(prev => {
      const next = prev.filter(t => t.path !== path);
      if (activeTab === path) {
        setActiveTab(next.length > 0 ? next[next.length - 1].path : null);
      }
      return next;
    });
  }, [activeTab]);

  // Update content in tab
  const handleEditorChange = useCallback((value: string | undefined) => {
    if (!activeTab || value === undefined) return;
    setOpenTabs(prev => prev.map(t =>
      t.path === activeTab ? { ...t, content: value } : t
    ));
  }, [activeTab]);

  // Save current file
  const handleSave = useCallback(() => {
    const tab = openTabs.find(t => t.path === activeTab);
    if (tab && tab.content !== tab.originalContent) {
      saveMutation.mutate({ path: tab.path, content: tab.content });
    }
  }, [activeTab, openTabs, saveMutation]);

  // Ctrl+S
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

  // Commit detail click
  const handleCommitClick = async (hash: string) => {
    try {
      const detail = await getCommitDetail(id, hash);
      setSelectedCommit(detail);
      setActiveTab(null);
    } catch {
      setSelectedCommit(null);
    }
  };

  const currentTab = openTabs.find(t => t.path === activeTab);
  const isModified = (path: string) => {
    const tab = openTabs.find(t => t.path === path);
    return tab ? tab.content !== tab.originalContent : false;
  };
  const hasAnyModified = openTabs.some(t => t.content !== t.originalContent);

  if (!product) {
    return <p className="text-gray-400 p-4">Загрузка...</p>;
  }

  const pathParts = currentPath ? currentPath.split('/') : [];

  return (
    <div className="flex flex-col h-[calc(100vh-64px)]">
      {/* Top bar */}
      <div className="flex items-center gap-3 px-4 py-2 border-b bg-white shrink-0">
        <button onClick={() => navigate(-1)} className="text-sm text-blue-600 hover:underline">
          ← Назад
        </button>
        <span className="text-sm font-medium text-gray-900">{product.name}</span>
        {gitInfo?.initialized && (
          <select
            value={gitInfo.branch}
            onChange={(e) => checkoutMutation.mutate(e.target.value)}
            disabled={checkoutMutation.isPending}
            className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded font-mono border-0 focus:outline-none focus:ring-1 focus:ring-blue-400"
          >
            {gitInfo.branches?.map((b) => (
              <option key={b} value={b}>{b}</option>
            ))}
          </select>
        )}
        {gitInfo?.changed_files ? (
          <span className="text-xs text-amber-600">{gitInfo.changed_files} изменений</span>
        ) : null}
        {hasAnyModified && (
          <button
            onClick={handleSave}
            disabled={saveMutation.isPending}
            className="ml-auto text-xs bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700 disabled:opacity-50"
          >
            {saveMutation.isPending ? 'Сохранение...' : 'Сохранить (Ctrl+S)'}
          </button>
        )}
      </div>

      <div className="flex flex-1 min-h-0">
        {/* File tree */}
        <div className="w-56 border-r bg-gray-50 flex flex-col overflow-hidden shrink-0">
          {/* Breadcrumb */}
          <div className="px-3 py-2 border-b text-xs flex items-center gap-1 flex-wrap shrink-0">
            <button
              onClick={() => setCurrentPath('')}
              className={`hover:underline ${currentPath ? 'text-blue-600' : 'text-gray-800 font-medium'}`}
            >
              root
            </button>
            {pathParts.map((part, i) => (
              <span key={i} className="flex items-center gap-1">
                <span className="text-gray-400">/</span>
                <button
                  onClick={() => setCurrentPath(pathParts.slice(0, i + 1).join('/'))}
                  className={`hover:underline ${
                    i === pathParts.length - 1 ? 'text-gray-800 font-medium' : 'text-blue-600'
                  }`}
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
                onClick={() => setCurrentPath(pathParts.slice(0, -1).join('/'))}
                className="w-full text-left px-3 py-1.5 text-xs text-gray-500 hover:bg-gray-100"
              >
                ..
              </button>
            )}
            {files?.map((entry) => (
              <button
                key={entry.path}
                onClick={() => openFileInTab(entry)}
                className={`w-full text-left px-3 py-1.5 text-xs hover:bg-blue-50 flex items-center gap-2 ${
                  activeTab === entry.path ? 'bg-blue-100 text-blue-700' : 'text-gray-700'
                }`}
              >
                <span className="text-[10px] text-gray-400 w-3">{entry.type === 'dir' ? '📁' : '📄'}</span>
                <span className="truncate flex-1">{entry.name}</span>
                {entry.type === 'file' && (
                  <span className="text-gray-300 text-[10px] shrink-0">
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
          {/* Tabs */}
          {openTabs.length > 0 && (
            <div className="flex border-b bg-gray-100 overflow-x-auto shrink-0">
              {openTabs.map((tab) => {
                const fileName = tab.path.split('/').pop() ?? tab.path;
                const modified = isModified(tab.path);
                return (
                  <button
                    key={tab.path}
                    onClick={() => { setActiveTab(tab.path); setSelectedCommit(null); }}
                    className={`flex items-center gap-1.5 px-3 py-1.5 text-xs border-r border-gray-200 shrink-0 ${
                      activeTab === tab.path
                        ? 'bg-white text-gray-900 border-b-2 border-b-blue-500'
                        : 'text-gray-500 hover:bg-gray-50'
                    }`}
                  >
                    <span className="truncate max-w-[120px]">{fileName}</span>
                    {modified && <span className="text-amber-500 text-[10px]">●</span>}
                    <span
                      onClick={(e) => closeTab(tab.path, e)}
                      className="text-gray-400 hover:text-gray-700 ml-1"
                    >
                      ×
                    </span>
                  </button>
                );
              })}
            </div>
          )}

          {/* Monaco editor */}
          {currentTab ? (
            <div className="flex-1 min-h-0">
              <Editor
                key={currentTab.path}
                defaultValue={currentTab.content}
                language={currentTab.language}
                theme="vs-dark"
                onChange={handleEditorChange}
                onMount={(editor) => { editorRef.current = editor; }}
                options={{
                  fontSize: 13,
                  fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace",
                  minimap: { enabled: true },
                  scrollBeyondLastLine: false,
                  wordWrap: 'on',
                  lineNumbers: 'on',
                  renderWhitespace: 'selection',
                  bracketPairColorization: { enabled: true },
                  automaticLayout: true,
                  tabSize: 2,
                  formatOnPaste: true,
                  suggestOnTriggerCharacters: true,
                  folding: true,
                  foldingStrategy: 'indentation',
                  links: true,
                  padding: { top: 8 },
                }}
              />
            </div>
          ) : selectedCommit ? (
            <>
              <div className="px-3 py-1.5 border-b bg-gray-50 flex items-center gap-2 shrink-0">
                <span className="text-xs font-mono text-blue-600">{selectedCommit.hash.slice(0, 8)}</span>
                <span className="text-xs text-gray-700 truncate flex-1">{selectedCommit.message}</span>
                <span className="text-[10px] text-gray-400">{selectedCommit.author}</span>
                <button
                  onClick={() => setSelectedCommit(null)}
                  className="text-gray-400 hover:text-gray-600 text-sm"
                >
                  ×
                </button>
              </div>
              <div className="flex-1 min-h-0">
                {selectedCommit.files && selectedCommit.files.length > 0 ? (
                  <DiffViewer
                    files={selectedCommit.files}
                    totalAdditions={selectedCommit.total_additions ?? 0}
                    totalDeletions={selectedCommit.total_deletions ?? 0}
                  />
                ) : (
                  <div className="flex items-center justify-center h-32 text-gray-400 text-sm">
                    Нет изменений
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center bg-[#1e1e1e] text-gray-500 text-sm">
              Выберите файл или коммит для просмотра
            </div>
          )}
        </div>

        {/* Git panel */}
        {gitInfo?.initialized && (
          <div className="w-64 border-l bg-gray-50 flex flex-col overflow-hidden shrink-0">
            <div className="px-3 py-2 border-b shrink-0">
              <p className="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Git</p>
            </div>
            <div className="flex-1 overflow-y-auto">
              {/* Sync status */}
              <div className="px-3 py-2 border-b">
                {syncStatus?.has_remote ? (
                  <div className="space-y-1.5">
                    <div className="flex items-center gap-1.5">
                      <span className="text-[10px] text-gray-400 truncate flex-1" title={syncStatus.remote_url}>
                        {syncStatus.remote_url?.replace(/^https?:\/\//, '').replace(/\.git$/, '') ?? syncStatus.remote}
                      </span>
                      <button
                        onClick={() => refetchSync()}
                        className="text-[10px] text-gray-400 hover:text-gray-600"
                        title="Обновить"
                      >
                        ⟳
                      </button>
                    </div>
                    <div className="flex items-center gap-1">
                      {(syncStatus.ahead ?? 0) > 0 && (
                        <span className="text-[10px] text-green-600">↑{syncStatus.ahead}</span>
                      )}
                      {(syncStatus.behind ?? 0) > 0 && (
                        <span className="text-[10px] text-orange-600">↓{syncStatus.behind}</span>
                      )}
                      {(syncStatus.ahead ?? 0) === 0 && (syncStatus.behind ?? 0) === 0 && syncStatus.upstream && (
                        <span className="text-[10px] text-gray-400">Up to date</span>
                      )}
                      {!syncStatus.upstream && (
                        <span className="text-[10px] text-gray-400">Нет upstream</span>
                      )}
                    </div>
                    <div className="flex gap-1">
                      <button
                        onClick={() => pushMutation.mutate()}
                        disabled={pushMutation.isPending}
                        className="flex-1 text-[10px] px-2 py-1 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                      >
                        {pushMutation.isPending ? '...' : `Push${(syncStatus.ahead ?? 0) > 0 ? ` (${syncStatus.ahead})` : ''}`}
                      </button>
                      <button
                        onClick={() => pullMutation.mutate()}
                        disabled={pullMutation.isPending || (syncStatus.behind ?? 0) === 0}
                        className="flex-1 text-[10px] px-2 py-1 bg-gray-200 text-gray-700 rounded hover:bg-gray-300 disabled:opacity-50"
                      >
                        {pullMutation.isPending ? '...' : `Pull${(syncStatus.behind ?? 0) > 0 ? ` (${syncStatus.behind})` : ''}`}
                      </button>
                    </div>
                    {pushMutation.isError && (
                      <p className="text-[10px] text-red-500 break-all">{(pushMutation.error as Error).message}</p>
                    )}
                    {pullMutation.isError && (
                      <p className="text-[10px] text-red-500 break-all">{(pullMutation.error as Error).message}</p>
                    )}
                  </div>
                ) : syncStatus && !syncStatus.has_remote ? (
                  <div className="space-y-1.5">
                    <p className="text-[10px] text-gray-400">Нет remote</p>
                    {showRemoteInput ? (
                      <div className="space-y-1">
                        <input
                          type="text"
                          value={remoteUrl}
                          onChange={(e) => setRemoteUrl(e.target.value)}
                          placeholder="https://github.com/..."
                          className="w-full text-[10px] px-2 py-1 border rounded"
                        />
                        <div className="flex gap-1">
                          <button
                            onClick={() => addRemoteMutation.mutate(remoteUrl)}
                            disabled={!remoteUrl || addRemoteMutation.isPending}
                            className="flex-1 text-[10px] px-2 py-1 bg-blue-600 text-white rounded disabled:opacity-50"
                          >
                            {addRemoteMutation.isPending ? '...' : 'Добавить'}
                          </button>
                          <button
                            onClick={() => { setShowRemoteInput(false); setRemoteUrl(''); }}
                            className="text-[10px] px-2 py-1 text-gray-500 hover:text-gray-700"
                          >
                            ✕
                          </button>
                        </div>
                        {addRemoteMutation.isError && (
                          <p className="text-[10px] text-red-500">{(addRemoteMutation.error as Error).message}</p>
                        )}
                      </div>
                    ) : (
                      <button
                        onClick={() => setShowRemoteInput(true)}
                        className="text-[10px] text-blue-600 hover:underline"
                      >
                        + Добавить remote
                      </button>
                    )}
                  </div>
                ) : (
                  <p className="text-[10px] text-gray-300">Загрузка...</p>
                )}
              </div>

              {/* Commits */}
              <div className="px-3 py-2">
                <p className="text-[10px] text-gray-400 mb-2">Последние коммиты</p>
                {gitInfo.commits?.map((c, i) => (
                  <button
                    key={i}
                    onClick={() => handleCommitClick(c.hash)}
                    className={`w-full text-left mb-1 last:mb-0 p-1.5 rounded transition-colors ${
                      selectedCommit?.hash.startsWith(c.hash)
                        ? 'bg-blue-50 border border-blue-200'
                        : 'hover:bg-gray-100'
                    }`}
                  >
                    <div className="flex items-center gap-1.5">
                      <span className="text-[10px] font-mono text-blue-600">{c.hash}</span>
                      <span className="text-[10px] text-gray-400">{c.date}</span>
                    </div>
                    <p className="text-xs text-gray-700 truncate">{c.message}</p>
                    <p className="text-[10px] text-gray-400">{c.author}</p>
                  </button>
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
