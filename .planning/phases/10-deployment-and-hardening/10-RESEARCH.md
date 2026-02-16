# Phase 10: Deployment and Hardening - Research

**Researched:** 2026-02-16
**Domain:** Cloud deployment of FastAPI + React SPA + LangGraph multi-agent system with MCP subprocess
**Confidence:** HIGH

## Summary

This research covers deploying the Dex system -- a FastAPI backend with LangGraph multi-agent orchestration, MCP data server (subprocess/stdio), and a React+Vite frontend -- to a hosted environment accessible by two users (Adam and Stephen) for demo/testing sessions.

The most critical architectural finding is that the MCP server currently uses **stdio transport** (subprocess spawned via `sys.executable -m backend.src.mcp`), which was designed for local/desktop use. For cloud deployment, this works fine with a single Uvicorn worker but must NOT use multiple workers (each worker would spawn its own MCP subprocess, and the `langchain-mcp-adapters` `MultiServerMCPClient` manages the subprocess lifecycle per session). Since the POC only needs 2-3 concurrent users, a single Uvicorn worker with async concurrency is sufficient -- FastAPI's async nature handles concurrent SSE streams without multiple workers.

The recommended deployment architecture is a **single Docker container** running on **Railway.app** that serves both the FastAPI API and the React static files. This eliminates CORS complexity, simplifies deployment, and keeps costs minimal (~$5-7/month). The React frontend build output (`frontend/dist/`) is copied into the container and served by FastAPI's `StaticFiles` mount with a catch-all route for SPA routing.

**Primary recommendation:** Deploy as a single Docker container on Railway.app ($5/month Hobby plan). FastAPI serves both the API endpoints and the React static build. Single Uvicorn worker with async concurrency handles 2-3 concurrent users. The MCP subprocess stdio transport works as-is in the container.

## Standard Stack

The established tools for this deployment:

### Core
| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| Docker | latest | Containerization | Industry standard for reproducible deployments |
| Railway.app | N/A | Cloud hosting (PaaS) | Simplest Git-deploy PaaS, $5/mo hobby tier, Docker support, env var management |
| uvicorn | >=0.34 | ASGI server | Already in dependencies, production-ready for single-worker async |
| uv | >=0.10 | Python package manager | Already used by project, excellent Docker integration with official images |

### Supporting
| Tool | Purpose | When to Use |
|------|---------|-------------|
| FastAPI StaticFiles | Serve React build from backend | Production: eliminates need for separate frontend hosting |
| python-multipart | Required by FastAPI for form data | If needed for future file upload features |
| Docker multi-stage build | Minimize image size | Always -- separate build (Node + Python) from runtime |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Railway | Render.com | Render Starter is $7/mo, slightly more complex. Either works for POC. |
| Railway | Fly.io | More control over regions, more complex CLI setup. Overkill for 2-user POC. |
| Single container | Separate frontend/backend services | Adds CORS config, two services to manage, higher cost. Unnecessary for POC. |
| stdio MCP transport | HTTP MCP transport | HTTP transport is more production-ready but requires code changes to both config.py and server startup. Not needed for 2-3 users with single worker. |

## Architecture Patterns

### Recommended Deployment Architecture
```
Single Docker Container (Railway.app)
|
+-- uvicorn (single worker, async)
|   |
|   +-- FastAPI app
|       |
|       +-- POST /query         (agent query)
|       +-- POST /query/stream  (SSE streaming)
|       +-- GET  /health        (health check)
|       +-- GET  /assets/*      (Vite static assets)
|       +-- GET  /*             (SPA catch-all -> index.html)
|       |
|       +-- [lifespan] MCP subprocess (stdio)
|           |
|           +-- python -m backend.src.mcp
|               |
|               +-- 19 JSON files loaded in-memory
|
+-- Environment Variables:
    +-- GEMINI_API_KEY (secret)
    +-- PORT (Railway-provided)
```

### Pattern 1: Single Container Full-Stack
**What:** FastAPI serves both API routes and the React SPA static files from a single process.
**When to use:** POC/demo deployments with low concurrency (2-10 users).
**Why:** Eliminates CORS issues, simplifies deployment, single URL for everything.

```python
# In app.py -- mount static files AFTER API routes
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

STATIC_DIR = Path(__file__).parent.parent.parent.parent / "frontend" / "dist"

# Serve Vite asset files (JS, CSS, images)
app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

# SPA catch-all: any non-API route serves index.html
@app.get("/{path:path}")
async def serve_spa(path: str):
    file_path = STATIC_DIR / path
    if file_path.is_file():
        return FileResponse(file_path)
    return FileResponse(STATIC_DIR / "index.html")
```

### Pattern 2: Docker Multi-Stage Build (Node + Python)
**What:** Stage 1 builds the React frontend, Stage 2 installs Python deps, final stage is runtime-only.
**When to use:** Always for containerized deployment.

```dockerfile
# Stage 1: Build React frontend
FROM node:22-alpine AS frontend-builder
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Install Python dependencies
FROM python:3.12-slim AS backend-builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY backend/pyproject.toml backend/uv.lock ./backend/
RUN --mount=type=cache,target=/root/.cache/uv \
    cd backend && uv sync --locked --no-install-project --no-dev

# Copy source and install project
COPY backend/ ./backend/
RUN --mount=type=cache,target=/root/.cache/uv \
    cd backend && uv sync --locked --no-dev

# Stage 3: Runtime
FROM python:3.12-slim
WORKDIR /app
COPY --from=backend-builder /app/backend/.venv /app/backend/.venv
COPY --from=backend-builder /app/backend/src /app/backend/src
COPY --from=frontend-builder /frontend/dist /app/frontend/dist

ENV PATH="/app/backend/.venv/bin:$PATH"
ENV PYTHONPATH="/app"

EXPOSE 8000
CMD ["uvicorn", "backend.src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Pattern 3: Environment-Aware Configuration
**What:** Use environment variables to switch between dev and production behavior.
**When to use:** When the same codebase runs locally and in cloud.

```python
import os

# In app.py CORS configuration
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

if ENVIRONMENT == "production":
    # In production, frontend is served from same origin -- no CORS needed
    # But keep permissive CORS for potential API-only access
    origins = [os.getenv("ALLOWED_ORIGIN", "*")]
else:
    origins = ["http://localhost:5173", "http://localhost:4173"]
```

### Anti-Patterns to Avoid
- **Multiple Uvicorn workers with MCP stdio subprocess:** Each worker spawns its own subprocess. The current architecture uses module-level `_agent` and `_mcp_client` globals set in lifespan. Multiple workers = multiple MCP subprocesses = wasted resources and potential issues. For 2-3 users, a single async worker is sufficient.
- **Gunicorn wrapping Uvicorn on Railway:** Railway containers already handle process management. Adding Gunicorn adds complexity without benefit at this scale. Use bare `uvicorn` with single worker.
- **Hardcoding localhost URLs in frontend:** The frontend already correctly uses relative `/api` paths. For production, these must be rewritten to direct API paths (no Vite proxy).
- **Exposing stack traces in error responses:** Default FastAPI error responses include implementation details. Add global exception handlers for production.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Static file serving | Custom file-reading middleware | `fastapi.staticfiles.StaticFiles` | Handles MIME types, caching headers, directory traversal protection |
| SPA catch-all routing | Complex regex matching | `FileResponse` with path fallback to `index.html` | Well-tested pattern, handles all edge cases |
| Docker image builds | Manual pip install in Dockerfile | `uv sync` with multi-stage build | 10x faster installs, deterministic lockfile, proper layer caching |
| Environment variables in cloud | `.env` files copied to container | Railway's built-in variable management | Sealed variables, not in image, rotatable without redeploy |
| Health checks | Custom monitoring scripts | FastAPI `/health` endpoint + Railway health checks | Already exists (`GET /health`), Railway supports HTTP health checks natively |
| Process management in container | supervisord/systemd | Single `uvicorn` process as PID 1 | Container orchestrator handles restarts. Single process = simple lifecycle. |
| HTTPS/TLS | certbot/Let's Encrypt | Railway's automatic HTTPS | Free TLS on all Railway domains, zero configuration |

**Key insight:** The entire deployment should add minimal new code. The bulk of the work is configuration (Dockerfile, railway config, environment variables) and small modifications to the existing FastAPI app (static file serving, CORS update, error handlers).

## Common Pitfalls

### Pitfall 1: Frontend API URL Mismatch
**What goes wrong:** Frontend makes requests to `/api/query/stream` but FastAPI routes are `/query/stream` (without `/api` prefix). In dev, Vite proxy rewrites `/api` to `""`. In production without Vite proxy, requests 404.
**Why it happens:** Vite's dev proxy masks the URL difference between frontend paths and backend routes.
**How to avoid:** Two options: (a) Change the frontend `API_BASE` to `""` for production builds via Vite env variable `VITE_API_BASE`, or (b) add an `/api` prefix to FastAPI routes. Option (a) is simpler.
**Warning signs:** Frontend loads but all queries fail with 404 or network errors.

### Pitfall 2: MCP Subprocess Path Resolution
**What goes wrong:** The MCP client config uses `sys.executable` and `_PROJECT_ROOT` to spawn the subprocess. In Docker, these paths differ from local development.
**Why it happens:** `Path(__file__).resolve().parents[3]` computes differently in the container vs. local. `sys.executable` in the venv may not be the expected path.
**How to avoid:** Set `PYTHONPATH=/app` in Docker and ensure `sys.executable` resolves to the venv Python. Verify MCP subprocess can start in the container during build verification.
**Warning signs:** App starts but queries fail with "Agent not initialized" or MCP connection errors.

### Pitfall 3: Railway PORT Variable
**What goes wrong:** Uvicorn starts on port 8000 but Railway expects the app to listen on `$PORT` (dynamically assigned).
**Why it happens:** Railway provides a `PORT` environment variable and routes traffic to it.
**How to avoid:** Use `--port ${PORT:-8000}` in the CMD or read from env in the startup command.
**Warning signs:** Deployment succeeds but health checks fail and app is unreachable.

### Pitfall 4: SSE Buffering
**What goes wrong:** SSE streaming appears to hang -- tokens arrive all at once instead of progressively.
**Why it happens:** Reverse proxies or intermediate layers buffer the SSE response.
**How to avoid:** The app already sends `X-Accel-Buffering: no` and `Cache-Control: no-cache` headers. Verify Railway doesn't add additional buffering. Railway's HTTP proxy generally passes through SSE correctly.
**Warning signs:** Streaming endpoint returns entire response after long delay instead of progressive tokens.

### Pitfall 5: InMemorySaver State Loss
**What goes wrong:** Conversation context is lost between requests because the container restarts.
**Why it happens:** `InMemorySaver` stores checkpoints in process memory. Container restarts (deploys, scale events) clear all state.
**How to avoid:** This is acceptable for POC. Document that conversation history is ephemeral. Users must re-state context after a redeploy. For v2, consider persistent checkpointer.
**Warning signs:** Users report "Dex forgot what we were talking about" after a deployment or container restart.

### Pitfall 6: Gemini API Rate Limits
**What goes wrong:** With 2-3 concurrent users, Gemini API may rate-limit requests.
**Why it happens:** Multi-agent graph makes multiple LLM calls per query (supervisor + concierge/specialist). Two concurrent queries = 6-10 API calls simultaneously.
**How to avoid:** Gemini Flash has generous rate limits (1000+ RPM for paid tier). Ensure the GEMINI_API_KEY is on a paid plan, not the free tier. Add graceful error handling for 429 responses.
**Warning signs:** Intermittent errors during concurrent demo sessions.

### Pitfall 7: Large Docker Image
**What goes wrong:** Docker image is >2GB, slow to deploy.
**Why it happens:** Including build tools (Node.js, uv, dev dependencies) in the final image.
**How to avoid:** Multi-stage build: Node in stage 1 (build React), Python/uv in stage 2 (install deps), minimal `python:3.12-slim` in final stage with only runtime artifacts.
**Warning signs:** Deploys take 5+ minutes on Railway.

## Code Examples

### Example 1: Frontend API Base URL Configuration
```typescript
// frontend/src/services/api.ts
// Use Vite env variable for flexibility
export const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";
```

```
# frontend/.env.production
VITE_API_BASE=
```

This makes the frontend call `/query/stream` directly in production (same origin) while keeping `/api/query/stream` in development (proxied by Vite).

### Example 2: FastAPI Static File Serving + SPA Catch-All
```python
# In app.py, AFTER all API route definitions
import os
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "dist"

if FRONTEND_DIR.exists():
    # Serve Vite-built assets (JS, CSS, etc.)
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="static-assets")

    @app.get("/{path:path}")
    async def serve_frontend(path: str):
        """Serve React SPA -- any non-API path falls through to index.html."""
        file_path = FRONTEND_DIR / path
        if file_path.is_file() and ".." not in path:
            return FileResponse(file_path)
        return FileResponse(FRONTEND_DIR / "index.html")
```

### Example 3: Global Exception Handler
```python
# In app.py
import logging
from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch unhandled exceptions -- return friendly message, log details."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An internal error occurred. Please try again.",
            "type": type(exc).__name__,
        },
    )
```

### Example 4: Railway Startup Command
```dockerfile
# Use shell form to expand $PORT
CMD uvicorn backend.src.api.app:app --host 0.0.0.0 --port ${PORT:-8000}
```

### Example 5: Dockerfile (.dockerignore)
```
# .dockerignore
.git
.planning
.pytest_cache
__pycache__
*.pyc
backend/.venv
backend/.pytest_cache
backend/src/etl/pdf_store
frontend/node_modules
frontend/.vite
*.md
nul
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Gunicorn + Uvicorn workers | Single Uvicorn worker for async apps | 2024+ | For small-scale async apps, single worker with asyncio handles concurrency fine |
| pip install in Docker | uv sync in Docker | 2024-2025 | 10-50x faster dependency installation, better layer caching |
| Separate frontend/backend hosting | Single container serving both | Ongoing | Simpler for POC/internal tools, fewer moving parts |
| MCP stdio transport only | MCP HTTP/streamable transport available | FastMCP v2 (2025) | HTTP transport better for production multi-worker, but stdio fine for single-worker POC |
| Railway Nixpacks (auto-detect) | Railway Dockerfile (explicit) | Ongoing | Dockerfile gives full control over multi-stage builds with Node + Python |

**Deprecated/outdated:**
- Railway's permanent free tier no longer exists (now 30-day trial only, then $5/mo Hobby)
- Render's free tier spins down after 15 minutes of inactivity (not suitable for demo sessions)
- Gunicorn is unnecessary when running single-worker Uvicorn in a container managed by an orchestrator

## Open Questions

1. **Railway vs Render vs Fly.io -- final platform choice**
   - What we know: All three support Docker, env vars, and custom domains. Railway is simplest ($5/mo), Render Starter is $7/mo, Fly.io is usage-based.
   - What's unclear: Whether the user has a preference or existing account on any platform.
   - Recommendation: Default to Railway ($5/mo Hobby plan). Switch to Render if Railway's $5 included credit is insufficient for the demo workload. Both are viable.

2. **Custom domain or platform subdomain?**
   - What we know: Railway provides `*.up.railway.app` domains with automatic HTTPS. Custom domains require DNS configuration.
   - What's unclear: Whether Adam/Stephen need a branded URL like `dex.spaparts.com` or if a Railway subdomain is fine for POC testing.
   - Recommendation: Use Railway's provided subdomain for POC. Custom domain is a v2 concern.

3. **Gemini API key billing tier**
   - What we know: The GEMINI_API_KEY must be on a plan with sufficient rate limits for concurrent multi-agent queries.
   - What's unclear: Whether the current key is on free tier or paid tier. Free tier has restrictive RPM limits that could fail during concurrent demo sessions.
   - Recommendation: Verify the Gemini API key is on a paid tier before demo sessions. If free tier, budget for Gemini API costs.

4. **Test matrix execution in deployed environment**
   - What we know: 332+ tests exist locally. Success criteria requires the 190-data-point test matrix to pass in deployed environment.
   - What's unclear: How to run integration tests against the deployed URL (not localhost). Whether the test suite needs modification for remote execution.
   - Recommendation: Create a small smoke test script that hits the deployed `/health` and `/query` endpoints. Full integration test matrix can be run with `BACKEND_URL` environment variable pointing to the Railway deployment.

## Sources

### Primary (HIGH confidence)
- FastAPI official docs: Static Files, Error Handling, Deployment, Server Workers
- uv Docker guide: https://docs.astral.sh/uv/guides/integration/docker/
- FastMCP deployment docs: https://gofastmcp.com/deployment/running-server
- Railway FastAPI guide: https://docs.railway.com/guides/fastapi
- Railway pricing: https://docs.railway.com/reference/pricing/plans

### Secondary (MEDIUM confidence)
- langchain-mcp-adapters MultiServerMCPClient: https://deepwiki.com/langchain-ai/langchain-mcp-adapters/2.1-multiservermcpclient (confirmed HTTP transport support)
- Render pricing: https://render.com/pricing (confirmed Starter at $7/mo)
- Fly.io FastAPI guide: https://fly.io/docs/python/frameworks/fastapi/ (confirmed Docker-based deploy)
- FastAPI + React SPA catch-all: https://gist.github.com/ultrafunkamsterdam/b1655b3f04893447c3802453e05ecb5e

### Tertiary (LOW confidence)
- Railway SSE streaming behavior -- no explicit documentation found; assumed to pass through SSE correctly based on Railway being an HTTP proxy
- Concurrent MCP stdio subprocess behavior under async FastAPI -- tested locally but not verified in container context

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All tools verified via official docs, existing project already uses uvicorn/FastAPI/uv
- Architecture: HIGH - Single-container pattern well-documented, verified via multiple sources
- Pitfalls: HIGH - MCP subprocess, PORT variable, API URL mismatch are well-understood issues with clear solutions
- Concurrency model: MEDIUM - Single uvicorn worker with async should handle 2-3 users, but not load-tested in container

**Research date:** 2026-02-16
**Valid until:** 2026-03-16 (stable -- deployment patterns change slowly)
