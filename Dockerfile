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
ENV PYTHONUNBUFFERED=1

# Install Playwright Chromium for JS-rendered sites (Bullfrog)
RUN playwright install --with-deps chromium

EXPOSE 8000
# Shell form so ${PORT:-8000} expands at runtime (Railway sets PORT dynamically)
CMD uvicorn backend.src.api.app:app --host 0.0.0.0 --port ${PORT:-8000}
