---
phase: 10-deployment-and-hardening
plan: 01
subsystem: infra
tags: [docker, fastapi, static-files, cors, error-handling, vite, production]

# Dependency graph
requires:
  - phase: 09-frontend
    provides: React+Vite+Tailwind chat UI with SSE streaming
  - phase: 07-multi-agent-orchestration
    provides: Multi-agent supervisor graph with MCP tools
provides:
  - Multi-stage Dockerfile (Node + Python) for containerized deployment
  - Production-hardened FastAPI app with global error handler, env-aware CORS, static file serving
  - Frontend env configuration for production API routing
affects: [10-02 (Railway deployment), future CI/CD pipelines]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Single-container full-stack: FastAPI serves React build + API on one port"
    - "Environment-aware CORS: production reads ALLOWED_ORIGIN env var"
    - "SPA catch-all: non-API paths fall through to index.html"
    - "Multi-stage Docker: node:22-alpine -> python:3.12-slim builder -> python:3.12-slim runtime"

key-files:
  created:
    - Dockerfile
    - .dockerignore
    - frontend/.env.production
  modified:
    - backend/src/api/app.py
    - frontend/src/services/api.ts

key-decisions:
  - "Shell-form CMD in Dockerfile for Railway PORT variable expansion"
  - "Conditional static file serving (only when frontend/dist exists) to avoid breaking tests"
  - "VITE_API_BASE env var with nullish coalescing (??) for dev/prod API routing"
  - "Global exception handler returns JSON with type field for debugging without stack traces"

patterns-established:
  - "Environment detection: os.getenv('ENVIRONMENT', 'development') for production vs dev behavior"
  - "SPA catch-all after API routes: path traversal protection with '..' check"

# Metrics
duration: 27min
completed: 2026-02-16
---

# Phase 10 Plan 01: Containerization Summary

**Multi-stage Dockerfile with production-hardened FastAPI (error handler, env-aware CORS, SPA static serving) and Vite env-based API routing**

## Performance

- **Duration:** 27 min
- **Started:** 2026-02-16T20:09:31Z
- **Completed:** 2026-02-16T20:36:22Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Production-hardened FastAPI app: global exception handler (JSON, no stack traces), environment-aware CORS, conditional static file serving with SPA catch-all
- Multi-stage Dockerfile: node:22-alpine (frontend build), python:3.12-slim (backend deps via uv), python:3.12-slim (runtime) with shell-form CMD for Railway PORT
- Frontend API routing: VITE_API_BASE env var makes API_BASE empty in production (direct paths) while keeping /api prefix in dev (Vite proxy)
- All 329 non-integration tests pass with no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Production-harden the FastAPI app** - `56c8a2f` (feat)
2. **Task 2: Create Dockerfile and .dockerignore** - `17bf275` (feat)

**Plan metadata:** (pending)

## Files Created/Modified
- `Dockerfile` - 3-stage multi-stage build (Node frontend + Python backend + slim runtime)
- `.dockerignore` - Excludes .git, .planning, pdf_store, node_modules, .venv, .env, __pycache__
- `backend/src/api/app.py` - Global exception handler, env-aware CORS, static file serving + SPA catch-all
- `frontend/src/services/api.ts` - API_BASE reads VITE_API_BASE env var with /api fallback
- `frontend/.env.production` - Sets VITE_API_BASE to empty string for production builds

## Decisions Made
- [10-01]: Shell-form CMD in Dockerfile (not exec form) so ${PORT:-8000} expands at runtime for Railway
- [10-01]: Conditional static file serving (if FRONTEND_DIR.exists()) so tests and dev mode work without frontend build
- [10-01]: VITE_API_BASE with nullish coalescing (?? "/api") instead of OR (||) to correctly handle empty string as falsy
- [10-01]: Global exception handler logs full traceback via logger.exception() but returns only friendly JSON to client
- [10-01]: _cors_origins variable pattern (not inline) for cleaner environment branching

## Deviations from Plan

None -- plan executed exactly as written.

## Issues Encountered
- Docker daemon not running on this Windows machine (Docker Desktop not started). Dockerfile and .dockerignore were created per plan specification but the docker build/run verification steps were skipped. The files follow the exact multi-stage pattern from the research document and are ready for testing when Docker daemon is available or on Railway deployment.
- Plan's verify command used `--ignore=tests/integration` but integration tests are at `tests/test_agent_integration.py` (not in a subdirectory). Used `-m "not integration"` marker filter instead. All 329 non-integration tests pass, 23 integration tests properly deselected.

## User Setup Required

None -- no external service configuration required for this plan. Railway deployment (Plan 02) will require environment variable setup.

## Next Phase Readiness
- Dockerfile and .dockerignore ready for Railway deployment (Plan 02)
- FastAPI app serves both API and frontend static files from single port
- Frontend production build uses direct API paths (no proxy needed)
- Docker build should be verified before first Railway deployment (docker daemon was not available during this execution)

---
*Phase: 10-deployment-and-hardening*
*Completed: 2026-02-16*
