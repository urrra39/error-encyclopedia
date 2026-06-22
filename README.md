# 🧭 Error Encyclopedia

[![CI](https://github.com/urrra39/error-encyclopedia/actions/workflows/ci.yml/badge.svg)](https://github.com/urrra39/error-encyclopedia/actions/workflows/ci.yml)

> A high-performance, structured search engine for software errors. Every entry
> pairs a **plain-English explanation**, the **common root causes**, and
> **verified before/after fixes** — so you can stop scrolling stale forum threads
> and just fix the thing.

Search any error message or code, understand what it actually means, and apply a
trusted fix. Built as a production-shaped, full-stack reference application: a
typed **FastAPI** backend, a **PostgreSQL** system of record, a **Meilisearch**
full-text engine, and a server-rendered **Next.js 14** frontend — all wired
together with a single **Docker Compose** command.

<p align="center">
  <img alt="Next.js 14" src="https://img.shields.io/badge/Next.js-14_App_Router-000000?logo=nextdotjs&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-async-009688?logo=fastapi&logoColor=white">
  <img alt="PostgreSQL" src="https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white">
  <img alt="Meilisearch" src="https://img.shields.io/badge/Meilisearch-1.10-FF5CAA?logo=meilisearch&logoColor=white">
  <img alt="Docker" src="https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white">
</p>

---

## Table of contents

- [Tech stack](#tech-stack)
- [System architecture](#system-architecture)
- [Production-readiness features](#production-readiness-features)
- [Quickstart (Docker Compose)](#quickstart-docker-compose)
- [Seeding sample data](#seeding-sample-data)
- [API reference](#api-reference)
- [Configuration](#configuration)
- [Local development (without Docker)](#local-development-without-docker)
- [Project layout](#project-layout)
- [License](#license)

---

## Tech stack

| Layer        | Technology                            | Role in the system                                                                 |
| ------------ | ------------------------------------- | ---------------------------------------------------------------------------------- |
| **Frontend** | **Next.js 14 (App Router)**           | Server-rendered React, dynamic SEO routes, typed API client, Tailwind CSS UI.      |
| **Backend**  | **FastAPI** (Uvicorn, Pydantic v2)    | Async REST API, request/response validation, dependency health checks.             |
| **Database** | **PostgreSQL** (SQLAlchemy 2.0 async) | System of record for errors, root causes, and verified fixes (asyncpg driver).     |
| **Search**   | **Meilisearch**                       | Typo-tolerant, sub-millisecond full-text index derived from PostgreSQL.            |
| **Infra**    | **Docker Compose**                    | One-command orchestration with multi-stage builds and health-gated startup order.  |

---

## System architecture

The application is built around a **dual-fetch pattern**: reads are routed to the
store best suited for them. **Search queries hit Meilisearch** for instant,
typo-tolerant results; **detail reads hit PostgreSQL** for the complete,
relational source of truth (an error plus its root causes, verified fixes, and
related errors).

```
                          ┌────────────────────────────┐
   Browser ──────────────▶│   frontend (Next.js 14)     │
   http://localhost:3000  │   standalone Node server     │
                          └─────────────┬────────────────┘
       client-side search box           │   server-side render (RSC)
       http://localhost:8000            │   http://backend:8000
                          ┌─────────────▼────────────────┐
                          │     backend (FastAPI)         │
                          │     async REST API            │
                          └──────┬─────────────────┬──────┘
                                 │                 │
              ① SEARCH path      │                 │   ② DETAIL path
              GET /api/search    │                 │   GET /api/errors/{slug}
                   ┌─────────────▼──┐        ┌─────▼──────────────────┐
                   │  Meilisearch   │        │   PostgreSQL 16        │
                   │  derived index │◀──sync─│   system of record     │
                   │  (fast search) │        │   (relational truth)   │
                   └────────────────┘        └────────────────────────┘
```

**The dual-fetch pattern in practice**

- **① Search → Meilisearch.** The debounced, keyboard-navigable search box calls
  `GET /api/search`. Meilisearch returns ranked, typo-tolerant matches in
  sub-millisecond query time — ideal for live typeahead, not for joins.
- **② Detail → PostgreSQL.** Opening `/error/[slug]` calls `GET /api/errors/{slug}`,
  which reads the canonical record and all of its relations straight from Postgres
  with eager-loaded (`selectin`) joins.

**Two API URLs, one backend.** The Next.js frontend reaches the backend from two
places, by design:

- The **browser** (the client-side search box) calls the host-mapped
  `http://localhost:8000`, baked into the client bundle at build time via
  `NEXT_PUBLIC_API_BASE_URL`.
- The **server** (React Server Components rendering `/error/[slug]`) calls the
  backend over the private Docker network at `http://backend:8000`, via the
  runtime-only `API_BASE_URL_INTERNAL`.

**Source of truth vs. derived index.** PostgreSQL owns the data; Meilisearch is a
derived projection of it. On startup the backend creates the schema and ensures
the search index exists; writes go to Postgres first and are then synced into the
index, so the two never diverge silently.

---

## Production-readiness features

This is a portfolio project built to production standards — the details that
separate a demo from something you'd actually ship.

### ⚡ Sub-millisecond search

Search is served by **Meilisearch**, not by `LIKE` queries against the database.
Tuned ranking rules and synonyms (e.g. `cors` ⇄ `cross-origin`, `oom` ⇄
`out of memory`) return typo-tolerant, relevance-ranked results in
sub-millisecond query time, driving a debounced, keyboard-navigable live search
box without ever blocking the primary database.

### 🎨 Responsive before/after code blocks (rose / emerald)

Every verified fix renders a side-by-side **before/after** diff. The **before**
block is themed **rose** (red) and the **after** block **emerald** (green) — an
instantly scannable visual contrast for "broken vs. fixed." The pair stacks on
mobile and splits into two columns on large screens
(`grid-cols-1 lg:grid-cols-2`), with horizontally scrollable, whitespace-preserving
`<pre>` regions and full dark-mode support.

### 🔎 Dynamic SEO metadata

Detail pages are server-rendered with per-error metadata generated at request
time via Next.js `generateMetadata`. Each `/error/[slug]` route emits a unique
`<title>`, a truncated meta description derived from the explanation, and
**Open Graph** tags (`type: article`, canonical URL) — so every error is a
first-class, shareable, crawlable landing page. A request-cached fetch
(`React.cache`) ensures metadata and the page body share a single network call
per render.

### 🗑️ Dual-cascade deletes

Deleting an `Error` always removes its dependent `RootCause` and `VerifiedFix`
rows — guaranteed at **two layers**:

1. **ORM level** — relationships use `cascade="all, delete-orphan"`, so the
   SQLAlchemy unit of work cleans up children on object deletion.
2. **Database level** — foreign keys declare `ondelete="CASCADE"` with
   `passive_deletes=True`, so the integrity guarantee holds even for raw SQL
   deletes that bypass the ORM.

No orphaned rows, no leaked relations — whichever path the delete takes.

### 🩺 Plus the operational basics

- **Health-gated orchestration** — Compose starts services in dependency order,
  each gated on a real health check.
- **Graceful degradation** — the API boots and reports `degraded` via `/health`
  instead of crashing when a dependency is down.
- **Clean error mapping** — no stack traces leak to clients.
- **One-command boot** — `docker compose up --build` brings the entire stack up.

---

## Quickstart (Docker Compose)

**Prerequisites:** Docker Engine 24+ and the Docker Compose v2 plugin
(`docker compose`, not the legacy `docker-compose`).

```bash
# 1. Clone and enter the project
git clone <your-fork-url> error-encyclopedia
cd error-encyclopedia

# 2. (Optional) customize secrets/ports — sensible defaults work out of the box
cp .env.example .env

# 3. Build and start the whole stack (detached)
docker compose up --build -d
```

Compose starts the services in dependency order, gated on health checks:

1. **postgres** and **meilisearch** start and must report healthy, then
2. **backend** starts, runs schema + index bootstrap, and must report healthy, then
3. **frontend** starts.

Once everything is up:

| Service              | URL                            |
| -------------------- | ------------------------------ |
| **Frontend (app)**   | http://localhost:3000          |
| **Backend API**      | http://localhost:8000          |
| **Interactive docs** | http://localhost:8000/docs     |
| **Health check**     | http://localhost:8000/health   |
| **Meilisearch**      | http://localhost:7700          |

Useful lifecycle commands:

```bash
docker compose ps              # show service status & health
docker compose logs -f         # tail logs from all services
docker compose down            # stop & remove containers
docker compose down -v         # also delete the postgres/meili data volumes
```

---

## Seeding sample data

The database starts empty. Load three realistic, fully-formed errors
(`ModuleNotFoundError`, a CORS error, and a JavaScript `TypeError`) — including
root causes and verified before/after fixes — and index them for search:

```bash
docker compose exec backend python seed.py
```

The seeder is **idempotent**: it skips any error whose slug already exists, so
it's safe to run more than once. It reuses the application's own building blocks
(`crud.create_error`, the Pydantic `*Create` schemas, and the search index), so
seeded data goes through exactly the same path as data created via the API.

After seeding, try searching for `cors`, `module`, or `undefined` at
http://localhost:3000.

---

## API reference

Interactive OpenAPI docs are served at **http://localhost:8000/docs**.

| Method | Path                         | Description                                          |
| ------ | ---------------------------- | ---------------------------------------------------- |
| `GET`  | `/health`                    | Liveness/readiness probe (DB + search dependencies). |
| `GET`  | `/api/search?q=&limit=`      | Full-text search across the encyclopedia (Meilisearch). |
| `GET`  | `/api/autocomplete?q=`       | Lightweight typeahead suggestions.                   |
| `GET`  | `/api/errors?limit=&offset=` | List errors, most recent first.                      |
| `GET`  | `/api/errors/{slug}`         | Full error detail (causes, fixes, related errors).   |
| `POST` | `/api/errors`                | Create an error and index it for search.             |

Example:

```bash
curl "http://localhost:8000/api/search?q=cors&limit=5"
```

---

## Configuration

All configuration is environment-driven. For Docker Compose, copy `.env.example`
to `.env` and adjust; every variable has a safe default so the stack runs without
one. Key variables:

| Variable                              | Used by  | Default                 | Notes                                                          |
| ------------------------------------- | -------- | ----------------------- | -------------------------------------------------------------- |
| `POSTGRES_USER` / `_PASSWORD` / `_DB` | both     | `error_enc` / …         | PostgreSQL credentials.                                       |
| `MEILI_MASTER_KEY`                    | both     | sample key              | **Change for any real deployment** (≥ 16 bytes required).     |
| `NEXT_PUBLIC_API_BASE_URL`            | frontend | `http://localhost:8000` | Browser-facing API URL; baked into the client bundle.        |
| `API_BASE_URL_INTERNAL`               | frontend | `http://backend:8000`   | Server-side API URL over the Docker network (set in compose). |

The backend reads `POSTGRES_*` and `MEILISEARCH_*` directly (see
`backend/.env.example` for the full list).

---

## Local development (without Docker)

You'll need Python 3.11+, Node 20+, and reachable PostgreSQL and Meilisearch
instances.

**Backend:**

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                # point at your local services
uvicorn main:app --reload --port 8000
python seed.py                                      # optional: load sample data
```

**Frontend:**

```bash
cd frontend
npm install
# Defaults to http://localhost:8000; override if needed:
export NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
npm run dev                                         # http://localhost:3000
```

---

## Project layout

```
error-encyclopedia/
├── docker-compose.yml        # Orchestrates all four services
├── .env.example              # Compose configuration template
├── backend/
│   ├── Dockerfile            # python:3.11-slim, uvicorn on :8000
│   ├── main.py               # FastAPI app, CORS, exception handling
│   ├── database.py           # Async engine, settings, session, lifecycle
│   ├── models.py             # Error / RootCause / VerifiedFix ORM models (dual-cascade)
│   ├── schemas.py            # Pydantic request/response contracts
│   ├── crud.py               # Async repository functions + slug generation
│   ├── search_index.py       # Meilisearch index config & sync
│   ├── routers/              # health, search, errors endpoints
│   ├── services/             # search orchestration / related errors
│   └── seed.py               # Idempotent sample-data seeder
└── frontend/
    ├── Dockerfile            # node:20-alpine standalone build
    ├── app/                  # App Router pages (home + /error/[slug] with dynamic SEO)
    ├── components/           # SearchBox (client component)
    └── lib/                  # Typed API client & shared types
```

---

## License

[MIT](./LICENSE) © 2026 urrra39
