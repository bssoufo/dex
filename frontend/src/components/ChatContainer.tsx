import { useRef, useEffect } from "react";
import { useChat } from "../hooks/useChat";
import { MessageBubble } from "./MessageBubble";
import { ChatInput } from "./ChatInput";

export function ChatContainer() {
  const { messages, isLoading, sendMessage, resetConversation } = useChat();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="flex flex-col h-screen max-w-4xl mx-auto bg-white">
      {/* Header */}
      <header className="flex items-center justify-between border-b px-6 py-3 bg-white">
        <div>
          <h1 className="text-lg font-semibold text-gray-800">Dex</h1>
          <p className="text-sm text-gray-500">
            Spa Parts Technical Assistant
          </p>
        </div>
        <button
          type="button"
          onClick={resetConversation}
          className="text-sm text-gray-500 hover:text-gray-700"
        >
          New Chat
        </button>
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4 bg-gray-50">
        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <p className="text-gray-400 text-lg">
              What would you like to know about spa specifications?
            </p>
          </div>
        ) : (
          messages.map((msg) => <MessageBubble key={msg.id} message={msg} />)
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <ChatInput onSubmit={sendMessage} disabled={isLoading} />
    </div>
  );
}
