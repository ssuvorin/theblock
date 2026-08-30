# Research: Second Brain CRM — Blocking Validation

**Date**: 2026-08-30
**Status**: Architecture decisions are resolved. Runtime implementation remains blocked on authenticated Collabute `tools/list`, Google callback/test-user configuration, sanitized Evolution build verification, and live credential preflight.

---

## R1: Google OAuth2 (Gmail, Calendar, Drive)

### Decision

Backend-owned OAuth2 callback on FastAPI. Dev: `http://localhost:8000/api/google/oauth/callback`. Prod: `https://<api-domain>/api/google/oauth/callback`. Register both URIs on one OAuth client. State = random 256-bit nonce stored in Redis (one-time, TTL 10min), validated constant-time on callback.

Scopes: `gmail.readonly` (restricted), `calendar.readonly` (sensitive), `drive.metadata.readonly` (restricted). Testing mode: no verification needed. Up to 100 test users. **Critical: test-user refresh tokens expire after 7 days** — demo preflight must re-consent within 7 days.

Gmail sync: initial = `messages.list?q=after:<epoch_90d>` (maxResults 500, paginated) + batched `messages.get`. Snapshot `getProfile().historyId` as cursor H0 *before* initial import. Delta = `history.list?startHistoryId=H0&historyTypes=messageAdded`. HTTP 404 = cursor expired → bounded 90-day resync.

Calendar sync: initial = `events.list(timeMin=now-90d, singleEvents=true)` paginated; persist `nextSyncToken`. Incremental = same endpoint with `syncToken`. HTTP 410 = token expired → bounded resync. `timeMin`/`q`/`orderBy` incompatible with `syncToken`.

Drive sync: `files.list?q=sharedWithMe and modifiedTime > '<90d>'` with explicit `fields=nextPageToken,files(id,name,mimeType,owners,sharingUser,modifiedTime,webViewLink,shared)`. Metadata-only — no content download.

### Rationale

- `prompt=consent` required on every connect to guarantee `refresh_token` (Google only issues it on first auth without prompt).
- `gmail.readonly` required (not `gmail.metadata` — metadata scope bans `q=` and returns no body).
- `drive.metadata.readonly` required (not `drive.file` — cannot enumerate `sharedWithMe`).
- Shared `CursorInvalidated` handler for Gmail 404 and Calendar 410.

### Alternatives Considered

- Next.js API route callback → rejected (exposes code to second service, needs client_secret).
- Internal user type (no 7-day expiry) → viable only if team has Google Workspace org.
- `gmail.metadata` scope → rejected (no `q=` support, no body text).

### Key APIs

| Operation | Endpoint |
|-----------|----------|
| Auth URL | `https://accounts.google.com/o/oauth2/v2/auth` |
| Token exchange | `POST https://oauth2.googleapis.com/token` |
| Gmail profile (cursor) | `GET /gmail/v1/users/me/profile` |
| Gmail list | `GET /gmail/v1/users/me/messages?q=after:<epoch>&maxResults=500` |
| Gmail history | `GET /gmail/v1/users/me/history?startHistoryId=<H>&historyTypes=messageAdded` |
| Gmail get | `GET /gmail/v1/users/me/messages/<id>?format=full` |
| Calendar list | `GET /calendars/primary/events?timeMin=<RFC3339>&singleEvents=true` |
| Calendar sync | `GET /calendars/primary/events?syncToken=<token>&singleEvents=true` |
| Drive list | `GET /drive/v3/files?q=sharedWithMe&fields=<explicit>` |

### Python Dependencies

`google-auth-oauthlib`, `google-api-python-client`, `google-auth`. Sync in Celery workers (sync API). Token refresh via `credentials.refresh(Request())`.

---

## R2: Evolution API 2.3.7 (WhatsApp)

### Decision

Self-host Evolution API 2.3.7 (validated source commit `fa09d37892cdbb1d65a250155d293d92230c5b30`) via Docker at `http://localhost:8080`. Python connector uses REST for lifecycle + webhooks for events.

**Auth**: single `apikey` header. Global key for create/delete; per-instance `hash` (token) for instance-scoped calls. Default global key `'BQR...` is insecure — always set `AUTHENTICATION_API_KEY`.

**QR lifecycle**: push-driven via `QRCODE_UPDATED` webhook. QR rotates every ~45s up to `QRCODE_LIMIT` (default 30). Two payload shapes: `{qrcode:{code,base64,pairingCode,count}}` (normal) and `{message,statusCode}` (limit reached). After `refused`, call `connect` again.

**MESSAGES_SET** (initial history): `data` is an array of `MessageRaw[]` + top-level `isLatest`/`progress`. `syncFullHistory:true` → full device history (many chunks); `false` → recent only. Sync-complete = `isLatest === true`.

**MESSAGES_UPSERT** (live messages): `data` is ONE `MessageRaw` object. Key fields: `key.id`, `key.remoteJid`, `key.fromMe`, `key.participant`, `key.remoteJidAlt` (LID rewrite), `messageType`, `messageTimestamp` (unix seconds), `pushName`. `extendedTextMessage` flattened to `conversation`.

**Webhook auth**: custom static header (`x-webhook-secret`) set via webhook config. Optional `jwt_key` → HS256 Bearer with 10-min expiry. **No HMAC body signature.** No event ID in envelope — dedup on `(instance, data.key.id)`.

**Webhook config**: set inline in `POST /instance/create` body (atomic — no missed events between create and set). Subscribe to `QRCODE_UPDATED, CONNECTION_UPDATE, MESSAGES_SET, MESSAGES_UPSERT`. `byEvents:false` (single endpoint), `base64:false`.

**PII-log sanitization**: `console.log(messageRaw)` near line 1481 in the validated source logs every inbound message body to stdout regardless of `LOG_LEVEL`. **Mitigation**: patch the source or treat container stdout as sensitive. Set `LOG_LEVEL=ERROR,WARN` to suppress logger-mediated leaks. `LOG_BAILEYS=error` for Baileys pino. `SENTRY_DSN` unset to avoid error exfil.

### Rationale

- Inline webhook config at create time prevents missed `QRCODE_UPDATED` between create and `webhook/set`.
- `key.id` is the durable dedup key (Evolution itself dedups on it).
- `@lid` JIDs are not phone numbers — retain as alternate identity, defer unsafe phone matching.
- No config suppresses raw `console.log` calls — source patch or log-driver filtering required.

### Alternatives Considered

- Global webhook (`WEBHOOK_GLOBAL_URL`) → rejected (no custom headers, less secure).
- `jwt_key` only → viable but custom header is simpler for a hackathon.
- RabbitMQ/Kafka event bus → overkill for single-instance demo.

### Key Endpoints

| Operation | Method | Path |
|-----------|--------|------|
| Create instance | POST | `/instance/create` |
| Connect / get QR | GET | `/instance/connect/{name}` |
| Connection state | GET | `/instance/connectionState/{name}` |
| Logout | DELETE | `/instance/logout/{name}` |
| Delete instance | DELETE | `/instance/delete/{name}` |
| Set webhook | POST | `/webhook/set/{name}` |

### Webhook Envelope

```jsonc
{
  "event": "messages.upsert",  // dot.lowercase form
  "instance": "instanceName",
  "data": { /* MessageRaw or MessageRaw[] */ },
  "destination": "<url>",
  "date_time": "<ISO>",
  "sender": "<wuid>",
  "server_url": "<url>",
  "apikey": "<instance token or null>"
}
```

---

## R3: Collabute Coding Tools MCP

### Decision

OAuth 2.1 authorization-code + PKCE (S256) as a **public client** (no client secret). Dynamic client registration via `POST /api/mcp/oauth/register`. Discovery via `/.well-known/oauth-authorization-server`. Scopes: `meeting:read` (minimum), optionally `memory:read`.

MCP Streamable HTTP transport at `https://api.collabute.ai/api/mcp`. JSON-RPC 2.0 over HTTP POST. `Authorization: Bearer <token>` on every request. `Accept: application/json, text/event-stream`. Echo `Mcp-Session-Id` if issued. `MCP-Protocol-Version: 2025-06-18` header post-init.

Session lifecycle: `initialize` → `notifications/initialized` → `tools/list` (capture fixture) → `tools/call` → DELETE session. One short-lived session per sync run.

**Tool discovery**: `tools/list` returns `{tools: [{name, title?, description, inputSchema, outputSchema?}]}`. **Exact meeting tool names/schemas are OAuth-gated and undocumented** — must capture after first authenticated connection. Store as versioned fixture in `contracts/collabute-tools-list.fixture.json`.

**Meeting normalization**: expected fields per FR-4.4: meeting ID, title/time, participants, summary, decisions, owners, action items. All optional-tolerant. Tool results arrive as `content[]` blocks (typically `type:"text"`) — parse defensively.

**Token refresh**: standard `refresh_token` grant. **Rotation mandatory** (store new refresh token every time). Refresh at ~80% of `expires_in`, reactively on 401. Refresh failure → `needs_reauth` status, preserve cursor.

**Rate limits**: 60 requests/minute. `RateLimit`/`RateLimit-Policy` headers on every response. `Retry-After` on 429. Bounded exponential backoff with jitter.

**Free tier**: 30 meetings/month, 7-day context history. Demo meeting must be <7 days old at demo time.

### Rationale

- Public client (auth method `none`) → PKCE mandatory, no client secret to leak.
- `resource` parameter (RFC 8707) required in both authorize and token requests.
- One session per sync run is simpler and safer than long-lived sessions across worker restarts.
- Official `mcp` Python SDK (`mcp.client.streamable_http`) handles SSE parsing and session headers.

### Alternatives Considered

- Device-code flow → viable fallback if redirect callback is awkward.
- Static API keys → do not exist for Collabute.
- Deprecated HTTP+SSE transport → rejected (Collabute is Streamable-HTTP-only).

### Must-Capture-After-First-Auth Checklist

1. Exact meeting tool names + inputSchema/outputSchema
2. Access-token `expires_in` and refresh-token rotation behavior
3. Whether server issues `Mcp-Session-Id` (stateful vs stateless)
4. Actual `RateLimit-Policy` header values
5. Participant identity format (email vs display name)
6. Whether responses are structured JSON or prose text blocks

### Key Endpoints

| Operation | URL |
|-----------|-----|
| Discovery | `GET https://api.collabute.ai/.well-known/oauth-authorization-server` |
| Authorize | `https://api.collabute.ai/api/mcp/oauth/authorize` |
| Token | `POST https://api.collabute.ai/api/mcp/oauth/token` |
| Register | `POST https://api.collabute.ai/api/mcp/oauth/register` |
| MCP endpoint | `POST https://api.collabute.ai/api/mcp` |

### Python Dependencies

`mcp` (official MCP Python SDK, streamable_http client), `httpx` (OAuth flow), `pkce` (or manual PKCE generation).

---

## R4: Convex Semantic Memory & RAG

### Decision

Convex stores `semanticChunks` table with vector index (1536 dims, `openai/text-embedding-3-small`). PostgreSQL is canonical; Convex is derived/searchable state.

**Schema**: single table `semanticChunks` with:
- `chunk_key` (deterministic: `sha256(interaction_id:content_version:ordinal)`)
- `owner_id`, `interaction_id`, `person_ids[]`, `source`, `occurred_at`, `ordinal`
- `text`, `text_hash`, `citation_locator`
- `embedding_model`, `embedding_version`
- `embedding` (`v.array(v.float64())`, 1536 dims)
- `active` (boolean, false = tombstoned), `tombstoned_at`, `indexed_at`

**Vector index**: `vectorIndex("by_embedding", {vectorField: "embedding", dimensions: 1536, filterFields: ["owner_id", "source", "embedding_version", "active"]})`. Use composite scope field (`owner_scope = "{owner_id}:{embedding_version}:active"`) as safest filter encoding since documented filter API is `eq`/`or` only — AND composition is a spike item.

**PostgreSQL outbox**: `semantic_index_outbox` table written in same PG transaction as canonical interaction. Worker claims with `FOR UPDATE SKIP LOCKED`, computes chunks + embeddings via OpenRouter, calls Convex `chunks:upsertBatch` mutation (atomic, idempotent).

**Tombstones**: `active=false` immediately excludes from vector search filter + read-time re-check in fetch query. Periodic purge hard-deletes tombstoned docs older than grace window.

**Reindexing**: version-partitioned. Bump `embedding_version`, replay outbox for all interactions, flip `ACTIVE_EMBEDDING_VERSION` config when backfill drains, purge old version. Dimension change → new vectorIndex (≤4/table allowed) or new table. Never mix dimensions.

**Python integration**: official `convex` PyPI package (v0.7.0). Synchronous — wrap in `asyncio.to_thread` for FastAPI async routes. Use `client.set_admin_auth(deploy_key)` for internal functions. HTTP API fallback via `httpx` if async needed.

**Idempotent writes**: Convex mutations are serializable transactions. Upsert keyed on `(chunk_key, embedding_version)` via `by_chunk_key` index lookup-then-insert/replace. No client-supplied `_id` — Convex generates it.

### Rationale

- Single table (metadata + vector) is simpler than separate embeddings table for the small demo corpus.
- `active` boolean in `filterFields` enables tombstone exclusion in vector search itself.
- Composite scope field is the safest filter encoding (single `q.eq` instead of undocumented AND).
- Outbox pattern guarantees ingestion never blocks on Convex availability (FR-8.5/8.8).
- `vectorSearch` only in actions, returns only `{_id, _score}` — follow-up query loads metadata.

### Alternatives Considered

- pgvector in PostgreSQL → rejected (Convex is required hackathon technology).
- Separate embeddings table → rejected (doubles write complexity for small corpus).
- Redis for outbox → rejected (PostgreSQL is canonical per constitution).

### Key Convex Functions

| Function | Type | Purpose |
|----------|------|---------|
| `chunks:upsertBatch` | internalMutation | Idempotent upsert keyed on (chunk_key, version) |
| `chunks:tombstoneInteraction` | internalMutation | Set active=false for all chunks of an interaction |
| `chunks:purgeTombstoned` | internalMutation | Hard-delete tombstoned docs older than N |
| `chunks:search` | action | vectorSearch + fetchResults with active re-check |
| `chunks:fetchResults` | internalQuery | Load docs by ID, strip vectors, re-check active |

### Convex Limits

- Vector field: `v.array(v.float64())`, exactly 1 per index, dims 2–4096
- ≤16 filterFields per index, ≤4 vector indexes per table
- Per search: 1 query vector, ≤64 filter expressions, limit 1–256
- Filters: equality/OR only (no ranges, no `neq`)
- Documents without exact-dimension vector silently excluded from index
- `vectorSearch` returns only `[{_id, _score}]`
- Doc limit ~1 MiB; 1536 float64s ≈ 12 KiB

---

## R5: Context.dev Organization Enrichment

### Decision

Use `POST https://api.context.dev/v1/brand/retrieve` with `{type: "by_domain", domain: "<normalized>", timeoutMS: 60000, tags: ["hackathon-demo"]}`. Auth: `Authorization: Bearer <key>` (env `CONTEXT_DEV_API_KEY`, keys start `ctxt_secret_`).

**Response (200)**: `brand` object with `title`, `domain`, `description`, `logos[]`, `socials[]`, `address`, `industries.eic[]` (EIC taxonomy, not NAICS/SIC). `key_metadata` with `credits_consumed`/`credits_remaining`. `cache_metadata` with hit/miss status.

**NOT_FOUND**: HTTP 400 with `error_code: "NOT_FOUND"` — normal terminal result, cache as miss, 0 credits consumed. Also `WEBSITE_NOT_FOUND`, `WEBSITE_ACCESS_ERROR` = clean not-found. `INPUT_VALIDATION_ERROR` = caller bug, raise, never cache.

**429**: honor `Retry-After` (1–60s), fall back to exponential backoff, ≤4 attempts, then Celery retry-later. 0 credits consumed. Free work-email plan: 30 req/min.

**Caching**: PostgreSQL table keyed by normalized domain (lowercase, strip scheme/www). Cache both hits and misses for ≥24h. Staleness check at read time — no expiry job needed.

**Budget**: shared Context.dev credit ledger. Reserve at most 200 credits for 20 successful brand calls, at most 100 credits for bounded web searches, and at least 200 credits for demo/retry reserve. Reconcile reservations against `key_metadata.credits_consumed`; refund when the provider reports 0.

**Free-email domains**: client-side denylist (gmail.com, yahoo.com, hotmail.com, outlook.com, aol.com, icloud.com, proton.me + disposables). Skip before API call. If reaches API via `by_email`, returns 422 `FREE_EMAIL_DETECTED` (0 credits).

**NAICS/SIC**: separate 10-credit endpoints, NOT included in `/brand/retrieve`. Store inline EIC classification only for hackathon budget. NAICS/SIC out of scope.

### Rationale

- PostgreSQL cache (not Redis) per constitution — provenance must survive restarts.
- Misses must be cached too, or retries burn rate limit re-resolving dead domains.
- Budget counts only credit-consuming responses, reconciled against `key_metadata`.
- `timeoutMS: 60000` required — <10000 on cold domain fails with 422 `COLD_DOMAIN_TIMEOUT_TOO_LOW`.

### Alternatives Considered

- Redis TTL cache → rejected (loses provenance on restart).
- `by_email` lookup → rejected for enrichment (resolves brand of email provider, not employer).
- NAICS/SIC separate calls → rejected (10 credits each, budget-busting).
- `POST /utility/prefetch` → subscriber-only, unavailable on free plan.

### Python Dependencies

Official `context.dev` PyPI package, or plain `httpx` (one POST + bearer header). SDK does not auto-retry 429/408 — wire retries yourself.

### Adapter Flow

```
1. Normalize domain (lowercase, strip scheme/www)
2. Free-email denylist check → skip (no API call, no budget)
3. PostgreSQL cache lookup → fresh (<24h) → return cached
4. Budget gate: atomically reserve the expected brand-call credits within the 200-credit brand allocation
5. POST /v1/brand/retrieve {type: by_domain, domain, timeoutMS: 60000}
6. Response mapping:
   200 → upsert Organization + provenance + telemetry
   400 NOT_FOUND → cached miss (terminal, refund budget)
   400 INPUT_VALIDATION_ERROR → raise (adapter bug)
   422 FREE_EMAIL → terminal skip
   429 → Retry-After or backoff, ≤4 attempts, then Celery retry
   408/500 → retry with backoff
```

---

## R6: Opportunity-First Retrieval for the Canonical Demo

### Decision

The Dubai Product Manager flow starts with bounded public vacancy discovery, then searches the owner’s private relationship memory for warm paths into the discovered companies:

1. Parse the question into role, related titles, industry, location, and desired action.
2. Call Context.dev `POST /web/search` with 10–30 results, `country: "ae"`, an explicit freshness window, and query variants for public company/ATS vacancy pages.
3. Preserve URL, title, source domain, excerpt or requested Markdown, publication date when available, checked time, cache metadata, and credits consumed.
4. Label a result `verified_open_role` only when accessible public evidence explicitly confirms role, company, location/remote eligibility, and open status. Label weaker expansion/careers evidence `hiring_signal`; ambiguous results remain `unverified`.
5. Resolve each opportunity to an existing/new `Organization` by normalized domain, enriching selected companies through `/brand/retrieve` within the shared Context.dev budget.
6. Generate semantic queries for the goal and resolved organizations; embed them with `openai/text-embedding-3-small`.
7. Search active owner-scoped Convex chunks, aggregate evidence by person, and cap repeated chunks from one interaction.
8. Expand canonical people, organization affiliations, relationships, accepted facts, and introducer evidence in PostgreSQL.
9. Rank opportunities first by goal fit/evidence freshness, then attach people and warm paths ranked by relationship evidence.
10. Generate an answer with separate public opportunity citations and private relationship citations.

OpenRouter may then generate an editable outreach draft from the selected opportunity, goal, and cited relationship context. P0 actions are edit, copy, external-client handoff, reminder, saved opportunity, and follow-up creation; there is no automatic sending or job application.

### Context.dev Web Search Contract

- Endpoint: `POST https://api.context.dev/v1/web/search`.
- Cost assumption: 1 credit per 10 requested results; actual `key_metadata.credits_consumed` is authoritative.
- Query length: 1–500 characters; `numResults`: 10–100, bounded to 10–30 in P0.
- UAE localization uses `country: "ae"`; freshness is one of `last_week`, `last_month`, or `last_year`.
- `queryFanout` may improve recall but must remain inside the credit/request budget.
- Optional `markdownOptions.enabled` is used only for shortlisted results when snippets cannot verify the vacancy.
- LinkedIn authentication/scraping is prohibited. Prefer first-party careers and public ATS sources.

### Rationale

- Job search is the opening user value and makes the demo immediately understandable.
- Context.dev becomes a core sponsor integration rather than decorative company enrichment.
- Convex/person aggregation remains the differentiator: it explains who can help reach each opportunity.
- Separate public/private citations prevent public hiring evidence from being confused with personal relationship evidence.
- Draft-and-copy delivers an actionable ending without channel-specific sending permissions and policy risk.

### Alternatives Considered

- OpenRouter `openrouter:web_search` → valid fallback with URL citations, rejected from P0 to keep one market-search source and emphasize Context.dev.
- Broad crawlers or continuous vacancy monitoring → rejected as unnecessary for the hackathon.
- LinkedIn job scraping → rejected for platform/account risk.
- Showing a functional `Send` or `Apply` button → rejected; automatic sending/application is outside P0.

---

## Cross-Cutting Decisions

### Shared Cursor-Invalidation Pattern

Gmail 404 and Calendar 410 both mean "cursor dead → bounded resync + fresh cursor". Implement once, parameterize per connector.

### Secret Handling

All credentials (Google tokens, Evolution keys, Collabute tokens, OpenRouter/Context.dev keys) stored server-side encrypted, referenced by `auth_ref`. Never in entity JSON, never in logs, never in generated artifacts.

### Demo Preflight Checklist

1. Google: re-consent test accounts within 7 days of demo
2. Evolution: `AUTHENTICATION_API_KEY` set, `LOG_LEVEL=ERROR,WARN`, `console.log(messageRaw)` patched
3. Collabute: OAuth valid, `tools/list` matches fixture, demo meeting <7 days old
4. Convex: deployment healthy, `ACTIVE_EMBEDDING_VERSION` set
5. Context.dev: `/web/search` and `/brand/retrieve` authorized; shared ledger healthy; provider `credits_remaining ≥ 200` demo reserve
6. OpenRouter: API key valid, `openai/text-embedding-3-small` accessible
