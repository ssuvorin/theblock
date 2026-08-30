# Career Brain

A job search engine tells you who's hiring. A CRM tells you who you know. Career Brain connects the opportunity to the person who can help you reach it.

Ask a question like "Product Manager role at a crypto company in Dubai" and the system:

1. Scans the live job market through **Context.dev** — bounded, UAE-localized, credit-budgeted.
2. Verifies each result against public career pages and ATS, separating confirmed vacancies from hiring signals.
3. Searches your private relationship memory through **Convex** vector search — interaction chunks embedded via OpenRouter, owner-scoped, ranked by relevance.
4. Reconstructs evidence-backed warm paths: You → Person you know → Company that's hiring.
5. Drafts a message grounded in the cited opportunity and relationship context. No auto-send.

Built at the Collabute × TheBlock hackathon, Dubai, 30 August 2026.

## Partner technology

### Devin (by Cognition)

Devin built the product end-to-end across 14+ agent sessions: the feature spec, the backend (FastAPI + SQLAlchemy + Alembic), the frontend (Next.js 16 + Tailwind v4), the Convex vector store, the Docker infrastructure, the CI pipeline, and the test suite (158 tests). Every commit carries `Co-Authored-By: Devin` — the full git history is the evidence.

### Convex

Convex is the reactive vector store for semantic relationship evidence. Interaction chunks (LinkedIn messages, invitations) are embedded through OpenRouter (`openai/text-embedding-3-small`, 1536 dimensions) and upserted into Convex through a durable PostgreSQL outbox — so a provider outage never costs the graph. The search action is owner-scoped and returns person IDs, source metadata, and citation locators that the query orchestrator joins with the PostgreSQL relationship graph to produce warm paths.

- `convex/convex/schema.ts` — `semanticChunks` table with 1536-dim vector index, `owner_scope` composite filter.
- `convex/convex/chunks.ts` — `upsertBatch`, `tombstoneInteraction`, `fetchResults`, `search` functions.
- `backend/app/connectors/convex/client.py` — HTTP adapter satisfying `SemanticStorePort`.
- `backend/app/services/semantic_index.py` — outbox drain: claim → chunk → embed → upsert → settle.
- `backend/app/api/semantic.py` — `/api/index` status, `/api/index/drain`, `/api/index/reindex`, `/api/index/search`.

### Context.dev

Context.dev `/web/search` powers the live job market scan. The adapter (`backend/app/connectors/context_dev/web_search.py`) sends bounded, goal-specific queries localized to the UAE with a freshness window, prioritizing first-party career pages and public ATS. Results are credit-budgeted through a atomic reserve/reconcile/fail ledger with row-level locking. A synthetic fallback with explicit disclosure covers the demo when no API key is configured.

## Architecture

```
LinkedIn archive → parse → normalize → owner resolution → graph writer (PostgreSQL)
                                                              ↓
                                                         outbox enqueue
                                                              ↓
                                                    drain: chunk → embed (OpenRouter)
                                                              ↓
                                                    Convex upsertBatch
                                                              ↓
Query → goal parse → Context.dev search → verify opportunities
    → Convex semantic search (warm paths) → PostgreSQL relationship graph
    → rank → answer with public + private citations
    → draft (no auto-send)
```

**Canonical store:** PostgreSQL (via PgBouncer). **Derived store:** Convex vector index. Sync is explicit and eventually consistent through the outbox pattern.

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12+ / FastAPI / SQLAlchemy / Alembic |
| Frontend | Next.js 16 (App Router) / React 19 / Tailwind CSS v4 |
| Database | PostgreSQL 16 + PgBouncer |
| Vector store | Convex (1536-dim, `openai/text-embedding-3-small`) |
| LLM / embeddings | OpenRouter |
| Web context | Context.dev |
| Coding agent | Devin by Cognition |
| Containerization | Docker + Docker Compose |
| CI | GitHub Actions (ruff, eslint, tsc, pytest, size guards, compose validation) |

## Quickstart

```bash
# 1. Clone
git clone https://github.com/ssuvorin/theblock.git
cd theblock

# 2. Copy env
cp .env.example .env
# Fill in: POSTGRES_PASSWORD, CRM_AUTH_SECRET, CRM_OWNER_PASSWORD
# Optional for live integrations: CONVEX_URL, CONVEX_DEPLOY_KEY, OPENROUTER_API_KEY, CONTEXT_DEV_API_KEY

# 3. Deploy Convex functions
cd convex && npx convex deploy && cd ..

# 4. Start everything
docker compose -f docker/docker-compose.yml up --build

# 5. Open
open http://localhost:3000
```

Login with the email and password from your `.env` file. The demo seeds synthetic data automatically. To import a real (or synthetic) LinkedIn export, use the Imports page.

## Demo

- **30-second promo:** `promo/career-brain-promo.mp4`
- **Full demo flow:** `demo.md` — step-by-step walkthrough with verification checklist.

## Project structure

```
theblock/
├── backend/           # FastAPI backend
│   ├── app/
│   │   ├── api/       # REST endpoints
│   │   ├── connectors/  # LinkedIn export, Context.dev, Convex
│   │   ├── domain/    # Ports, schemas, identity normalization
│   │   ├── migrations/  # Alembic (autogenerated from models)
│   │   ├── repositories/  # SQLAlchemy persistence
│   │   └── services/  # Graph writer, semantic index, query orchestrator
│   └── tests/         # 158 tests (behavior + contract)
├── frontend/          # Next.js 16 + Tailwind v4
├── convex/            # Convex vector store (schema + functions)
├── docker/            # Docker Compose + Dockerfiles
├── scripts/           # Size guard CI script
├── specs/             # Feature spec, plan, tasks, contracts
├── mockups/           # Design system + brandbook
├── promo/             # 30-second promo video
└── demo.md            # Canonical demo flow
```

## Engineering

- **Size guards:** file ≤ 700 lines, class ≤ 300, function ≤ 80. Enforced in CI by `scripts/check_size.py`.
- **Lint:** Ruff (Python) + ESLint/Prettier (TypeScript). Zero warnings policy.
- **Idempotency:** imports, outbox claims, and credit reservations are idempotent. Re-importing an archive creates zero duplicate rows.
- **Honest degradation:** provider outages degrade gracefully with named components; defects surface as 500s, not silent empty results.
- **Synthetic data:** demo mode refuses non-synthetic archives. All demo data carries `data_origin = 'synthetic'` and explicit disclosure strings.

## License

Built for the Collabute × TheBlock hackathon. All rights reserved by the team.
