import { useEffect, useRef } from "react";
import type { ChatItem } from "../types";
import { isHandoffItem } from "../types";
import { ChatMessage } from "./ChatMessage";
import { HandoffBlock } from "./HandoffBlock";

interface ChatWindowProps {
  items: ChatItem[];
}

export function ChatWindow({ items }: ChatWindowProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (bottomRef.current && typeof bottomRef.current.scrollIntoView === "function") {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [items]);

  if (items.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center text-gray-400">
        No messages yet. Send a message to start.
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto space-y-3 p-4">
      {items.map((item) =>
        isHandoffItem(item) ? (
          <HandoffBlock key={item.id} item={item} />
        ) : (
          <ChatMessage key={item.id} message={item} />
        )
      )}
      <div ref={bottomRef} />
    </div>
  );
}
