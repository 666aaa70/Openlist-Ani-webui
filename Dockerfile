# syntax=docker/dockerfile:1.7

# ── Stage 1: Build Vue 3 + TypeScript + Tailwind CSS frontend ─────────
FROM node:22-alpine AS frontend-builder

WORKDIR /src/frontend

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


# ── Stage 2: Minimal Python 3.12 runtime (AMD64 & ARM64 compatible) ───
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    WEBUI_STATIC_DIR=/app/static \
    WEBUI_DATA_DIR=/data \
    WEBUI_HOST=0.0.0.0 \
    WEBUI_PORT=8080

RUN groupadd --gid 1000 webui \
    && useradd --uid 1000 --gid 1000 --create-home --shell /usr/sbin/nologin webui

WORKDIR /app

COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY backend/app /app/app
COPY --from=frontend-builder /src/frontend/dist /app/static

RUN mkdir -p /data && chown -R webui:webui /app /data

USER webui

VOLUME ["/data"]
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os, urllib.request; port=os.environ.get('WEBUI_PORT','8080'); urllib.request.urlopen(f'http://127.0.0.1:{port}/api/v1/health/live', timeout=3)"

CMD ["sh", "-c", "exec uvicorn app.main:get_asgi_app --factory --host \"${WEBUI_HOST:-0.0.0.0}\" --port \"${WEBUI_PORT:-8080}\" --log-level \"${WEBUI_LOG_LEVEL:-info}\""]
