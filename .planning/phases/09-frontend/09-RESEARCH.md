# Phase 9: Frontend - Research

**Researched:** 2026-02-16
**Domain:** React chat interface with SSE streaming and markdown table rendering
**Confidence:** HIGH

## Summary

This phase builds a React + Vite + TypeScript chat interface that connects to the existing FastAPI backend. The interface must render markdown (including GFM tables) for technical spec responses and stream responses via SSE for a responsive feel.

The backend currently uses `ainvoke()` (full response, no streaming). Success Criterion 1 requires SSE streaming, which means the backend `/query` endpoint must be augmented with a streaming variant. LangGraph's supervisor pattern has **known issues with token-level streaming** (the `create_supervisor` function wraps agents in subgraphs, causing `astream` with `stream_mode="messages"` to return complete messages instead of token chunks). The pragmatic approach is to stream at the **node output level** using `astream(stream_mode="updates")` or to use `astream_events(version="v2")` with careful filtering -- or to accept chunk-level streaming of the final assembled response text rather than true token-by-token from the LLM.

The frontend stack is straightforward: React 19 + Vite 6 + TypeScript + Tailwind CSS v4.1 for styling, react-markdown with remark-gfm for rendering, and `@microsoft/fetch-event-source` for consuming POST-based SSE. No routing library is needed (single-page chat).

**Primary recommendation:** Build a minimal, professional chat UI with Tailwind. Add a `/query/stream` SSE endpoint to FastAPI that streams the final agent response progressively. Use react-markdown + remark-gfm for all response rendering including tables.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| React | 19.x | UI framework | Locked decision from project charter |
| Vite | 6.x | Build tool / dev server | Locked decision; fast HMR, native TS support |
| TypeScript | 5.7+ | Type safety | Standard for production React in 2026 |
| Tailwind CSS | 4.1 | Utility-first CSS | No config file needed in v4; direct Vite plugin; professional look with minimal effort |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| react-markdown | 9.x | Render markdown to React elements | All agent response rendering |
| remark-gfm | 4.x | GFM table/strikethrough/task support | Required for table rendering (UI-02) |
| @microsoft/fetch-event-source | 2.x | POST-based SSE client | Consuming streaming responses (native EventSource only supports GET) |
| sse-starlette | 2.x | FastAPI SSE response helper (backend) | Backend streaming endpoint |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Tailwind CSS | Plain CSS / CSS Modules | Tailwind is faster for prototyping; no design system needed for this internal tool |
| react-markdown | markdown-to-jsx | markdown-to-jsx has built-in GFM but react-markdown has larger ecosystem and plugin architecture |
| @microsoft/fetch-event-source | Native EventSource | Native EventSource only supports GET requests; our endpoint is POST |
| sse-starlette | FastAPI StreamingResponse | StreamingResponse works fine for SSE; sse-starlette adds proper event types and disconnect detection. Either works -- StreamingResponse is simpler |

**Installation (frontend):**
```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install react-markdown remark-gfm @microsoft/fetch-event-source
npm install tailwindcss @tailwindcss/vite
```

**Installation (backend addition):**
```bash
pip install sse-starlette
```

## Architecture Patterns

### Recommended Project Structure
```
frontend/
├── index.html
├── vite.config.ts          # React + Tailwind plugins, dev proxy to FastAPI
├── tsconfig.json
├── package.json
├── src/
│   ├── main.tsx            # Entry point
│   ├── App.tsx             # Root component
│   ├── index.css           # @import "tailwindcss"
│   ├── components/
│   │   ├── ChatContainer.tsx   # Main chat layout (message list + input)
│   │   ├── MessageBubble.tsx   # Single message (user or assistant)
│   │   ├── MarkdownRenderer.tsx # react-markdown wrapper with GFM + table styling
│   │   ├── ChatInput.tsx       # Text input + submit button
│   │   └── LoadingIndicator.tsx # Typing/streaming indicator
│   ├── hooks/
│   │   └── useChat.ts         # SSE connection, message state, conversation management
│   ├── services/
│   │   └── api.ts             # fetchEventSource wrapper, API types
│   └── types/
│       └── index.ts           # Message, ChatState, APIResponse types
```

### Pattern 1: SSE Streaming Endpoint (Backend)

**What:** Add a `/query/stream` POST endpoint that returns an SSE stream.
**When to use:** All frontend queries go through this endpoint.

```python
# Backend: FastAPI SSE streaming endpoint
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
import json

@app.post("/query/stream")
async def query_stream(request: QueryRequest):
    """Stream agent response via SSE."""
    conv_id = request.conversation_id or str(uuid4())
    config = {"configurable": {"thread_id": conv_id}}

    async def event_generator():
        # Send conversation_id immediately
        yield f"event: metadata\ndata: {json.dumps({'conversation_id': conv_id})}\n\n"

        # Use astream with stream_mode="updates" for node-level streaming
        async for chunk in _agent.astream(
            {"messages": [{"role": "user", "content": request.question}]},
            config=config,
            stream_mode="updates",
        ):
            # Extract content from the last message update
            for node_name, node_output in chunk.items():
                messages = node_output.get("messages", [])
                for msg in messages:
                    if hasattr(msg, "content") and msg.content:
                        content = msg.content
                        if isinstance(content, list):
                            parts = [b.get("text", "") if isinstance(b, dict) else str(b) for b in content]
                            content = "\n".join(parts)
                        yield f"event: token\ndata: {json.dumps({'content': content, 'node': node_name})}\n\n"

        # Run validator on the final state
        # (validator runs on complete response, not streamed)
        yield f"event: done\ndata: {json.dumps({'status': 'complete'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )
```

**Note on streaming granularity:** The supervisor graph may deliver complete agent messages rather than token-by-token chunks. This is acceptable for a v1 -- the user sees a progressive response as each agent node completes (supervisor routes, concierge clarifies, specialist answers). True token-by-token streaming from the LLM within a supervisor subgraph has known issues in langgraph-supervisor as of early 2026. If finer granularity is needed later, the options are: (a) use `astream_events(version="v2")` with `subgraphs=True` and filter for `on_chat_model_stream`, or (b) restructure the graph to avoid the supervisor wrapper.

### Pattern 2: SSE Consumer Hook (Frontend)

**What:** Custom React hook managing the SSE connection and message state.
**When to use:** The single hook powering the chat UI.

```typescript
// hooks/useChat.ts
import { fetchEventSource } from "@microsoft/fetch-event-source";
import { useState, useCallback, useRef } from "react";

interface Message {
  role: "user" | "assistant";
  content: string;
  isStreaming?: boolean;
}

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const conversationId = useRef<string | null>(null);
  const abortController = useRef<AbortController | null>(null);

  const sendMessage = useCallback(async (question: string) => {
    // Add user message immediately
    setMessages(prev => [...prev, { role: "user", content: question }]);
    setIsLoading(true);

    // Add empty assistant message for streaming
    setMessages(prev => [...prev, { role: "assistant", content: "", isStreaming: true }]);

    abortController.current = new AbortController();

    await fetchEventSource("/api/query/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        conversation_id: conversationId.current,
      }),
      signal: abortController.current.signal,

      onmessage(ev) {
        const data = JSON.parse(ev.data);

        if (ev.event === "metadata") {
          conversationId.current = data.conversation_id;
        } else if (ev.event === "token") {
          // Append content to the last (assistant) message
          setMessages(prev => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            updated[updated.length - 1] = {
              ...last,
              content: last.content + data.content,
            };
            return updated;
          });
        } else if (ev.event === "done") {
          setMessages(prev => {
            const updated = [...prev];
            updated[updated.length - 1] = {
              ...updated[updated.length - 1],
              isStreaming: false,
            };
            return updated;
          });
          setIsLoading(false);
        }
      },

      onerror(err) {
        setIsLoading(false);
        throw err; // Stops retrying
      },
    });
  }, []);

  return { messages, isLoading, sendMessage };
}
```

### Pattern 3: Markdown Renderer with Styled Tables

**What:** Wrapper component for react-markdown with GFM tables and Tailwind styling.
**When to use:** Every assistant message.

```tsx
// components/MarkdownRenderer.tsx
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface Props {
  content: string;
}

export function MarkdownRenderer({ content }: Props) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        table: ({ children }) => (
          <div className="overflow-x-auto my-2">
            <table className="min-w-full border-collapse text-sm">
              {children}
            </table>
          </div>
        ),
        th: ({ children }) => (
          <th className="border border-gray-300 bg-gray-100 px-3 py-1.5 text-left font-semibold">
            {children}
          </th>
        ),
        td: ({ children }) => (
          <td className="border border-gray-300 px-3 py-1.5">
            {children}
          </td>
        ),
        // Bold part numbers stand out
        strong: ({ children }) => (
          <strong className="font-bold text-gray-900">{children}</strong>
        ),
      }}
    />
  );
}
```

### Pattern 4: Vite Dev Proxy

**What:** Proxy `/api` requests to FastAPI during development to avoid CORS.
**When to use:** Development only. Production will use same-origin or explicit CORS.

```typescript
// vite.config.ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
```

### Anti-Patterns to Avoid
- **Putting business logic in components:** Keep API/state logic in hooks and services, not in component event handlers.
- **Direct DOM manipulation for scrolling:** Use `useRef` + `scrollIntoView`, not `document.getElementById`.
- **Global state for chat:** Chat state is simple enough for `useState` -- no need for Redux/Zustand for a single-page chat.
- **Polling instead of SSE:** The native browser EventSource API only supports GET. Use `@microsoft/fetch-event-source` for POST.
- **dangerouslySetInnerHTML for markdown:** Always use react-markdown, never raw HTML injection.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Markdown rendering | Custom regex parser | react-markdown + remark-gfm | Edge cases in markdown parsing are enormous; tables, nested lists, escaping |
| SSE client for POST | Custom fetch + text parsing | @microsoft/fetch-event-source | Handles reconnection, error events, proper SSE spec parsing |
| Table styling | Custom table component | react-markdown `components` prop | Override table/th/td elements directly in the markdown renderer |
| CSS utility system | Custom CSS framework | Tailwind CSS v4.1 | Professional appearance with zero custom CSS design needed |
| Auto-scroll in chat | Manual scroll calculations | useRef + scrollIntoView | Browser API handles edge cases (smooth scroll, viewport changes) |

**Key insight:** This is an internal tool for 2-3 staff members. Every hour spent on UI polish is an hour not spent on data accuracy. Use utility CSS (Tailwind), component libraries in markdown (react-markdown), and minimal custom components.

## Common Pitfalls

### Pitfall 1: Supervisor Graph Token Streaming
**What goes wrong:** Using `astream(stream_mode="messages")` with a supervisor graph returns complete messages instead of token chunks. The `create_supervisor` function wraps agents in compiled subgraphs, and `astream` with `subgraphs=False` (default) treats each subgraph as a single step.
**Why it happens:** LangGraph supervisor creates nested graph compilation that absorbs token-level events.
**How to avoid:** Use `stream_mode="updates"` for node-level streaming (each agent's complete output arrives as it finishes). This gives meaningful progressive display (user sees "thinking..." then the full answer). Accept this granularity for v1.
**Warning signs:** If response appears all at once with no streaming effect, check that the SSE endpoint is actually using `astream` and not `ainvoke`.

### Pitfall 2: CORS During Development
**What goes wrong:** Frontend on `localhost:5173` cannot reach FastAPI on `localhost:8000` due to CORS.
**Why it happens:** Browsers enforce same-origin policy.
**How to avoid:** Use Vite's `server.proxy` to forward `/api/*` requests to FastAPI. This avoids CORS entirely during development. Add CORS middleware to FastAPI only for production deployment (Phase 10).
**Warning signs:** `Access-Control-Allow-Origin` errors in browser console.

### Pitfall 3: SSE Connection Not Closing
**What goes wrong:** SSE connections remain open after component unmount or navigation, causing memory leaks and orphaned backend generators.
**Why it happens:** `fetchEventSource` keeps the connection open by default.
**How to avoid:** Pass an `AbortController.signal` and call `abort()` in the cleanup function of `useEffect` or when the component unmounts.
**Warning signs:** Multiple simultaneous connections visible in browser Network tab; backend logs showing concurrent generators.

### Pitfall 4: Markdown Rendering During Streaming
**What goes wrong:** Partial markdown renders incorrectly mid-stream (e.g., `| col1 | col2` without closing renders as raw text).
**Why it happens:** Markdown parser sees incomplete table syntax and treats it as plain text.
**How to avoid:** With node-level streaming (updates mode), each streamed chunk is a complete agent message, so this is less of an issue. If token-level streaming is added later, buffer the content and only re-render the markdown periodically, or accept that tables will "snap" into format when complete.
**Warning signs:** Flickering table rendering, raw pipe characters appearing then disappearing.

### Pitfall 5: Message State Mutation
**What goes wrong:** Appending to the last message's content mutates state directly.
**Why it happens:** Developer uses `messages[messages.length-1].content += chunk` instead of creating new array.
**How to avoid:** Always create new array and new message object when updating: `setMessages(prev => { const updated = [...prev]; updated[updated.length-1] = { ...last, content: last.content + chunk }; return updated; })`.
**Warning signs:** UI not updating despite receiving SSE events.

### Pitfall 6: Vite Proxy Only Works in Dev
**What goes wrong:** API calls fail after `npm run build` because Vite's proxy is dev-only.
**Why it happens:** Built static files have no proxy middleware.
**How to avoid:** In production (Phase 10), either serve the frontend from FastAPI's static files, or configure CORS on FastAPI, or use a reverse proxy (nginx). For now in Phase 9 (development only), the Vite proxy is sufficient.
**Warning signs:** API calls work in `npm run dev` but fail in `npm run build && npm run preview`.

## Code Examples

### Chat Container Layout
```tsx
// components/ChatContainer.tsx
import { useRef, useEffect } from "react";
import { useChat } from "../hooks/useChat";
import { MessageBubble } from "./MessageBubble";
import { ChatInput } from "./ChatInput";

export function ChatContainer() {
  const { messages, isLoading, sendMessage } = useChat();
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="flex flex-col h-screen max-w-4xl mx-auto">
      {/* Header */}
      <header className="border-b px-6 py-3 bg-white">
        <h1 className="text-lg font-semibold text-gray-800">Dex</h1>
        <p className="text-sm text-gray-500">Spa Parts Technical Assistant</p>
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
        {messages.map((msg, i) => (
          <MessageBubble key={i} message={msg} />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <ChatInput onSubmit={sendMessage} disabled={isLoading} />
    </div>
  );
}
```

### Message Bubble with Markdown
```tsx
// components/MessageBubble.tsx
import { MarkdownRenderer } from "./MarkdownRenderer";

interface Message {
  role: "user" | "assistant";
  content: string;
  isStreaming?: boolean;
}

export function MessageBubble({ message }: { message: Message }) {
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
        ) : (
          <MarkdownRenderer content={message.content} />
        )}
        {message.isStreaming && (
          <span className="inline-block w-2 h-4 bg-gray-400 animate-pulse ml-1" />
        )}
      </div>
    </div>
  );
}
```

### Chat Input Component
```tsx
// components/ChatInput.tsx
import { useState, FormEvent } from "react";

interface Props {
  onSubmit: (message: string) => void;
  disabled: boolean;
}

export function ChatInput({ onSubmit, disabled }: Props) {
  const [input, setInput] = useState("");

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || disabled) return;
    onSubmit(trimmed);
    setInput("");
  };

  return (
    <form onSubmit={handleSubmit} className="border-t px-6 py-3 bg-white">
      <div className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about spa specs, parts, or models..."
          disabled={disabled}
          className="flex-1 rounded-lg border border-gray-300 px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={disabled || !input.trim()}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Send
        </button>
      </div>
    </form>
  );
}
```

### FastAPI CORS Middleware (for production)
```python
# Add to backend/src/api/app.py when needed for production
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Create React App | Vite 6 | CRA deprecated 2023 | Vite is 40x faster HMR, first-class TS |
| Tailwind v3 (config file + PostCSS) | Tailwind v4.1 (Vite plugin, no config) | 2025 | `@import "tailwindcss"` is all that's needed |
| Native EventSource (GET only) | @microsoft/fetch-event-source | 2021+ | POST support, custom headers, reconnection logic |
| WebSockets for streaming | SSE for unidirectional server push | Ongoing | SSE is simpler for read-only streams; works over HTTP/2 |
| CSS Modules / Styled Components | Tailwind utility classes | 2023+ trend | Faster prototyping, no CSS-in-JS runtime cost |

**Deprecated/outdated:**
- Create React App (CRA): Officially deprecated, replaced by Vite/Next.js
- Tailwind v3 config files: v4 eliminates `tailwind.config.js` for most setups
- `componentDidMount` / class components: Use hooks (`useEffect`, `useRef`)

## Open Questions

Things that could not be fully resolved:

1. **Token-level streaming with supervisor graph**
   - What we know: `astream(stream_mode="updates")` works for node-level streaming. `astream(stream_mode="messages")` has known issues with supervisor subgraphs not emitting `AIMessageChunk` tokens.
   - What's unclear: Whether `astream_events(version="v2", subgraphs=True)` filtering for `on_chat_model_stream` works reliably with the specific `langgraph-supervisor` + `create_react_agent` combination used in this project.
   - Recommendation: Start with node-level streaming (`updates` mode). The specialist agent's full response arrives as one chunk, giving a "typing complete" feel rather than character-by-character. This is acceptable for v1. Upgrade to token streaming later if needed.

2. **Gemini streaming support via LangChain**
   - What we know: The project uses `ChatGoogleGenerativeAI` with `gemini-2.5-flash`. LangChain's Gemini adapter supports streaming.
   - What's unclear: Whether the adapter properly emits `AIMessageChunk` events through the supervisor graph for the `messages` stream mode.
   - Recommendation: Test during implementation. Fall back to `updates` mode if token streaming does not work.

3. **Validation warnings in streaming response**
   - What we know: The validator runs post-hoc on the complete agent result. In a streaming endpoint, the validator cannot run until all tokens are received.
   - What's unclear: Best UX for showing validation warnings (after stream completes? separate event?).
   - Recommendation: Send a `validation` SSE event after the `done` event with any warnings. Frontend can display them as a subtle banner below the response.

## Sources

### Primary (HIGH confidence)
- [Tailwind CSS v4.1 official docs](https://tailwindcss.com/docs) - Installation steps for Vite verified
- [Vite official getting started](https://vite.dev/guide/) - `npm create vite@latest` with `react-ts` template
- [FastAPI CORS docs](https://fastapi.tiangolo.com/tutorial/cors/) - CORSMiddleware configuration
- [react-markdown GitHub](https://github.com/remarkjs/react-markdown) - remark-gfm plugin usage
- [remark-gfm npm](https://www.npmjs.com/package/remark-gfm) - v4.x for GFM table support
- [@microsoft/fetch-event-source GitHub](https://github.com/Azure/fetch-event-source) - POST-based SSE client

### Secondary (MEDIUM confidence)
- [Softgrade SSE + FastAPI + React + LangGraph](https://www.softgrade.org/sse-with-fastapi-react-langgraph/) - End-to-end SSE pattern with code examples
- [LangChain Forum: Streaming from langgraph-supervisor](https://forum.langchain.com/t/streaming-from-langgraph-supervisor/1789) - Supervisor streaming issues and workarounds
- [LangGraph streaming concepts](https://docs.langchain.com/oss/python/langgraph/streaming) - Stream modes: values, updates, messages, custom, debug
- [langgraph-supervisor issue #226](https://github.com/langchain-ai/langgraph-supervisor-py/issues/226) - Known bug with `stream_mode="messages"` and supervisor subgraphs

### Tertiary (LOW confidence)
- Various Medium articles on chat UI patterns - General patterns, not verified against current library versions
- WebSearch results on auto-scroll patterns - Common React pattern, well-established

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries verified via official docs, versions confirmed
- Architecture: HIGH - SSE + react-markdown pattern is well-established, code examples from multiple verified sources
- Streaming approach: MEDIUM - Node-level streaming is proven; token-level with supervisor has known issues. Recommended approach (updates mode) is the safe path
- Pitfalls: HIGH - CORS, SSE lifecycle, markdown mid-stream issues are well-documented problems with known solutions

**Research date:** 2026-02-16
**Valid until:** 2026-03-16 (stable ecosystem; Tailwind v4 and React 19 are established)
