# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Error Encyclopedia — frontend (Next.js 14) image
# Multi-stage build producing a minimal "standalone" server (no full
# node_modules in the final image — only the traced runtime dependencies).
# ---------------------------------------------------------------------------

# ---- 1. Install dependencies ----
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# ---- 2. Build the standalone bundle ----
FROM node:20-alpine AS builder
WORKDIR /app

# NEXT_PUBLIC_* values are inlined into the client bundle at *build* time, so
# the browser-facing API URL must be present here — not just at runtime.
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
ENV NEXT_TELEMETRY_DISABLED=1

COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# ---- 3. Minimal runtime image ----
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# `output: "standalone"` (see next.config.mjs) emits a self-contained server at
# .next/standalone, with public/ and .next/static copied alongside it.
COPY --from=builder /app/public ./public
COPY --from=builder --chown=node:node /app/.next/standalone ./
COPY --from=builder --chown=node:node /app/.next/static ./.next/static

# Run as the unprivileged "node" user that ships with the base image.
USER node

EXPOSE 3000

CMD ["node", "server.js"]
