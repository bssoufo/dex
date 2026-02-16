import { useState, useCallback, useRef } from "react";
import { streamQuery } from "../services/api";
import type { Message } from "../types";

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const conversationId = useRef<string | null>(null);
  const abortController = useRef<AbortController | null>(null);

  const sendMessage = useCallback(async (question: string) => {
    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: question,
    };

    const assistantMessage: Message = {
      id: crypto.randomUUID(),
      role: "assistant",
      content: "",
      isStreaming: true,
    };

    setMessages((prev) => [...prev, userMessage, assistantMessage]);
    setIsLoading(true);

    abortController.current = new AbortController();

    try {
      await streamQuery(
        question,
        conversationId.current,
        {
          onMetadata(data) {
            conversationId.current = data.conversation_id;
          },

          onToken(data) {
            setMessages((prev) => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              updated[updated.length - 1] = {
                ...last,
                content: last.content + data.content,
              };
              return updated;
            });
          },

          onDone() {
            setMessages((prev) => {
              const updated = [...prev];
              updated[updated.length - 1] = {
                ...updated[updated.length - 1],
                isStreaming: false,
              };
              return updated;
            });
            setIsLoading(false);
          },

          onValidation(data) {
            if (data.warnings && data.warnings.length > 0) {
              console.warn("Validation warnings:", data.warnings);
            }
          },

          onError() {
            setMessages((prev) => {
              const updated = [...prev];
              updated[updated.length - 1] = {
                ...updated[updated.length - 1],
                content: "Sorry, something went wrong. Please try again.",
                isStreaming: false,
              };
              return updated;
            });
            setIsLoading(false);
          },
        },
        abortController.current.signal,
      );
    } catch {
      // fetchEventSource throws on abort or onerror rethrow -- already handled
    }
  }, []);

  const resetConversation = useCallback(() => {
    abortController.current?.abort();
    setMessages([]);
    conversationId.current = null;
    setIsLoading(false);
  }, []);

  return { messages, isLoading, sendMessage, resetConversation };
}
