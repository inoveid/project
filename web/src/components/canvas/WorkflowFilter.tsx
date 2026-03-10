import type { Workflow } from "../../types";
import { getWorkflowColor } from "./canvasUtils";

interface WorkflowFilterProps {
  workflows: Workflow[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
}

export function WorkflowFilter({ workflows, selectedId, onSelect }: WorkflowFilterProps) {
  if (workflows.length === 0) return null;

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-gray-500 font-medium">Workflow:</span>
      <button
        onClick={() => onSelect(null)}
        className={`text-xs px-2 py-1 rounded border ${
          selectedId === null
            ? "bg-gray-800 text-white border-gray-800"
            : "bg-white text-gray-600 border-gray-200 hover:bg-gray-50"
        }`}
      >
        All
      </button>
      {workflows.map((wf, index) => {
        const color = getWorkflowColor(index);
        const isSelected = selectedId === wf.id;
        return (
          <button
            key={wf.id}
            onClick={() => onSelect(wf.id)}
            className={`text-xs px-2 py-1 rounded border flex items-center gap-1 ${
              isSelected
                ? "bg-gray-800 text-white border-gray-800"
                : "bg-white text-gray-600 border-gray-200 hover:bg-gray-50"
            }`}
          >
            <span
              className="inline-block w-2 h-2 rounded-full"
              style={{ backgroundColor: color }}
            />
            {wf.name}
          </button>
        );
      })}
    </div>
  );
}
