import { fetchEventSource } from "@microsoft/fetch-event-source";
import type { StreamCallbacks } from "../types";

export const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";

export async function streamQuery(
  question: string,
  conversationId: string | null,
  callbacks: StreamCallbacks,
  signal: AbortSignal,
): Promise<void> {
  await fetchEventSource(`${API_BASE}/query/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      conversation_id: conversationId,
    }),
    signal,
    openWhenHidden: true,

    onmessage(ev) {
      const data = JSON.parse(ev.data);

      switch (ev.event) {
        case "metadata":
          callbacks.onMetadata(data);
          break;
        case "token":
          callbacks.onToken(data);
          break;
        case "done":
          callbacks.onDone(data);
          break;
        case "validation":
          callbacks.onValidation(data);
          break;
      }
    },

    onerror(err) {
      callbacks.onError(err instanceof Error ? err : new Error(String(err)));
      throw err; // Stop retrying
    },
  });
}
