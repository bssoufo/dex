import { MarkdownRenderer } from "./MarkdownRenderer";
import type { Message } from "../types";

interface Props {
  message: Message;
}

export function MessageBubble({ message }: Props) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[80%] rounded-lg px-4 py-2 ${
          isUser
            ? "bg-blue-600 text-white"
            : "bg-gray-50 border border-gray-200 text-gray-800"
        }`}
      >
        {isUser ? (
          <p>{message.content}</p>
        ) : message.isStreaming && !message.content ? (
          <div className="flex gap-1 py-1">
            <span className="w-2 h-2 rounded-full bg-gray-400 animate-pulse" />
            <span className="w-2 h-2 rounded-full bg-gray-400 animate-pulse [animation-delay:150ms]" />
            <span className="w-2 h-2 rounded-full bg-gray-400 animate-pulse [animation-delay:300ms]" />
          </div>
        ) : (
          <>
            <MarkdownRenderer content={message.content} />
            {message.isStreaming && (
              <span className="inline-block w-2 h-4 bg-gray-400 animate-pulse ml-1 align-text-bottom" />
            )}
          </>
        )}
      </div>
    </div>
  );
}
