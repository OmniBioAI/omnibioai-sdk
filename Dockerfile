# ── Stage 1: Build React launcher ─────────────────────────────────────────────
FROM --platform=$BUILDPLATFORM node:20-bookworm-slim AS launcher-builder
WORKDIR /app
COPY launcher/package*.json ./
RUN npm ci
COPY launcher/ .
RUN PUBLIC_URL=/_svc/sdk REACT_APP_OMNIBIOAI_BASE_URL=/_svc/workbench npm run build

# ── Stage 2: Python SDK + nginx ───────────────────────────────────────────────
FROM python:3.12-slim-bookworm

LABEL org.opencontainers.image.source=https://github.com/man4ish/omnibioai
LABEL org.opencontainers.image.description="OmniBioAI SDK + Launcher UI"

RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install only runtime dep
RUN pip install --no-cache-dir "requests>=2.31.0"

# Copy SDK source directly
COPY omnibioai_sdk/ ./omnibioai_sdk/

# Copy React launcher build
COPY --from=launcher-builder /app/build /usr/share/nginx/html

# nginx config
RUN rm -f /etc/nginx/sites-enabled/default /etc/nginx/sites-available/default && \
    printf 'server {\n    listen 5190;\n    root /usr/share/nginx/html;\n    index index.html;\n    location / { try_files $uri $uri/ /index.html; }\n}\n' \
    > /etc/nginx/conf.d/sdk.conf

ENV OMNIBIOAI_BASE_URL=http://localhost:8000
ENV PYTHONPATH=/app

EXPOSE 5190
CMD ["nginx", "-g", "daemon off;"]
