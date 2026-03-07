import { useState } from "react";
import { useCreateWorkspace, useWorkspaces } from "../hooks/useWorkspaces";

type FormState = { name: string; cloneUrl: string };

const EMPTY_FORM: FormState = { name: "", cloneUrl: "" };

export function WorkspacePanel() {
  const { data: workspaces, isLoading } = useWorkspaces();
  const createWorkspace = useCreateWorkspace();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    createWorkspace.mutate(
      { name: form.name, clone_url: form.cloneUrl || undefined },
      {
        onSuccess: () => {
          setForm(EMPTY_FORM);
          setShowForm(false);
        },
      },
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg font-semibold text-gray-900">Workspaces</h2>
        {!showForm && (
          <button
            onClick={() => setShowForm(true)}
            className="border px-3 py-1.5 rounded text-sm hover:bg-gray-50"
          >
            New Workspace
          </button>
        )}
      </div>

      {showForm && (
        <form
          onSubmit={handleSubmit}
          className="mb-4 p-4 border rounded bg-gray-50 flex flex-col gap-3"
        >
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Name
            </label>
            <input
              type="text"
              required
              placeholder="my-project"
              value={form.name}
              onChange={(e) => setForm((s) => ({ ...s, name: e.target.value }))}
              className="w-full border rounded px-3 py-1.5 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Clone URL{" "}
              <span className="font-normal text-gray-400">(optional — leave empty to init)</span>
            </label>
            <input
              type="url"
              placeholder="https://github.com/org/repo"
              value={form.cloneUrl}
              onChange={(e) => setForm((s) => ({ ...s, cloneUrl: e.target.value }))}
              className="w-full border rounded px-3 py-1.5 text-sm"
            />
          </div>
          {createWorkspace.error && (
            <p className="text-sm text-red-600">{createWorkspace.error.message}</p>
          )}
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={createWorkspace.isPending}
              className="bg-blue-600 text-white px-4 py-1.5 rounded text-sm hover:bg-blue-700 disabled:opacity-50"
            >
              {createWorkspace.isPending
                ? form.cloneUrl
                  ? "Cloning..."
                  : "Creating..."
                : form.cloneUrl
                  ? "Clone"
                  : "Create"}
            </button>
            <button
              type="button"
              onClick={() => { setShowForm(false); setForm(EMPTY_FORM); }}
              className="border px-4 py-1.5 rounded text-sm hover:bg-gray-100"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {isLoading ? (
        <p className="text-sm text-gray-400">Loading...</p>
      ) : workspaces && workspaces.length > 0 ? (
        <ul className="space-y-1">
          {workspaces.map((ws) => (
            <li key={ws.name} className="flex items-center gap-2 text-sm">
              <span className="text-green-600">&#9679;</span>
              <span className="font-medium">{ws.name}</span>
              <span className="text-gray-400 font-mono text-xs">{ws.path}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-gray-400">No workspaces yet.</p>
      )}
    </div>
  );
}
