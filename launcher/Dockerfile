# ── Stage 1: Build React ───────────────────────────────────────────────────────
FROM node:20-slim AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# ── Stage 2: nginx serve ───────────────────────────────────────────────────────
FROM nginx:alpine
LABEL org.opencontainers.image.source=https://github.com/man4ish/omnibioai
COPY --from=builder /app/build /usr/share/nginx/html
EXPOSE 5190
CMD ["nginx", "-g", "daemon off;"]
