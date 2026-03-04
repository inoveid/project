import Markdown from "react-markdown";
import type { Message } from "../types";
import { ToolUseBlock } from "./ToolUseBlock";

interface ChatMessageProps {
  message: Message;
}

export function ChatMessage({ message }: ChatMessageProps) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[70%] rounded-lg bg-blue-600 px-4 py-2 text-white">
          <p className="whitespace-pre-wrap text-sm">{message.content}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div className="max-w-[70%] rounded-lg bg-white px-4 py-2 shadow-sm border border-gray-200">
        <div className="prose prose-sm prose-gray max-w-none text-sm text-gray-800">
          <Markdown>{message.content}</Markdown>
        </div>
        {message.tool_uses && message.tool_uses.length > 0 && (
          <div className="mt-2">
            {message.tool_uses.map((tu, idx) => (
              <ToolUseBlock key={idx} toolUse={tu} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
