# Implementation Plan: Second Brain CRM

**Spec**: [spec.md](spec.md)
**Research**: [research.md](research.md)
**Data Model**: [data-model.md](data-model.md)
**Constitution**: [.specify/memory/constitution.md](../../.specify/memory/constitution.md)

---

## Technical Context

| Component | Technology | Status |
|-----------|-----------|--------|
| Backend | Python 3.12+ / FastAPI | Resolved |
| Frontend | Next.js 16.3.3 (Active LTS) App Router + Tailwind CSS v4, dark-first per `mockups/BRANDBOOK.md` | Resolved |
| Database | PostgreSQL 16 + PgBouncer | Resolved |
| Task Queue | Redis 7 + Celery | Resolved |
| Semantic Store | Convex (vector search, 1536 dims) | Resolved |
| Embeddings | OpenRouter openai/text-embedding-3-small | Resolved |
| LLM | OpenRouter (multi-model) | Resolved |
| WhatsApp | Evolution API 2.3.7 (self-hosted, Docker) | Resolved |
| Collabute | Streamable HTTP MCP, OAuth 2.1 + PKCE | Resolved (tool schemas pending first auth) |
| Context.dev | `/v1/web/search` opportunity discovery + `/v1/brand/retrieve` enrichment, shared 500-credit ledger | Resolved |
| Google | OAuth2 (gmail.readonly, calendar.readonly, drive.metadata.readonly) | Resolved |
| Lint | Ruff (Python) + ESLint/Prettier (TS) | Resolved |

### NEEDS CLARIFICATION → Resolved

Architecture decisions are resolved in [research.md](research.md). Implementation remains gated by the spike items below and the runtime credential/dependency preflight.

### Spike Items (must validate before implementation freezes)

1. **Convex filter AND composition**: `q.eq` + `q.or` only — composite `owner_scope` field is the safe fallback. Validate in a 30-min spike.
2. **Collabute tools/list fixture**: OAuth-gated, undocumented. Must capture after first authenticated connection.
3. **Gmail `q=after:<epoch>`**: epoch-seconds support is Gmail search-box behavior, not API reference. Validate in OAuth spike.
4. **Collabute `Mcp-Session-Id`**: stateful vs stateless. Check initialize response headers.
5. **Collabute `expires_in`**: capture from first token response.

---

## Constitution Check

| Principle | Compliance |
|-----------|-----------|
| OOP | Domain entities as dataclasses/pydantic models with encapsulated state. Connectors implement Protocol. |
| SOLID-S | Each connector, service, worker has one responsibility. `PersonResolver` resolves; `GmailConnector` syncs. |
| SOLID-O | New sources = new `SourceConnector` impl + registry line. Zero core changes. |
| SOLID-L | All connectors substitutable for `SourceConnector` protocol. Contract tests verify. |
| SOLID-I | Split fat interfaces: `SourceConnector` (sync), `OAuthConnector` (auth flow), `WebhookReceiver` (events). |
| SOLID-D | Services depend on protocols (ABCs), injected via constructor. `QueryService` depends on `EmbeddingProvider` protocol, not `OpenRouterClient`. |
| YAGNI | P0 sources only. Bounded on-demand Context.dev vacancy search is included; no LinkedIn scraping, broad crawling, continuous monitoring, automatic application, or sending. |
| KISS | Relational graph (not Neo4j). Single Convex table. Composite scope field for filtering. |
| DRY | One `CursorInvalidated` handler for Gmail 404 + Calendar 410. One `SourceConnector` contract. |
| CLink | Composition: inject `EmbeddingProvider`, `ConvexClient`, `SecretStore` via constructor. |
| IsDry | Idempotency keys: `(source_connection_id, external_id)` for interactions, `(chunk_key, embedding_version)` for chunks, `(owner_id, source, source_key)` for follow-ups. |
| Size Guards | CI-enforced: file ≤700, class ≤300, function ≤80. Ruff + custom script. |

**Gate**: PASS. No violations.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Next.js 16 Frontend                        │
│  (App Router, Tailwind v4, DESIGN.md Technocratic Brutalist) │
└──────────────────────────┬──────────────────────────────────┘
                           │ REST API (JWT auth)
┌──────────────────────────▼──────────────────────────────────┐
│                   FastAPI Backend (Python)                    │
│  ┌─────────┐ ┌──────────┐ ┌─────────┐ ┌──────────────────┐  │
│  │  API    │ │ Connectors│ │ Domain  │ │   Query Service  │  │
│  │ Routes  │ │ Registry  │ │ Services│ │ (RAG + Graph)    │  │
│  └─────────┘ └──────────┘ └─────────┘ └──────────────────┘  │
│       │           │              │              │            │
│  ┌────▼───────────▼──────────────▼──────────────▼──────┐    │
│  │              Infrastructure Layer                   │    │
│  │  PostgreSQL │ Redis │ Convex Client │ OpenRouter    │    │
│  └─────────────────────────────────────────────────────┘    │
└──────────┬───────────────────────────────────┬──────────────┘
           │                                   │
    ┌──────▼──────┐                     ┌──────▼──────┐
    │ PostgreSQL  │                     │   Convex    │
    │ (canonical) │                     │  (semantic) │
    │  + Outbox   │                     │  vector idx │
    └─────────────┘                     └─────────────┘
           │
    ┌──────▼──────┐
    │   Celery    │── OpenRouter (embeddings + generation)
    │   Workers   │── Context.dev (vacancy search + enrichment)
    │             │── Evolution API (WhatsApp REST + webhooks)
    │             │── Collabute MCP (meetings)
    │             │── Google APIs (Gmail, Calendar, Drive)
    └─────────────┘
```

---

## Implementation Phases

### Phase 0: Foundation (Day 1)

**Goal**: Runnable skeleton with DB, auth, and project structure.

| Task | Deliverable | Size Guard |
|------|-------------|------------|
| 0.1 Project scaffold | `backend/`, `frontend/`, `convex/`, `docker/` dirs. `pyproject.toml` with Ruff. `package.json` with ESLint. | — |
| 0.2 Docker Compose | PostgreSQL 16 + PgBouncer + Redis + Evolution API 2.3.7 (with PII patch) | — |
| 0.3 Database migrations | Alembic: all tables from data-model.md. `gen_random_uuid()`, indexes, constraints. | — |
| 0.4 Secret storage | `SecretStore` protocol + AES-256 implementation. `auth_ref` references. | ≤80 lines/function |
| 0.5 JWT auth | Owner login, session token, cookie (secure, HTTP-only, same-site). | — |
| 0.6 Health endpoints | `/api/health` + `/api/health/deps` (preflight). | — |
| 0.7 Size guard CI script | Python + TS line counters. File ≤700, class ≤300, function ≤80. | — |
| 0.8 Convex schema deploy | `convex/schema.ts` + empty function stubs. `npx convex deploy`. | — |

### Phase 1: Source Connector Framework (Day 1-2)

**Goal**: Pluggable connector architecture with contract tests.

| Task | Deliverable | Size Guard |
|------|-------------|------------|
| 1.1 SourceConnector protocol | `base.py`: `SourceConnector`, `OAuthConnector`, `WebhookReceiver` protocols. | ≤300 lines/class |
| 1.2 Connector registry | DI container. Extensible string source types. | — |
| 1.3 Normalized record mapper | Transform source records to canonical schema. | — |
| 1.4 Sync run tracking | `SyncRun` CRUD. Checkpoint, counts, status. | — |
| 1.5 Cursor invalidation handler | Shared `CursorInvalidated` for Gmail 404 + Calendar 410. | — |
| 1.6 Contract test suite | Parameterized tests: auth, sync, idempotency, cursor, failure isolation, disconnect. | — |
| 1.7 Outlook fixture connector | Prove extensibility: passes contract tests, feeds normalization. Zero core changes. | — |

### Phase 2: Google Integration (Day 2)

**Goal**: Gmail + Calendar + Drive sync with OAuth.

| Task | Deliverable | Size Guard |
|------|-------------|------------|
| 2.1 Google OAuth flow | `GET /api/google/oauth/connect` → redirect → `callback`. State in Redis. `prompt=consent`. | — |
| 2.2 Gmail connector | Initial: `messages.list?q=after:<90d>` + batched `messages.get`. Delta: `history.list`. Cursor: `getProfile().historyId`. | ≤300 lines/class |
| 2.3 Calendar connector | Initial: `events.list(timeMin, singleEvents)`. Delta: `syncToken`. 410 → bounded resync. | ≤300 lines/class |
| 2.4 Drive connector | `files.list?q=sharedWithMe` + explicit fields. Metadata-only. Manual person link for NDA. | ≤300 lines/class |
| 2.5 Token refresh + reauth | `credentials.refresh()`. `invalid_grant` → `reauth_required`. 7-day test-user expiry handling. | — |
| 2.6 Multi-account | One `SourceConnection` per Google account. Dedup contacts across accounts. | — |

### Phase 3: WhatsApp Integration (Day 2-3)

**Goal**: QR connect, history import, live messages via Evolution API.

| Task | Deliverable | Size Guard |
|------|-------------|------------|
| 3.1 Evolution REST client | Create instance (inline webhook), connect, connectionState, logout, delete. | ≤300 lines/class |
| 3.2 Webhook receiver | `POST /api/webhooks/evolution/{instance}`. Validate `x-webhook-secret`. Dedup `(instance, key.id)`. Return 200 after durable enqueue. | ≤80 lines/function |
| 3.3 QR lifecycle handler | `QRCODE_UPDATED` → render base64 in UI. Refresh on rotation. Limit-reached → recoverable state. | — |
| 3.4 MESSAGES_SET handler | Batch array. `isLatest=true` → sync complete. Progress in UI. `syncFullHistory=true` for demo. | — |
| 3.5 MESSAGES_UPSERT handler | Single MessageRaw. Extract `message.conversation`. Normalize `key`, `fromMe`, `remoteJid`, `participant`. | — |
| 3.6 PII-log patch | Patch `console.log(messageRaw)` → `this.logger.debug`. Set `LOG_LEVEL=ERROR,WARN`. | — |
| 3.7 Connection state UI | `CONNECTION_UPDATE` → UI state. `close`/`refused` → retry/logout. | — |

### Phase 4: Collabute Integration (Day 3)

**Goal**: MCP meeting import with OAuth + tool discovery.

| Task | Deliverable | Size Guard |
|------|-------------|------------|
| 4.1 Collabute OAuth | Dynamic registration, PKCE, authorize URL, callback, token exchange. Encrypted token storage. | ≤300 lines/class |
| 4.2 MCP client | `mcp` SDK streamable_http. Initialize → tools/list → tools/call → DELETE. Session per sync run. | ≤300 lines/class |
| 4.3 Tool discovery fixture | Capture `tools/list` response → `contracts/collabute-tools-list.fixture.json`. Verify on subsequent runs. | — |
| 4.4 Meeting normalizer | Map tool output → `InteractionEvent` + `InteractionParticipant`. Optional-tolerant fields. | — |
| 4.5 Action item → follow-up | Dedup by stable ID or content hash. `source_key` = ID/hash. Idempotent creation. | — |
| 4.6 Token refresh + reauth | Refresh at 80% `expires_in`. Rotation. 401 → `needs_reauth`. Preserve cursor. | — |
| 4.7 Rate limiting | 60 rpm token bucket. `RateLimit` headers. 429 → `Retry-After` + backoff. | — |
| 4.8 Calendar/Collabute linking | Stable match → link evidence, don't duplicate meeting. | — |

### Phase 5: Identity Resolution & Graph (Day 3-4)

**Goal**: Merge identities, build relationship graph.

| Task | Deliverable | Size Guard |
|------|-------------|------------|
| 5.1 Identity normalizer | Canonicalize email (lowercase), phone (E.164), URLs, JIDs. Retain raw + source. | — |
| 5.2 Deterministic matcher | Exact verified email, exact normalized phone, exact profile URL → auto-link. Role/shared → no auto-merge. | ≤80 lines/function |
| 5.3 AI merge proposer | LLM (OpenRouter) analyzes name, org, signatures, co-participants. Proposes `MergeCandidate`. Always requires review in P0. | — |
| 5.4 Merge review UI | Conflicting fields, evidence, source identities, consequences. Accept/reject. | — |
| 5.5 Merge operation + undo | `MergeOperation` ledger. Reassign records. Reversible. Source identities immutable. | — |
| 5.6 Relationship builder | Person-to-person, person-to-org employments, interaction counts, strength score (recency/frequency/diversity/manual). | ≤300 lines/class |
| 5.7 Status derivation | `active`/`cold`/`dormant` from 90-day threshold. Manual override. | — |
| 5.8 Memory fact extraction | Promises/needs/decisions as `MemoryFact` suggestions tied to cited evidence. Sensitive facts not inferred. | — |

### Phase 6: Convex Semantic Memory (Day 4)

**Goal**: Embedding pipeline, vector search, RAG.

| Task | Deliverable | Size Guard |
|------|-------------|------------|
| 6.1 Convex functions | Deploy `chunks:upsertBatch`, `tombstoneInteraction`, `purgeTombstoned`, `search`, `fetchResults`. | ≤300 lines/file |
| 6.2 Outbox worker | Celery: `FOR UPDATE SKIP LOCKED`. Load interaction, chunk deterministically, batch OpenRouter embeddings, call Convex. | ≤300 lines/class |
| 6.3 Chunking strategy | Split on message/paragraph boundaries. `chunk_key = sha256(interaction_id:content_version:ordinal)`. Bounded size. | ≤80 lines/function |
| 6.4 Tombstone on delete | `is_deleted=true` + outbox `tombstone` op → Convex `active=false`. Immediate retrieval exclusion. | — |
| 6.5 Reindex support | `embedding_version` partition. Bump version, replay outbox, flip config, purge old. | — |
| 6.6 Degraded mode | Convex unavailable → outbox accumulates, ingestion continues. UI marks semantic search degraded. | — |
| 6.7 Purge cron | Periodic `purgeTombstoned` for docs older than grace window. | — |

### Phase 7: Context.dev Opportunity Search and Enrichment (Day 4-5)

**Goal**: Bounded public vacancy discovery, verification, and organization enrichment with shared credit enforcement.

| Task | Deliverable | Size Guard |
|------|-------------|------------|
| 7.1 Web-search adapter | `POST /v1/web/search`; 10–30 results, UAE country, freshness, query fanout/domain controls, normalized public evidence. | ≤300 lines/class |
| 7.2 Search cache/idempotency | Cache by query fingerprint/config; deduplicate opportunities by canonical URL and evidence content hash. | — |
| 7.3 Opportunity persistence | `MarketSearchRun`, `Opportunity`, `OpportunityEvidence`, and verification-state transitions. | — |
| 7.4 Brand adapter | `POST /v1/brand/retrieve` for selected opportunity organizations. Free-email denylist and cache. | ≤300 lines/class |
| 7.5 Organization upsert | Resolve by normalized domain; store brand fields/provenance without treating them as vacancy evidence. | — |
| 7.6 Credit ledger | Reserve/reconcile provider credits: 100 search, 200 brand, 200 reserve. Expose remaining budget in preflight. | — |

### Phase 8: Opportunity and Network Query (Day 5)

**Goal**: Opportunity-first job questions with cited public evidence and private warm paths.

| Task | Deliverable | Size Guard |
|------|-------------|------------|
| 8.1 Job-goal parser | Extract role, related titles, industry, location, and desired action; allow correction before search. | ≤80 lines/function |
| 8.2 Opportunity-first orchestrator | Context.dev market search → verify results → resolve organizations → Convex search → person aggregation → graph expansion → final ranking. | ≤300 lines/class |
| 8.3 Opportunity verifier | Classify `verified_open_role`, `hiring_signal`, `unverified`, or `stale` from current public evidence. | ≤80 lines/function |
| 8.4 Organization resolver | Normalize public source domains and match opportunities to canonical organizations before optional brand enrichment. | ≤80 lines/function |
| 8.5 Person evidence aggregator | Search by goal/resolved companies, group Convex chunks by `person_ids`, and cap repeated evidence from one interaction. | ≤80 lines/function |
| 8.6 Graph traversal | Opportunity → organization → known person/introducer evidence → interactions/facts. Return evidence-backed warm paths only. | ≤80 lines/function |
| 8.7 Ranking | Rank opportunities by goal fit/freshness/evidence, then people by semantic relevance/path/strength/recency. Expose factors. | — |
| 8.8 LLM answer synthesis | Distinguish open roles/signals/unknown, keep public/private evidence separate, and prefer partial/no-result over unsupported claims. | — |
| 8.9 Citation rendering | Vacancy claims cite public URLs; relationship claims cite private source records; brand facts are external enrichment. | — |
| 8.10 Relationship-grounded draft | Generate editable draft from selected opportunity + goal + cited relationship context. Allow edit/copy/external handoff/reminder/save; reject sending/applying. | — |
| 8.11 Degraded query | Market or private retrieval failure returns the other evidence set with `degraded: true`; ingestion remains available. | — |

### Phase 9: Frontend (Day 5-6)

**Goal**: All P0 user-facing flows per DESIGN.md.

| Task | Deliverable | Size Guard |
|------|-------------|------------|
| 9.1 Layout + design system | Tailwind v4 config from DESIGN.md. Technocratic Brutalist. Safety Orange. No shadows. 1px borders. | — |
| 9.2 Connections page | Google/WhatsApp/Collabute connect. OAuth redirect. QR render. Sync progress. Status badges. | — |
| 9.3 People directory | Search, filter by tag/status. Source badges. Sort by last interaction. | — |
| 9.4 Person profile | Unified timeline, identities, employments, relationship, documents, facts, follow-ups. Source filtering. | — |
| 9.5 Merge review | Compare evidence, source identities, conflicting fields. Accept/reject/undo. | — |
| 9.6 Follow-up dashboard | Sorted by overdue/due date, then priority. Provenance. Status transitions. | — |
| 9.7 Opportunity-first interface | Goal confirmation → Context.dev search progress → verified roles/signals → warm paths → separate public/private citations → draft/edit/copy/reminder/save actions. | — |
| 9.8 Data controls | Disconnect/delete per source. Consent info before sync. Pause/resume. | — |
| 9.9 Keyboard accessibility | All core flows keyboard-navigable. Visible focus. WCAG AA contrast. | — |

### Phase 10: Demo Pipelines & Preflight (Day 6-7)

**Goal**: Two repeatable demo pipelines, stable for 3 rehearsals.

| Task | Deliverable | Size Guard |
|------|-------------|------------|
| 10.1 Pipeline A script | Fragmented identity → unified profile. Real Google OAuth + Evolution QR. | — |
| 10.2 Pipeline B script | Dubai Product Manager goal → Context.dev vacancies → verified opportunities → Convex/graph warm paths → dual citations → draft/copy/save/reminder. | — |
| 10.3 Preflight checker | `/api/health/deps`. Verify all dependencies. Credits remaining. Collabute meeting <7 days. | — |
| 10.4 Pre-synced fallback | Real connector snapshot for live-outage fallback. Clearly disclosed. No fabricated mocks. | — |
| 10.5 Demo data prep | Team-controlled test accounts. Synthetic/consented contacts. NDA document in Drive. | — |
| 10.6 Three rehearsals | Full demo script passes 3 consecutive times. Graceful degradation tested. | — |

---

## Demo Pipeline Implementation

### Pipeline A: Fragmented Identity → Unified Profile

```
Step 1: Preflight
  → GET /api/health/deps (all green)

Step 2: Connect Google
  → POST /api/connections/gmail/connect → redirect → OAuth → callback
  → Connection status: connected → syncing

Step 3: Import Gmail + Calendar + Drive
  → Celery: Gmail initial sync (90d) + Calendar sync + Drive metadata
  → UI: progress bars, processed/skipped/error counts

Step 4: Connect WhatsApp
  → POST /api/connections/whatsapp/connect → Evolution create instance
  → UI: QR code render (QRCODE_UPDATED webhook)
  → User scans → CONNECTION_UPDATE state=open
  → MESSAGES_SET batches → progress → isLatest=true

Step 5: Live message
  → Send test message → MESSAGES_UPSERT webhook → timeline update <3s

Step 6: Identity resolution
  → Deterministic: email match → auto-link
  → Ambiguous: AI proposes → MergeCandidate → UI review → accept
  → Open unified profile: cross-source timeline, source badges, NDA link

Step 7: Convex verification
  → Diagnostics: same interaction references in PG + Convex chunks
  → Tombstone test: delete interaction → immediately unretrievable
```

### Pipeline B: Meeting Evidence → Network Action

```
Step 1: Connect Collabute
  → POST /api/connections/collabute/connect → OAuth → AuthKit human login
  → Callback → token exchange → MCP initialize → tools/list (capture fixture)

Step 2: Import meeting
  → tools/call for recent meeting (<7 days)
  → Normalize: participants, decisions, action items
  → Each participant → identity resolution → person profile link

Step 3: Create follow-up
  → Action item → FollowUp (idempotent, source_key = Collabute action ID)
  → Dashboard: follow-up with meeting citation

Step 4: Search current opportunities first
  → POST /api/query with the Dubai crypto Product Manager goal from demo.md
  → Parse role/related titles/industry/location/action
  → Context.dev POST /web/search (10–30 results, country=ae, explicit freshness)
  → Normalize and verify public evidence as open role, hiring signal, unverified, or stale

Step 5: Resolve companies and warm paths
  → Match opportunity domains to canonical organizations
  → Context.dev /brand/retrieve only for selected organizations within the shared credit ledger
  → Convex vector search (1536-dim) for goal + resolved companies
  → Aggregate chunks by person → graph expansion → opportunity/person ranking

Step 6: Combined answer, citations, and action
  → Show opportunities first, each with verification status and public URL citation
  → Attach known people/warm paths with separate private relationship citations
  → Show at least one opportunity with no warm path when supported
  → Generate selected-opportunity draft → edit/copy/save or create reminder
  → No automatic sending or application
```

---

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| Google 7-day token expiry | Demo blocked | Re-consent at preflight. `reauth_required` UI state. |
| Evolution `console.log` PII leak | Privacy violation | Patch source. `LOG_LEVEL=ERROR,WARN`. Container log isolation. |
| Collabute tool schemas unknown | Adapter blocked | Spike: capture tools/list after first auth. Provisional normalizer. |
| Convex filter AND not documented | Search broken | Composite `owner_scope` field. 30-min spike. |
| Context.dev budget exhaustion | Vacancy search/enrichment unavailable | Shared credit ledger: 100 search, 200 brand, 200 reserve; cache/dedup and partial network-only fallback. |
| Demo instability | Failed presentation | 3 rehearsals. Pre-synced fallback. Graceful degradation. |

---

## Post-Plan Constitution Re-Check

| Principle | Post-Design Compliance |
|-----------|----------------------|
| OOP | ✅ Entities, connectors, services are objects with encapsulated state |
| SOLID | ✅ Protocols for connectors, embedding, secret storage. DI throughout. |
| YAGNI | ✅ P0 sources only. No LinkedIn/Telegram/Outlook in implementation phases. |
| KISS | ✅ Relational graph, single Convex table, composite scope field. |
| DRY | ✅ Shared CursorInvalidated, one SourceConnector contract, one outbox pattern. |
| CLink | ✅ All dependencies injected. No concrete class references in domain layer. |
| IsDry | ✅ Idempotency keys on all external operations. Tombstone-first deletion. |
| Size Guards | ✅ Every task notes limits. CI script in Phase 0. |

**Gate**: PASS.
