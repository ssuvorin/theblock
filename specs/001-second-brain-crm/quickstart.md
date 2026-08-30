# Quickstart: Second Brain CRM

## Prerequisites

- Python 3.12+
- Node.js 20+ (for Convex deployment + Next.js frontend)
- Docker + Docker Compose
- PostgreSQL 16+ (or use Docker)
- Redis 7+ (or use Docker)

## 1. Clone & Setup

```bash
git clone <repo-url> theblock
cd theblock
cp .env.example .env  # Fill in secrets (see below)
```

## 2. Environment Variables

```env
# PostgreSQL
DATABASE_URL=postgresql://crm:crm@localhost:5432/second_brain
PGBOUNCER_POOL_SIZE=20

# Redis
REDIS_URL=redis://localhost:6379/0

# Convex
CONVEX_DEPLOY_URL=https://<your-deployment>.convex.cloud
CONVEX_DEPLOY_KEY=<deploy_key>
ACTIVE_EMBEDDING_VERSION=v1

# OpenRouter
OPENROUTER_API_KEY=<key>
EMBEDDING_MODEL=openai/text-embedding-3-small
EMBEDDING_DIMENSIONS=1536
GENERATION_MODEL=<chosen model>

# Google OAuth (runtime secrets — never commit)
GOOGLE_CLIENT_ID=<id>
GOOGLE_CLIENT_SECRET=<secret>
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/api/google/oauth/callback

# Evolution API
EVOLUTION_API_URL=http://localhost:8080
EVOLUTION_API_KEY=<strong random key>
EVOLUTION_WEBHOOK_SECRET=<rotated secret>

# Collabute
COLLABUTE_MCP_URL=https://api.collabute.ai/api/mcp
COLLABUTE_OAUTH_REDIRECT_URI=http://localhost:8000/api/integrations/collabute/callback

# Context.dev
CONTEXT_DEV_API_KEY=<ctxt_secret_...>

# App
JWT_SECRET=<strong random key>
ENCRYPTION_KEY=<32-byte key for secret storage>
OWNER_EMAIL=demo@secondbrain.app
OWNER_PASSWORD=<demo password>
```

## 3. Start Infrastructure

```bash
docker compose up -d postgres redis pgbouncer
```

## 4. Start Evolution API (WhatsApp)

```bash
# Build from pinned source with PII-log patch
cd docker/evolution
docker compose up -d evolution-api
# Verify: curl http://localhost:8080/instance/fetchInstances -H "apikey: $EVOLUTION_API_KEY"
```

## 5. Deploy Convex Functions

```bash
cd convex/
npx convex deploy
# Schema + functions (chunks:upsertBatch, search, tombstoneInteraction, purgeTombstoned)
```

## 6. Install the Backend

```bash
cd backend/
pip install -e ".[dev]"
```

The schema is authored in `app/models.py` and applied by Alembic. The app runs
`alembic upgrade head` itself on startup, against the engine it already holds, so local runs,
tests, and the container all take the same path. To apply migrations by hand:

```bash
cd backend/
CRM_DATABASE_URL="postgresql+psycopg://..." alembic upgrade head
```

After changing a model, generate the matching revision — `tests/test_schema_source.py` fails
until you do:

```bash
cd backend/
CRM_DATABASE_URL="sqlite:///./tmp.db" alembic upgrade head
CRM_DATABASE_URL="sqlite:///./tmp.db" alembic revision --autogenerate -m "describe the change"
```

## 7. Start Backend

```bash
cd backend/
uvicorn app.main:app --reload --port 8000
```

## 8. Start Frontend

```bash
cd frontend/
npm install
npm run dev  # http://localhost:3000
```

## 9. Start Celery Workers

```bash
cd backend/
celery -A app.celery_app worker --loglevel=info -Q sync,indexing,enrichment
celery -A app.celery_app beat --loglevel=info
```

## 10. Demo Preflight

```bash
curl http://localhost:8000/api/health/deps
# Verify all dependencies healthy:
# postgresql: healthy
# redis: healthy
# convex: healthy
# openrouter: healthy
# evolution: healthy
# google_oauth: configured
# collabute: connected (or needs_reauth — re-consent if 7+ days)
# context_dev: { web_search: ready, brand_retrieve: ready, credits_remaining: >= 200 }
```

## 11. Run Demo Pipelines

### Pipeline A: Fragmented Identity → Unified Profile

1. Open `http://localhost:3000`
2. Login with demo credentials
3. Settings → Connections → Connect Google → OAuth → consent
4. Wait for Gmail + Calendar + Drive sync (watch progress bar)
5. Settings → Connections → Connect WhatsApp → scan QR
6. Wait for initial history import (watch progress)
7. Send a test WhatsApp message to the connected number
8. Go to People → find the test contact → open profile
9. Verify: cross-source timeline, source badges, NDA document link
10. Review any pending merge candidates → accept/reject

### Pipeline B: Current Opportunity → Warm Network Path

1. Settings → Connections → Connect Collabute → OAuth → consent
2. Wait for MCP tool discovery + recent meeting sync; verify its cited follow-up
3. Go to Job Search and enter the Dubai crypto Product Manager query from `demo.md`
4. Confirm the parsed role, related titles, industry, and UAE location
5. Verify Context.dev `/web/search` runs first with bounded results, UAE localization, freshness, and available credit budget
6. Verify results are separated into `verified_open_role`, `hiring_signal`, `unverified`, and `stale`
7. Open a result and verify its public source URL and checked timestamp
8. Verify selected opportunity organizations are resolved/enriched without using brand data as vacancy proof
9. Verify Convex then finds relevant people and PostgreSQL reconstructs evidence-backed warm paths
10. Verify public opportunity citations and private relationship citations are displayed separately
11. Generate a relationship-grounded draft, edit/copy it or create a reminder/save the opportunity
12. Verify the CRM does not send a message or apply automatically

## Project Structure

```
theblock/
├── backend/                 # Python FastAPI + Celery
│   ├── app/
│   │   ├── main.py          # FastAPI app
│   │   ├── connectors/      # SourceConnector implementations
│   │   │   ├── base.py      # SourceConnector protocol
│   │   │   ├── gmail.py
│   │   │   ├── calendar.py
│   │   │   ├── drive.py
│   │   │   ├── whatsapp.py
│   │   │   └── collabute.py
│   │   ├── domain/          # Domain entities + services
│   │   │   ├── entities.py
│   │   │   ├── resolver.py  # Entity resolution
│   │   │   ├── graph.py     # Relationship graph
│   │   │   └── query.py     # NL network query
│   │   ├── infra/           # Infrastructure
│   │   │   ├── db.py        # PostgreSQL
│   │   │   ├── convex.py    # Convex client
│   │   │   ├── openrouter.py
│   │   │   ├── secrets.py   # Encrypted secret storage
│   │   │   └── celery_app.py
│   │   ├── api/             # FastAPI routes
│   │   └── workers/         # Celery tasks
│   │   └── migrations/      # Alembic revisions, generated from models.py
│   ├── scripts/             # Archive generator and import CLI
│   ├── tests/
│   └── pyproject.toml       # Ruff config
├── frontend/                # Next.js 16 + Tailwind v4 (dark-first, BRANDBOOK.md)
│   ├── app/                 # App Router
│   ├── components/
│   └── package.json
├── convex/                  # TypeScript Convex functions
│   ├── schema.ts
│   ├── chunks.ts
│   └── package.json
├── docker/                  # Docker Compose files
│   ├── evolution/           # Evolution API 2.3.7 + PII patch
│   └── compose.yaml         # PostgreSQL, Redis, PgBouncer
├── specs/001-second-brain-crm/
│   ├── spec.md
│   ├── research.md
│   ├── data-model.md
│   ├── plan.md              # ← This file
│   ├── contracts/
│   │   ├── api.md
│   │   ├── source-connector.md
│   │   ├── evolution-api.md
│   │   ├── collabute-mcp.md
│   │   ├── convex-semantic.md
│   │   └── context-dev.md
│   └── checklists/
│       └── requirements.md
├── .specify/
│   ├── memory/constitution.md
│   └── feature.json
├── DESIGN.md
├── demo.md                  # Canonical opportunity-first presentation flow
└── AGENTS.md
```

## Size Guard CI

```bash
# Python: Ruff + custom line counter
ruff check backend/
python scripts/size_guard.py backend/ --file 700 --class 300 --function 80

# TypeScript: ESLint + custom line counter
eslint frontend/ --max-lines 700
node scripts/size_guard.ts frontend/ --file 700 --class 300 --function 80
```
