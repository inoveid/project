import { useParams, useNavigate } from 'react-router-dom';
import { useState, useEffect, useCallback, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import Editor, { type Monaco } from '@monaco-editor/react';
import { getProduct } from '../api/products';
import { getFileTree, readFile, writeFile, getGitInfo, checkoutBranch, getCommitDetail, getSyncStatus, gitPush, gitPull, addRemote, createBranch, renameBranch, deleteBranch, mergeBranch } from '../api/products';
import type { FileEntry, CommitDetail, SyncStatus } from '../api/products';
import { DiffViewer } from '../components/DiffViewer';
import { SpecPanel } from '../components/SpecPanel';
import { SecretsPanel } from '../components/SecretsPanel';
import { ChangesPanel } from '../components/ChangesPanel';

type ProductTab = 'code' | 'spec' | 'settings';

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
  const [activeSection, setActiveSection] = useState<ProductTab>('code');

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

  const [showBranchInput, setShowBranchInput] = useState(false);
  const [showChanges, setShowChanges] = useState(false);
  const [newBranchName, setNewBranchName] = useState('');
  const [showBranchDropdown, setShowBranchDropdown] = useState(false);
  const [branchSearch, setBranchSearch] = useState('');
  const branchDropdownRef = useRef<HTMLDivElement>(null);
  const [branchContextMenu, setBranchContextMenu] = useState<string | null>(null);
  const [renamingBranch, setRenamingBranch] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const [confirmDeleteBranch, setConfirmDeleteBranch] = useState<string | null>(null);
  const [branchFromName, setBranchFromName] = useState<string | null>(null);
  const [branchError, setBranchError] = useState<string | null>(null);

  const createBranchMutation = useMutation({
    mutationFn: (name: string) => createBranch(id, name),
    onSuccess: () => {
      setShowBranchInput(false);
      setNewBranchName('');
      queryClient.invalidateQueries({ queryKey: ['product-git', id] });
      queryClient.invalidateQueries({ queryKey: ['product-files', id] });
    },
  });

  const renameBranchMutation = useMutation({
    mutationFn: ({ oldName, newName }: { oldName: string; newName: string }) => renameBranch(id, oldName, newName),
    onSuccess: () => {
      setRenamingBranch(null);
      setRenameValue('');
      setBranchContextMenu(null);
      setBranchError(null);
      queryClient.invalidateQueries({ queryKey: ['product-git', id] });
    },
    onError: (err: Error) => setBranchError(err.message),
  });

  const deleteBranchMutation = useMutation({
    mutationFn: (name: string) => deleteBranch(id, name),
    onSuccess: () => {
      setConfirmDeleteBranch(null);
      setBranchContextMenu(null);
      setBranchError(null);
      queryClient.invalidateQueries({ queryKey: ['product-git', id] });
    },
    onError: (err: Error) => setBranchError(err.message),
  });

  const mergeBranchMutation = useMutation({
    mutationFn: (source: string) => mergeBranch(id, source),
    onSuccess: () => {
      setBranchContextMenu(null);
      setBranchError(null);
      queryClient.invalidateQueries({ queryKey: ['product-git', id] });
      queryClient.invalidateQueries({ queryKey: ['product-files', id] });
    },
    onError: (err: Error) => setBranchError(err.message),
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

  // Close branch dropdown on click outside
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (branchDropdownRef.current && !branchDropdownRef.current.contains(e.target as Node)) {
        setShowBranchDropdown(false);
        setBranchSearch('');
        setShowBranchInput(false);
        setNewBranchName('');
        setBranchContextMenu(null);
        setRenamingBranch(null);
        setConfirmDeleteBranch(null);
        setBranchFromName(null);
        setBranchError(null);
      }
    };
    if (showBranchDropdown) {
      document.addEventListener('mousedown', handler);
      return () => document.removeEventListener('mousedown', handler);
    }
  }, [showBranchDropdown]);

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
      <div className="flex items-center gap-2 px-4 py-2 border-b bg-white shrink-0">
        <button onClick={() => navigate(-1)} className="text-sm text-blue-600 hover:underline">
          ← Назад
        </button>
        <span className="text-sm font-medium text-gray-900">{product.name}</span>

        {/* Branch selector dropdown */}
        {gitInfo?.initialized && (
          <div className="relative" ref={branchDropdownRef}>
            <button
              onClick={() => { setShowBranchDropdown(!showBranchDropdown); setBranchSearch(''); }}
              className="flex items-center gap-1.5 text-xs bg-gray-100 hover:bg-gray-200 text-gray-700 pl-2 pr-1.5 py-1 rounded font-mono transition-colors"
            >
              <span className="text-gray-400 text-[10px]">⎇</span>
              <span>{gitInfo.branch}</span>
              <span className="text-gray-400 text-[10px]">▾</span>
            </button>
            {showBranchDropdown && (
              <div className="absolute top-full left-0 mt-1 w-64 bg-white border rounded-lg shadow-lg z-50 overflow-hidden">
                <div className="p-2 border-b">
                  <input
                    type="text"
                    value={branchSearch}
                    onChange={(e) => setBranchSearch(e.target.value)}
                    placeholder="Найти ветку..."
                    autoFocus
                    className="w-full text-xs px-2 py-1.5 border rounded focus:outline-none focus:ring-1 focus:ring-blue-400"
                  />
                </div>
                <div className="max-h-64 overflow-y-auto">
                  {gitInfo.branches
                    ?.filter(b => !branchSearch || b.toLowerCase().includes(branchSearch.toLowerCase()))
                    .map(b => {
                      const isCurrent = b === gitInfo.branch;
                      const isRemote = b.includes('/');
                      const showCtx = branchContextMenu === b;

                      return (
                        <div key={b} className="relative">
                          <div
                            className={`flex items-center px-3 py-1.5 text-xs font-mono hover:bg-blue-50 cursor-pointer group ${
                              isCurrent ? 'bg-blue-50 text-blue-700' : 'text-gray-700'
                            }`}
                            onClick={() => {
                              if (showCtx) { setBranchContextMenu(null); return; }
                              if (!isCurrent) checkoutMutation.mutate(b);
                              setShowBranchDropdown(false);
                              setBranchSearch('');
                            }}
                          >
                            {isCurrent ? <span className="text-blue-500 text-[10px] w-4 shrink-0">●</span> : <span className="w-4 shrink-0" />}
                            <span className="truncate flex-1">{b}</span>
                            {isRemote && <span className="text-[9px] text-gray-400 shrink-0 ml-1">remote</span>}
                            {!isRemote && (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setBranchContextMenu(showCtx ? null : b);
                                  setRenamingBranch(null);
                                  setConfirmDeleteBranch(null);
                                  setBranchFromName(null);
                                  setBranchError(null);
                                }}
                                className="text-gray-400 hover:text-gray-600 opacity-0 group-hover:opacity-100 text-[10px] shrink-0 ml-1"
                              >
                                ⋯
                              </button>
                            )}
                          </div>

                          {/* Context menu */}
                          {showCtx && !isRemote && (
                            <div className="border-t border-b bg-gray-50 py-1">
                              {/* Rename */}
                              {renamingBranch === b ? (
                                <form
                                  className="flex items-center gap-1 px-3 py-1"
                                  onSubmit={(e) => {
                                    e.preventDefault();
                                    if (renameValue.trim() && renameValue.trim() !== b) {
                                      renameBranchMutation.mutate({ oldName: b, newName: renameValue.trim() });
                                    }
                                  }}
                                >
                                  <input
                                    type="text"
                                    value={renameValue}
                                    onChange={(e) => setRenameValue(e.target.value)}
                                    autoFocus
                                    className="flex-1 text-[11px] px-2 py-0.5 border rounded font-mono focus:outline-none focus:ring-1 focus:ring-blue-400"
                                  />
                                  <button type="submit" disabled={!renameValue.trim() || renameValue.trim() === b} className="text-[10px] px-1.5 py-0.5 bg-blue-600 text-white rounded disabled:opacity-50">OK</button>
                                  <button type="button" onClick={() => setRenamingBranch(null)} className="text-[10px] text-gray-400">✕</button>
                                </form>
                              ) : (
                                <button
                                  onClick={(e) => { e.stopPropagation(); setRenamingBranch(b); setRenameValue(b); }}
                                  className="w-full text-left px-3 py-1 text-[11px] text-gray-700 hover:bg-gray-100"
                                >
                                  Переименовать
                                </button>
                              )}

                              {/* New branch from */}
                              {branchFromName === b ? (
                                <form
                                  className="flex items-center gap-1 px-3 py-1"
                                  onSubmit={(e) => {
                                    e.preventDefault();
                                    if (newBranchName.trim()) {
                                      createBranchMutation.mutate(newBranchName.trim());
                                      setBranchFromName(null);
                                      setShowBranchDropdown(false);
                                    }
                                  }}
                                >
                                  <input
                                    type="text"
                                    value={newBranchName}
                                    onChange={(e) => setNewBranchName(e.target.value)}
                                    placeholder="new-branch"
                                    autoFocus
                                    className="flex-1 text-[11px] px-2 py-0.5 border rounded font-mono focus:outline-none focus:ring-1 focus:ring-blue-400"
                                  />
                                  <button type="submit" disabled={!newBranchName.trim()} className="text-[10px] px-1.5 py-0.5 bg-blue-600 text-white rounded disabled:opacity-50">OK</button>
                                  <button type="button" onClick={() => setBranchFromName(null)} className="text-[10px] text-gray-400">✕</button>
                                </form>
                              ) : (
                                <button
                                  onClick={(e) => { e.stopPropagation(); setBranchFromName(b); setNewBranchName(''); }}
                                  className="w-full text-left px-3 py-1 text-[11px] text-gray-700 hover:bg-gray-100"
                                >
                                  Новая ветка от {b.length > 20 ? b.slice(0, 20) + '...' : b}
                                </button>
                              )}

                              {/* Merge */}
                              {!isCurrent && (
                                <button
                                  onClick={(e) => { e.stopPropagation(); mergeBranchMutation.mutate(b); }}
                                  disabled={mergeBranchMutation.isPending}
                                  className="w-full text-left px-3 py-1 text-[11px] text-gray-700 hover:bg-gray-100 disabled:opacity-50"
                                >
                                  {mergeBranchMutation.isPending ? '...' : `Merge в ${gitInfo.branch}`}
                                </button>
                              )}

                              {/* Delete */}
                              {!isCurrent && (
                                confirmDeleteBranch === b ? (
                                  <div className="flex items-center gap-1 px-3 py-1">
                                    <span className="text-[10px] text-red-600">Удалить?</span>
                                    <button
                                      onClick={(e) => { e.stopPropagation(); deleteBranchMutation.mutate(b); }}
                                      disabled={deleteBranchMutation.isPending}
                                      className="text-[10px] px-1.5 py-0.5 bg-red-600 text-white rounded"
                                    >
                                      {deleteBranchMutation.isPending ? '...' : 'Да'}
                                    </button>
                                    <button onClick={() => setConfirmDeleteBranch(null)} className="text-[10px] text-gray-500">Нет</button>
                                  </div>
                                ) : (
                                  <button
                                    onClick={(e) => { e.stopPropagation(); setConfirmDeleteBranch(b); }}
                                    className="w-full text-left px-3 py-1 text-[11px] text-red-600 hover:bg-red-50"
                                  >
                                    Удалить
                                  </button>
                                )
                              )}

                              {/* Error */}
                              {branchError && (
                                <p className="px-3 py-1 text-[10px] text-red-500">{branchError}</p>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })
                  }
                  {gitInfo.branches?.filter(b => !branchSearch || b.toLowerCase().includes(branchSearch.toLowerCase())).length === 0 && (
                    <p className="text-xs text-gray-400 px-3 py-2">Не найдено</p>
                  )}
                </div>
                <div className="border-t p-2">
                  {showBranchInput ? (
                    <form
                      onSubmit={(e) => {
                        e.preventDefault();
                        if (newBranchName.trim()) {
                          createBranchMutation.mutate(newBranchName.trim());
                          setShowBranchDropdown(false);
                        }
                      }}
                      className="flex items-center gap-1"
                    >
                      <input
                        type="text"
                        value={newBranchName}
                        onChange={(e) => setNewBranchName(e.target.value)}
                        placeholder="new-branch"
                        autoFocus
                        className="flex-1 text-xs px-2 py-1 border rounded font-mono focus:outline-none focus:ring-1 focus:ring-blue-400"
                      />
                      <button
                        type="submit"
                        disabled={!newBranchName.trim() || createBranchMutation.isPending}
                        className="text-xs px-2 py-1 bg-blue-600 text-white rounded disabled:opacity-50"
                      >
                        {createBranchMutation.isPending ? '...' : 'OK'}
                      </button>
                    </form>
                  ) : (
                    <button
                      onClick={() => setShowBranchInput(true)}
                      className="w-full text-left text-xs text-blue-600 hover:text-blue-700 px-1 py-0.5"
                    >
                      + Новая ветка
                    </button>
                  )}
                  {createBranchMutation.isError && (
                    <p className="text-[10px] text-red-500 mt-1">{(createBranchMutation.error as Error).message}</p>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Changes badge */}
        {gitInfo?.changed_files ? (
          <button
            onClick={() => setShowChanges(true)}
            className="flex items-center gap-1 text-xs bg-amber-50 text-amber-700 hover:bg-amber-100 px-2 py-1 rounded transition-colors"
            title={`${gitInfo.changed_files} незакоммиченных ${gitInfo.changed_files === 1 ? 'изменение' : 'изменений'}`}
          >
            <span className="text-amber-500 text-[10px]">●</span>
            <span>{gitInfo.changed_files}</span>
          </button>
        ) : null}

        {/* Sync button */}
        {gitInfo?.initialized && syncStatus && (
          syncStatus.has_remote ? (
            <div className="flex items-center gap-1">
              {(syncStatus.ahead ?? 0) > 0 || syncStatus.remote_branch_exists === false || (!syncStatus.upstream && (syncStatus.ahead ?? 0) === 0 && (syncStatus.behind ?? 0) === 0) ? (
                <button
                  onClick={() => pushMutation.mutate()}
                  disabled={pushMutation.isPending}
                  className="flex items-center gap-1 text-xs bg-green-50 text-green-700 hover:bg-green-100 px-2 py-1 rounded transition-colors disabled:opacity-50"
                >
                  {pushMutation.isPending ? '...' : <><span>↑{(syncStatus.ahead ?? 0) > 0 ? syncStatus.ahead : ''}</span><span>Push</span></>}
                </button>
              ) : (syncStatus.behind ?? 0) > 0 ? (
                <button
                  onClick={() => pullMutation.mutate()}
                  disabled={pullMutation.isPending}
                  className="flex items-center gap-1 text-xs bg-orange-50 text-orange-700 hover:bg-orange-100 px-2 py-1 rounded transition-colors disabled:opacity-50"
                >
                  {pullMutation.isPending ? '...' : <><span>↓{syncStatus.behind}</span><span>Pull</span></>}
                </button>
              ) : (
                <span className="text-xs text-gray-400 px-1" title="Синхронизировано">✓</span>
              )}
              {pushMutation.isError && (
                <span className="text-[10px] text-red-500 max-w-[200px] truncate" title={(pushMutation.error as Error).message}>
                  {(pushMutation.error as Error).message}
                </span>
              )}
              {pullMutation.isError && (
                <span className="text-[10px] text-red-500 max-w-[200px] truncate" title={(pullMutation.error as Error).message}>
                  {(pullMutation.error as Error).message}
                </span>
              )}
            </div>
          ) : (
            showRemoteInput ? (
              <div className="flex items-center gap-1">
                <input
                  type="text"
                  value={remoteUrl}
                  onChange={(e) => setRemoteUrl(e.target.value)}
                  placeholder="https://github.com/..."
                  className="text-xs px-2 py-1 border rounded w-48 focus:outline-none focus:ring-1 focus:ring-blue-400"
                />
                <button
                  onClick={() => addRemoteMutation.mutate(remoteUrl)}
                  disabled={!remoteUrl || addRemoteMutation.isPending}
                  className="text-xs px-2 py-1 bg-blue-600 text-white rounded disabled:opacity-50"
                >
                  {addRemoteMutation.isPending ? '...' : 'OK'}
                </button>
                <button
                  onClick={() => { setShowRemoteInput(false); setRemoteUrl(''); }}
                  className="text-xs text-gray-400 hover:text-gray-600"
                >
                  ✕
                </button>
              </div>
            ) : (
              <button
                onClick={() => setShowRemoteInput(true)}
                className="text-xs text-gray-500 hover:text-blue-600 px-1"
                title="Подключить remote"
              >
                ⊕
              </button>
            )
          )
        )}

        {/* Save button */}
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

      {/* Section tabs */}
      <div className="flex items-center gap-0 border-b bg-white shrink-0">
        {(['code', 'spec', 'settings'] as const).map(tab => (
          <button
            key={tab}
            onClick={() => setActiveSection(tab)}
            className={`px-4 py-2 text-xs font-medium border-b-2 transition-colors ${
              activeSection === tab
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {tab === 'code' ? 'Code' : tab === 'spec' ? 'Spec' : 'Settings'}
          </button>
        ))}
      </div>

      <div className="flex flex-1 min-h-0">
        {activeSection === 'spec' ? (
          <SpecPanel productId={id} />
        ) : activeSection === 'settings' ? (
          <SecretsPanel productId={id} />
        ) : (
          <>
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
          </>
        )}
      </div>
      {showChanges && (
        <ChangesPanel
          productId={id}
          onClose={() => setShowChanges(false)}
        />
      )}
    </div>
  );
}
