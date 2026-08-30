# Tasks: Second Brain CRM (P0)

**Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md) · **Data Model**: [data-model.md](data-model.md) · **API**: [contracts/api.md](contracts/api.md) · **Context.dev**: [contracts/context-dev.md](contracts/context-dev.md) · **Demo**: [../../demo.md](../../demo.md) · **Constitution**: [../../.specify/memory/constitution.md](../../.specify/memory/constitution.md)

## Strategy: vertical slices, not layers

The repository contains **no application code** — no `backend/`, no `frontend/`, no `convex/`. What exists is `mockups/`: a Claude Design export (interactive canvas, `BRANDBOOK.md`, 8 exported screens, 11 avatars, `support.js`, `image-slot.js`). These are **design artifacts, not a frontend** — there is no `package.json`, no React component, no API client. The frontend must be *built from* them, not wired to them.

Every milestone below must end with something a judge can see in a browser.

### Design source of truth

| Layer | Authority |
|---|---|
| Visual system, tokens, components, motion, copy voice | `mockups/BRANDBOOK.md` — **canonical** |
| Light-theme token values | `DESIGN.md` — fallback theme export only |
| Screen composition reference | `mockups/design/*.png` + the canvas |
| Product behaviour, data, integrations | `spec.md` — **always wins over the brandbook** |

**Dark theme is canonical** (`--bg #0A0B0D`). Light is a fallback and must stay reachable through the single theme attribute the brandbook mandates. `DESIGN.md` is not a competing system: its palette is exactly the brandbook's light ramp (`#F9F9F9` / `#FFFFFF` / `#F3F3F3` / `#1A1C1C` / `#5A4136` / `#E5E5E5` / `#A04200`). Both are "Mono Ether"; the brandbook is the superset.

### Brandbook↔spec reconciliation (resolve before writing UI code)

The mockups were produced **before the opportunity-first pivot** and describe an earlier network-first product. The brandbook loses on every product claim:

| # | Brandbook says | Spec says | Resolution |
|---|---|---|---|
| 1 | Dark theme canonical | DESIGN.md is light | **Dark canonical**, light fallback. No real conflict — see above. |
| 2 | "People, edges, timeline entries and signals **live** in Convex" | PostgreSQL is canonical; Convex is a derived semantic index (FR-8.1) | Convex read-out becomes `SEMANTIC INDEX · N CHUNKS`. Nothing in the UI may imply Convex is the system of record. |
| 3 | Context.dev "turns raw threads into context, resolves entities and ranks who is relevant" | Context.dev does **public vacancy search + brand enrichment** (FR-5); it never sees private threads | Read-out becomes `MARKET SEARCH · N SOURCES CHECKED`. Sending private thread text to Context.dev violates NFR-2. |
| 4 | Mockup README serves on port 8080 | Evolution API owns 8080 (spec.md, quickstart.md, evolution-api.md) | Mockups move to **8081**; frontend dev 3000; backend 8000; Evolution keeps 8080. |
| 5 | Product name "Career Brain" | "Second Brain / Intelligent CRM" | **"Career Brain"** is the user-facing name; specs keep the internal feature name. One name in the UI, one in the repo. |
| 6 | Positioning remembers "email, meetings, **LinkedIn** and messengers" | LinkedIn is post-hackathon, never scraped, `excludeDomains` only (FR-5.7) | Drop LinkedIn from positioning copy. It may appear only as an outbound citation. |
| 7 | Cast: "Daniel Ruiz — **Telegram** contact" | Telegram is P1, not in P0 (FR-15.1) | Re-source Daniel to WhatsApp or Gmail in the seeded corpus. |
| 8 | Collabute "joins the calls **this CRM schedules**, records and transcribes them" | Collabute is a read-only MCP import of existing meetings (FR-4.4); the CRM never schedules, records or transcribes | Read-out becomes `MEETING IMPORT · N MEETINGS`. No scheduling or recording affordance in the UI. |
| 9 | Partner read-outs `1.2M DOCS`, `4,212 THREADS`, `96 MEETINGS` | Fabricated figures must not be presented as live (FR-16, SC-3) | Every read-out binds to a real counter or renders `—`. Hard-coded metrics are a build failure. |
| 10 | Screens are Ask / Profile / Graph / Signals | The demo opens with verified opportunities and dual citations (demo.md, FR-9.4) | **An opportunities screen does not exist in the export.** It must be designed from brandbook primitives — see T1.8. |

Task **T0.8** applies 2, 3, 6, 8 and 9 to the brandbook itself so the file stops contradicting the spec.

Ordering rule: **M1 delivers the job-search value, M2 delivers the Second Brain differentiation, M3 delivers the action.** Real ingestion pipelines (Gmail, Evolution, Collabute) come in M4, after the demo story already works end to end against a prepared corpus.

- **Canonical flow is `demo.md`**: opportunities are discovered publicly first, then connected to private network evidence. This is a *response-structure and evidence-dependency* contract, not a call-order contract — see T3.1.
- **Hard exclusions**: Telegram, LinkedIn login/scraping (LinkedIn stays in `excludeDomains`), continuous vacancy monitoring, automatic sending, automatic applications.
- **Size guards**: file ≤700, class ≤300, function ≤80.
- `[P]` = parallelizable with sibling `[P]` tasks.
- **Deferred out of P0**: see [Deferred](#deferred-explicitly-not-p0) at the end. Do not implement those without cutting something else.

### Scope-specific verification

| Scope | Command |
|---|---|
| Backend | `cd backend && ruff check . && ruff format --check . && pytest -q` |
| Frontend | `cd frontend && npm run lint && npm run typecheck && npm run build` |
| Convex | `cd convex && npx tsc --noEmit && npx convex deploy --dry-run` |
| Size guards | `python scripts/check_size.py` (excludes `mockups/**`) |
| Infra | `docker compose -f docker/docker-compose.yml config -q` |
| Contract fixtures | `pytest backend/tests/contracts -q` |

Run only the scopes a task touched. CI runs all six.

---

## M0 — Runnable vertical foundation

Goal: an authenticated page in a browser reading one row from PostgreSQL. No connectors yet.

### T0.1 Backend scaffold + config
- **Trace**: SC-10, FR-14.1
- **Files**: `backend/pyproject.toml`, `backend/app/main.py`, `backend/app/config.py`, `.env.example`, `scripts/check_size.py`, `.github/workflows/ci.yml`
- **Deps**: —
- **Tests**: settings load from env; a missing required secret fails startup loudly; no secret literal in the repo.
- **Verify**: `curl -sf localhost:8000/api/health`
- **Done**: FastAPI boots; Ruff + size-guard wired into CI with all six scopes above. **`scripts/check_size.py` excludes `mockups/**`** — the export contains `Second Brain Mockups.dc.html` (2046 lines), `support.js` (1911) and `image-slot.js` (1225), which are immutable generated design artifacts, not authored source. The exclusion is a hard-coded ignore list, not a per-file suppression comment.

### T0.2 Frontend scaffold (Next.js 16) [P]
- **Trace**: FR-11.1, NFR-6, BRANDBOOK.md
- **Files**: `frontend/package.json`, `frontend/app/layout.tsx`, `frontend/app/globals.css`, `frontend/lib/api.ts`, `frontend/next.config.ts`
- **Deps**: —
- **Version**: `next@16.3.3` (Active LTS). This is the August 2026 security release fixing two critical vulnerabilities; every earlier `16.3.x` is knowingly vulnerable, which overrides the usual "prefer a release older than 7 days" rule. Do not use a floating range.
- **Tests**: `npm run build` succeeds; base layout renders; axe reports no contrast violation in dark theme.
- **Verify**: `cd frontend && npm run build && npm run dev` (port 3000)
- **Done**: Next.js 16.3.3 App Router + Tailwind v4; typed API client with a single `fetchApi` wrapper; global visible focus styles; dev server on 3000 so 8000/8080 stay free.

### T0.8 Design tokens + brandbook reconciliation [P]
- **Trace**: BRANDBOOK.md §2/§4/§8/§11, FR-8.1, FR-5.7, FR-4.4, NFR-2, NFR-6
- **Files**: `frontend/app/tokens.css`, `frontend/tailwind.config.ts`, `mockups/BRANDBOOK.md`, `mockups/README.md`, `DESIGN.md`
- **Deps**: T0.2
- **Scope**:
  - port the full dark ramp as CSS custom properties (`--bg` … `--idle`) and the light ramp under a single `[data-theme]` attribute, dark as default;
  - map tokens into Tailwind theme so **no component ever hard-codes a hex** (brandbook §11);
  - amend `BRANDBOOK.md` per reconciliation rows 2, 3, 6, 8, 9 above;
  - change `mockups/README.md` serve port to **8081**;
  - add a header note to `DESIGN.md` marking it the light-theme fallback export subordinate to `BRANDBOOK.md`.
- **Tests**: `grep -rE "#[0-9a-fA-F]{6}" frontend/app frontend/components` matches only `tokens.css`; radius rules hold (containers 0, controls 4px); **`box-shadow` appears nowhere** in frontend sources.
- **Verify**: `cd frontend && npm run lint && npm run build`
- **Done**: theme flips with one attribute; the brandbook no longer contradicts the spec.

### T0.9 Component library from mockup primitives
- **Trace**: BRANDBOOK.md §5/§6, NFR-6
- **Files**: `frontend/components/ui/{Button,Badge,Card,SignalCard,Meter,DataTable,EmptyState,MonoLabel}.tsx`
- **Deps**: T0.8
- **Scope**: the eight primitives the brandbook actually defines. Signal card = 3px left border (orange follow-up/cold, green opportunity). Meter = 6px track on `--hi2`, `--idle` when cold. Empty state = dashed 1px on `--low`.
- **Tests**: one filled-orange element per screen region (brandbook §2 "a second filled orange element in one region is a bug") asserted by a component test; every primitive keyboard-reachable with visible focus; no shimmering skeleton.
- **Done**: screens in M1–M4 compose these primitives instead of re-styling ad hoc. Motion (`sbrise`, `sbdash`, `sbpulse`) defined once as keyframes, decoration never animated.

### T0.3 Docker infra (PG + Redis only) [P]
- **Trace**: SC-10
- **Files**: `docker/docker-compose.yml`, `docker/pgbouncer/pgbouncer.ini`
- **Deps**: —
- **Verify**: `docker compose -f docker/docker-compose.yml up -d && docker compose ps`
- **Done**: PostgreSQL 16 + PgBouncer + Redis 7 healthy. **Evolution API is added later in T4.4** — it is not a dependency of the main demo flow.

### T0.4 Core migrations (demo-path tables only)
- **Trace**: FR-14.2, data-model.md
- **Files**: `backend/alembic.ini`, `backend/migrations/env.py`, `backend/migrations/versions/0001_core.py`, `backend/app/models/*.py`
- **Deps**: T0.1, T0.3
- **Scope**: `owner`, `person`, `person_identity`, `organization`, `source_connection`, `conversation`, `interaction_event`, `interaction_participant`, `relationship`, `follow_up`, `document`, `document_person_link`, `sync_run`, `outbox`. Dependency roots first; circular FKs (`owner.self_person_id`, `person.current_org_id`) added last.
- **Tests**: `upgrade head → downgrade base → upgrade head`; unique constraints asserted: `(source_connection_id, external_id)`, `(owner_id, source, source_key)`, `(kind, normalized_value, owner_id)`; every owned table has `owner_id NOT NULL`.
- **Verify**: `cd backend && alembic upgrade head && alembic downgrade base && alembic upgrade head`
- **Done**: opportunity tables intentionally deferred to T1.4; merge tables to T4.1.

### T0.5 Secret store + owner auth
- **Trace**: FR-14.1, FR-14.3, NFR-2, api.md `POST /api/auth/session`
- **Files**: `backend/app/infra/secrets/base.py`, `backend/app/infra/secrets/aes.py`, `backend/app/api/auth.py`, `backend/app/api/deps.py`
- **Deps**: T0.4
- **Tests**: AES-256-GCM roundtrip, wrong key fails, `repr()` leaks nothing; protected route 401 without token; cookie secure/HTTP-only/same-site.
- **Verify**: `pytest backend/tests/test_auth.py backend/tests/test_secret_store.py -q`
- **Done**: `get_current_owner` injects `owner_id` server-side on every route; tokens only in `SecretStore` behind `auth_ref`.

### T0.6 Health + preflight skeleton
- **Trace**: NFR-3, NFR-5, SC-10, api.md `/api/health/deps`
- **Files**: `backend/app/api/health.py`, `backend/app/services/preflight.py`
- **Deps**: T0.5
- **Tests**: each dependency failure surfaces independently; response never contains secrets.
- **Done**: reports PostgreSQL + Redis now; each later milestone appends its own dependency check to the same registry.

### T0.7 Login + app shell
- **Trace**: FR-14.1, BRANDBOOK.md §4
- **Files**: `frontend/lib/auth.ts`, `frontend/app/login/page.tsx`, `frontend/components/AppShell.tsx`, `frontend/components/PartnerReadout.tsx`
- **Deps**: T0.5, T0.9
- **Shell geometry**: sidebar 240px (rail 64px), top bar 56px, right rail 320px, 8px grid, 1px `--bd` separators, utility screens left-aligned.
- **Partner read-outs**: `PartnerReadout` accepts a live counter or renders `—`; a hard-coded metric fails the test (reconciliation row 9).
- **Tests**: 401 redirects to login; token is not in `localStorage`.
- **Done**: **M0 exit gate** — logging in shows a shell page rendering live owner data from PostgreSQL.

---

## M1 — Main job-search value (Context.dev)

Goal: type a goal, see verified opportunity cards with public citations. No private network yet.

### T1.1 Context credit ledger (gate for every provider call)
- **Trace**: FR-5.8, NFR-4, context-dev.md Budget Enforcement
- **Files**: `backend/app/services/context_credits.py`
- **Deps**: T0.4
- **Tests**: reserve→reconcile atomic via `UNIQUE (category, request_key)`; caps enforced (search 100, brand 200, reserve floor 200); reconciliation uses response `key_metadata.credits_consumed`, not the estimate; exhaustion returns a `budget_exhausted` result, not an exception.
- **Verify**: `pytest backend/tests/test_credit_ledger.py -q`
- **Done**: no provider call is reachable without a reservation; remaining budget appears in `/api/health/deps`.

### T1.2 Migration: credit + market tables
- **Trace**: data-model.md `context_credit_*`, `enrichment_cache`
- **Files**: `backend/migrations/versions/0002_context.py`
- **Deps**: T0.4
- **Done**: `context_credit_budget` seeded with one row, `context_credit_usage`, `enrichment_cache` created.

### T1.3 Web-search adapter (broad discovery)
- **Trace**: FR-5.4, FR-5.5, FR-5.7, context-dev.md `POST /web/search`
- **Files**: `backend/app/connectors/context_dev/web_search.py`
- **Deps**: T1.1, T1.2
- **Tests**: `numResults` clamped 10–30; `country=ae`; explicit `freshness`; `excludeDomains` always contains `linkedin.com`; `markdownOptions.enabled=false` for discovery; retains URL, title, source domain, excerpt, published/discovered/checked timestamps, `query_fingerprint`, provider cache metadata, credits consumed. No fetch of any result URL happens in this module.
- **Verify**: `pytest backend/tests/connectors/test_context_web_search.py -q` (recorded cassette), then one live call
- **Done**: broad discovery returns normalized public evidence at ~1 credit per 10 results.

### T1.4 Migration + persistence for opportunities
- **Trace**: data-model.md `market_search_run`, `opportunity`, `opportunity_evidence`, SC-11
- **Files**: `backend/migrations/versions/0003_opportunity.py`, `backend/app/repositories/opportunity_repo.py`
- **Deps**: T1.3
- **Tests**: duplicate canonical URLs collapse to one active opportunity (`UNIQUE (owner_id, canonical_url)`); evidence versioned by URL + `content_hash`; repeating a search updates `checked_at` without duplicating; identical `query_fingerprint` served from cache with zero credits.
- **Verify**: `pytest backend/tests/test_opportunity_dedup.py -q`
- **Done**: `MarketSearchRun` transitions `pending→running→success|partial|failed`.

### T1.5 Shortlist source verification ← *this was the missing step*
- **Trace**: FR-5.6, SC-11, context-dev.md "Opportunity verification" (5 checks), `markdownOptions.enabled` true only for shortlisted
- **Files**: `backend/app/services/opportunity_verifier.py`
- **Deps**: T1.4
- **Behaviour**: for shortlisted results only, re-request the source with `markdownOptions.enabled=true` (budgeted through T1.1), confirm the URL is accessible at `checked_at`, extract role/company/location-or-remote/open-state, and store `content_hash` + `checked_at`.
- **Tests**: all five checks pass → `verified_open_role`; careers/funding/expansion evidence without a matching role → `hiring_signal`; snippet-only or missing field → `unverified`; previously verified source now unreachable or closed → `stale`. **A result never reaches `verified_open_role` from broad-search snippets alone.** Shortlist size is bounded and ledger-gated.
- **Verify**: `pytest backend/tests/test_verification_states.py -q`
- **Done**: verification status is always backed by a fetched, hashed, timestamped public source.

### T1.6 Opportunities API [P]
- **Trace**: api.md Opportunities
- **Files**: `backend/app/api/opportunities.py`
- **Deps**: T1.5
- **Tests**: `GET` filters by `verification_status`/`saved`/`organization_id`; `PATCH` save/dismiss never mutates provider evidence.
- **Done**: response shapes match api.md.

### T1.8 Design the opportunities screen ← *absent from the mockup export*
- **Trace**: FR-9.4, SC-11, demo.md Steps 4–6, BRANDBOOK.md §5
- **Files**: `mockups/BRANDBOOK.md` (new screen spec section), `frontend/components/OpportunityCard.tsx`
- **Deps**: T0.9
- **Why**: the export ships Ask / Profile / Graph / Signals. None of them presents a verified vacancy with role, organization, verification status, `checked_at` and a public URL, which is the opening move of `demo.md`. Reusing "Ask — answered" would hide the opportunity-first structure.
- **Scope**: compose from existing primitives only — no new visual language. Card = 1px `--bd` on `--lowest`; verification status as a badge (accent border only for `verified_open_role`); `--pos` reserved for opportunity signals; public citation block in mono with source domain and `checked_at`; "no warm path found" as a dashed empty state inside the card.
- **Tests**: all four verification states are visually distinct without relying on colour alone (NFR-6); one filled-orange element per card.
- **Done**: screen spec written into the brandbook so the frontend and any later export stay in sync.

### T1.7 Goal form + opportunity cards UI
- **Trace**: FR-9.1, FR-9.4, US-2, demo.md Step 4
- **Files**: `frontend/app/query/page.tsx`, `frontend/components/GoalForm.tsx`, `frontend/components/OpportunityCard.tsx`, `frontend/components/VerificationBadge.tsx`, `frontend/components/SearchProgress.tsx`
- **Deps**: T1.6, T0.7, T1.8
- **Tests**: badge text distinguishes all four states; each card shows its public URL, source domain and `checked_at`; empty state explains what is missing rather than showing zero cards silently; `SearchProgress` uses `sbpulse`, never a shimmering skeleton.
- **Verify**: `cd frontend && npm run build`, then run the Dubai PM goal live
- **Done**: **M1 exit gate** — a judge types the goal and sees real, verified, cited vacancies. This alone is a demoable product.

---

## M2 — Second Brain differentiation (Convex + warm paths)

Goal: the same opportunities gain warm paths from private evidence, against a prepared corpus.

### T2.1 Convex schema + functions
- **Trace**: FR-8.1, FR-8.3, FR-8.6, SC-4
- **Files**: `convex/schema.ts`, `convex/chunks.ts` (`upsertBatch`, `tombstoneInteraction`, `search`, `fetchResults`)
- **Deps**: T0.1
- **Tests**: vector index is 1536 dims; `owner_scope` composite filter field present (spike fallback for AND-composition); tombstoned docs excluded from `search`.
- **Verify**: `cd convex && npx tsc --noEmit && npx convex deploy`
- **Done**: every chunk carries owner/interaction/person IDs, source, occurred time, text hash, locator, model/version, vector.

### T2.2 Synthetic corpus as a LinkedIn-format archive [P]
- **Trace**: FR-13.5, FR-17.3, SC-2, SC-3
- **Files**: `backend/scripts/generate_synthetic_archive.py`, `backend/tests/fixtures/synthetic_export/{messages,Invitations,Profile,Positions,Company Follows,Skills,Email Addresses,PhoneNumbers}.csv`
- **Deps**: T0.4
- **Approach**: generate the demo corpus **in the exact schema of the real LinkedIn export** (headers and formats verified in T2.2b) rather than as bespoke JSON seeds. One import code path serves both the demo and any real archive, so nothing on the critical path is exercised only by synthetic-specific code.
- **Must reproduce faithfully**: quoted embedded newlines inside `CONTENT`; the `%Y-%m-%d %H:%M:%S UTC` format in `messages.csv` versus `%m/%d/%y, %I:%M %p` in `Invitations.csv`; a realistic content-length distribution (median ≈70 chars, a few over 3000); some rows with empty `CONTENT`; both `INBOX` and `ARCHIVE` folders; outgoing-dominated invitations with almost no message text; **no `Connections.csv`**. A generator that emits clean, uniform CSV would let a broken parser pass.
- **Cast**: `BRANDBOOK.md` §9 verbatim (Alex Ivanov as owner, Marta, Sergey Lapin, John, Daniel Ruiz, plus cold nodes) so seeded data matches every mockup frame — names, roles and dates must not drift. **Exception**: Daniel Ruiz is re-sourced from Telegram to WhatsApp or Gmail (reconciliation row 7). Avatars come from `mockups/design/avatars/`.
- **Volume**: ≥10 people, ≥30 identities, and enough crypto/product/Dubai conversation to make ranking meaningful — several hundred messages, not a dozen.
- **Tests**: the generated archive parses through the T2.2b importer with zero warnings; regenerating with a fixed seed is byte-identical; loading is idempotent.
- **Done**: this is the **only** corpus used on stage. Every synthetic person is written with `data_origin='synthetic'`.

### T2.2b LinkedIn export importer (file-based, no scraping)
- **Trace**: FR-1.1, FR-1.3, FR-1.5, FR-6.1, FR-6.2, FR-8.2, FR-13.1, FR-13.5, NFR-2; spec.md "a future export-file importer is preferred over collecting LinkedIn passwords"
- **Files**: `backend/app/connectors/linkedin_export/{importer,parse,normalize}.py`, `backend/app/api/imports.py`, `frontend/app/settings/imports/page.tsx`
- **Deps**: T2.3, T2.4 (needs the identity matcher and the indexing pipeline)
- **Why this is in P0**: it is the cheapest possible connector — no OAuth, no webhooks, no rate limits, no cursor — and it is a genuine ingestion path rather than a fixture loader, so the demo corpus arrives the same way a real user's data would. **Zero scraping and zero credentials**, so FR-5.7 is untouched: LinkedIn is a source the owner exports from, never a site the product logs into.
- **Primary fixture is the synthetic archive from T2.2.** The real archive is an optional, developer-local robustness check (`--archive` pointing outside the repo) that validates the parser at real volume and messiness. The demo never depends on it.

#### Verified archive shape (`Basic_LinkedInDataExport`, parsed 2026-08-30)

The real archive was parsed once to establish the schema. These are the numbers the synthetic generator must imitate structurally:

| File | Parsed rows | Role in the import |
|---|---|---|
| `messages.csv` | **2076** rows / **714** conversations / **351** distinct sender profile URLs | Primary interaction + embedding corpus |
| `Invitations.csv` | 1579 (1517 outgoing / 62 incoming, **1** carrying message text) | Weak identity hints only — see below |
| `Positions.csv` | 6 | The **owner's** own employment history, not contacts' |
| `Company Follows.csv` | 193 | Owner interest signal for goal parsing |
| `Skills.csv` | 58 | Owner profile enrichment |
| `Profile.csv`, `Email Addresses.csv`, `PhoneNumbers.csv` | 1 each | Owner identity, seeds `owner.self_person_id` |
| `Recommendations_Received/Given.csv` | 2 each | Optional relationship evidence with named counterparties |
| `Ad_Targeting.csv`, `Learning.csv`, `Rich_Media.csv`, `Receipts_v2.csv`, `SavedJobAlerts.csv`, `*_messages.csv` | — | **Not imported.** No relationship value, and ad-targeting data is sensitive. |

**`Connections.csv` is absent from the Basic export.** There is no contact list, no `Connected On` date, and no company/title per contact. The LinkedIn graph must therefore be derived from message reciprocity, not from a connections file. Do not write code that expects `Connections.csv`; treat it as an optional file if a Full export appears later.

#### Mapping

| Archive field | Canonical target |
|---|---|
| `CONVERSATION ID` | `conversation.external_id`, `type='linkedin_thread'` |
| `SENDER PROFILE URL`, `RECIPIENT PROFILE URLS` | `person_identity.kind='linkedin_url'`, canonicalized — the **high-trust deterministic identifier** of FR-6.2 |
| `FROM` / `TO` | `interaction_participant.source_address` + `role` |
| `DATE` (`2026-08-30 07:37:53 UTC`) | `interaction_event.occurred_at` |
| `SUBJECT` (only 22 rows populated) | `interaction_event.subject`, nullable |
| `CONTENT` | `interaction_event.body_text` → chunked by T2.4 |
| `FOLDER` (`INBOX` 1992 / `ARCHIVE` 73 / empty 11) | `metadata.folder` |
| direction | derived by comparing `SENDER PROFILE URL` to the owner's own profile URL from `Profile.csv` |
| `ATTACHMENTS` | metadata only, never fetched |

- **Idempotency**: `external_id = sha256(conversation_id + date + sender_url + content_hash)`. The archive supplies no per-message ID, so the key must be deterministic and content-derived; re-importing the same archive is a no-op, and a re-export with edited content produces an audited `content_version` bump (FR-1.5).

#### Required parser behaviour (tests)

1. **Use a real CSV parser with a raised field limit.** `CONTENT` contains embedded newlines: `wc -l messages.csv` reports 6672 while the file holds 2076 records. A line-splitting importer silently corrupts the corpus. Assert parsed row count == 2076 on the fixture.
2. **Two different date formats.** `messages.csv` uses `%Y-%m-%d %H:%M:%S UTC`; `Invitations.csv` uses `%m/%d/%y, %I:%M %p` with no timezone. Parse them separately; never apply one format to both. Invitation timestamps are stored as date-only when the zone is unknown.
3. **217 rows have empty `CONTENT`.** They are persisted as interactions but **skipped for embedding** — an empty chunk must never reach Convex.
4. **Invitations do not create people.** 1517 outgoing invitations with 1518 distinct invitee URLs and exactly one message body are not relationships. Importing them as `Person` records floods the directory with 1518 non-contacts and destroys ranking. They may only (a) register a `linkedin_url` identity hint that an existing person can match against, and (b) contribute a `weak` edge when a message thread with the same URL also exists. Assert the importer creates **zero** new people from `Invitations.csv` alone.
5. **Content-length distribution is short** (median 72 chars, max 3545). Chunking must not pad or merge across conversations; a 72-char message is one chunk.
6. `Profile.csv` + `Email Addresses.csv` + `PhoneNumbers.csv` seed the owner's own identities so direction detection and self-person linkage work.

- **Verify**: `python -m backend.scripts.import_linkedin --archive <path> --dry-run` prints per-file counts and proposed identity matches without writing. Against the synthetic archive: expected counts match and 0 people come from invitations. Against the real archive (optional): 2076 interactions, 714 conversations, 0 people from invitations.
- **Done**: imported messages are searchable through Convex and produce warm paths, with LinkedIn provenance distinguishable from Gmail/WhatsApp in the UI.

### T2.2c Data-origin guard
- **Trace**: FR-13.1, FR-13.5, FR-17.10, NFR-2
- **Files**: `backend/migrations/versions/0006_data_origin.py`, `backend/app/services/import_guard.py`
- **Deps**: T2.2b
- **Why it stays even with synthetic data**: the real archive still exists on a developer machine and the importer accepts any path. The risk is not the design, it is an accidental `--archive ~/Downloads/...` before a rehearsal. FR-13.5 forbids unrelated contacts' communications reaching the demo, so the guard is a cheap interlock rather than the pseudonymization engine previously planned.
- **Scope**: `person.data_origin` and `interaction_event.data_origin ∈ {synthetic, real_import, live_connector}`, set at write time. With `DEMO_MODE=true` the API refuses to serve `real_import` records and the import endpoint rejects an archive not marked synthetic.
- **Tests**: importing the synthetic archive yields only `synthetic` rows; a `real_import` row is invisible to every API response under `DEMO_MODE=true`; the flag never mutates stored data.
- **Done**: no real contact can reach the stage by accident. Archives stay git-ignored and uncommitted.

### T2.3 Deterministic identity normalizer + matcher
- **Trace**: FR-6.1, FR-6.2, SC-2, US-5
- **Files**: `backend/app/domain/identity/normalize.py`, `backend/app/domain/identity/matcher.py`
- **Deps**: T2.2
- **Tests**: email lowercase, phone E.164, canonical profile URL, WhatsApp JID/LID retained with raw value + source; exact verified email / normalized personal phone / stable profile URL auto-link at 100% precision on the labelled set; role addresses, shared phones, name+company similarity **never** auto-merge.
- **Verify**: `pytest backend/tests/test_deterministic_precision.py -q`
- **Done**: same person across two source connections becomes one `Person` with both identity rows visible (US-5 satisfied without a separate multi-account task).

### T2.4 Chunking + outbox indexing worker
- **Trace**: FR-8.2, FR-8.4, FR-8.5, NFR-3
- **Files**: `backend/app/services/chunking.py`, `backend/app/workers/outbox.py`, `backend/app/infra/convex_client.py`, `backend/app/infra/embeddings/openrouter.py`
- **Deps**: T2.1, T2.2
- **Tests**: `chunk_key = sha256(interaction_id:content_version:ordinal)` is stable; splits on message/paragraph boundaries; `FOR UPDATE SKIP LOCKED` prevents double processing; interaction save succeeds before indexing; re-indexing the same interaction yields **zero duplicate active chunks**; `embedding_version` recorded on every chunk.
- **Verify**: `celery -A app.workers worker -l warning` + `pytest backend/tests/test_outbox.py -q`
- **Done**: OpenRouter `openai/text-embedding-3-small` (1536) batched with data-collection denial requested.

### T2.5 Deletion: tombstone + canonical re-check
- **Trace**: FR-8.6, FR-13.4, US-8, SC-4, SC-9
- **Files**: `backend/app/services/deletion_service.py`, `backend/app/services/query/canonical_filter.py`
- **Deps**: T2.4
- **Behaviour**: delete sets `is_deleted=true` and enqueues a Convex tombstone **and** every vector result is re-checked against PostgreSQL before use. A deleted interaction is dropped from results even if Convex is unreachable and the tombstone has not been applied.
- **Tests**: delete → immediately unretrievable with the Convex tombstone stubbed as failing; disconnect with `delete_data=true` removes source-only records while a person supported by another source survives.
- **Verify**: `pytest backend/tests/test_tombstone_immediate.py backend/tests/test_source_deletion_scope.py -q`
- **Done**: immediacy comes from the canonical re-check, not from asynchronous delivery.

### T2.6 Goal parser
- **Trace**: FR-9.1, US-2
- **Files**: `backend/app/services/query/goal_parser.py`, `backend/app/infra/llm/openrouter.py`
- **Deps**: T0.5
- **Tests**: Dubai crypto PM question → role, related roles, industry, location, action; parsed goal is returned for owner correction before any search runs.
- **Done**: ≤80 lines/function; **no dependency on identity or merge subsystems**.

### T2.7 Organization resolver
- **Trace**: FR-7.5, FR-9.2
- **Files**: `backend/app/services/query/org_resolver.py`, `backend/app/services/organization_service.py`
- **Deps**: T1.5, T2.3
- **Tests**: normalized-domain match first; ambiguous matches are surfaced for review, never asserted; resolution succeeds **without** any brand enrichment.
- **Done**: resolution is a prerequisite for brand enrichment, not the reverse.

### T2.8 Brand enrichment (optional layer) [P]
- **Trace**: FR-5.1, FR-5.2, FR-5.3, FR-9.5
- **Files**: `backend/app/connectors/context_dev/brand.py`
- **Deps**: T1.1, T2.7
- **Tests**: `NOT_FOUND` is a terminal success; 429 → bounded backoff honouring `Retry-After`; hits and misses cached ≥24h; free-email domains skipped without a connector error; brand fields stored with provider provenance and flagged `external_enrichment`, never usable as vacancy or relationship evidence; unverified person fields never overwritten.
- **Done**: called only for organizations already resolved in T2.7, one domain at a time.

### T2.9 Person evidence aggregator
- **Trace**: FR-8.7, FR-9.2, SC-4
- **Files**: `backend/app/services/query/person_aggregator.py`
- **Deps**: T2.4, T2.5, T2.7
- **Tests**: Convex chunks grouped by `person_ids`; repeated evidence from one interaction capped; vector scores feed candidate scoring, not only prompt text; deleted interactions excluded via T2.5.
- **Done**: every evaluated query retrieves and uses Convex chunks.

### T2.10 Relationship graph + warm paths
- **Trace**: FR-7.1, FR-7.2, FR-7.3, FR-7.5, SC-11
- **Files**: `backend/app/services/relationship_service.py`, `backend/app/services/query/graph.py`, `backend/migrations/versions/0004_opportunity_paths.py`
- **Deps**: T2.9
- **Tests**: strength exposes recency/frequency/channel_diversity/manual_adjust and is labelled advisory; `active|cold|dormant` from the configurable 90-day threshold with manual override; traversal opportunity→organization→person/introducer→interaction returns **only** evidence-backed paths; shared employment alone is labelled suggestive, never proof; `opportunity_person_path` persisted with rationale.
- **Verify**: `pytest backend/tests/test_warm_path_evidence.py -q`
- **Done**: an opportunity with no path returns `warm_paths: []` and stays visible — never a fabricated contact.

---

## M3 — Action (combined answer + draft)

### T3.1 Opportunity-first orchestrator
- **Trace**: FR-9.1, FR-9.2, FR-9.6, SC-1, SC-11, demo.md Steps 4–6
- **Files**: `backend/app/services/query/orchestrator.py`, `backend/app/api/query.py`
- **Deps**: T2.6, T1.5, T2.7, T2.9, T2.10, T3.2, T3.3
- **Invariants tested (behaviour, not call order)**:
  1. the response lists `opportunities` before any network section, per api.md;
  2. every `warm_path` attached to an opportunity references an organization resolved from that opportunity's public evidence;
  3. no `warm_path` exists for an opportunity absent from the market-search result set;
  4. removing all Context.dev results yields zero opportunity-attached paths (network-only fallback instead);
  5. `evidence_quality ∈ {sufficient, partial, insufficient}` is consistent with the evidence actually present.
- **Explicitly allowed**: goal-level Convex retrieval may run concurrently with market search; only *opportunity-specific* retrieval depends on resolution. No test asserts client invocation order.
- **Verify**: `curl -sX POST localhost:8000/api/query -d '{"question":"…Product Manager… crypto… Dubai…"}' -H 'content-type: application/json' | jq '.answer.opportunities'`
- **Done**: p95 <30s or a visible partial result while bounded verification continues.

### T3.2 Ranking with exposed factors [P]
- **Trace**: FR-9.2, FR-9.3, FR-9.4
- **Files**: `backend/app/services/query/ranking.py`
- **Deps**: T2.10, T1.5
- **Tests**: opportunities ranked by goal fit + evidence quality/freshness + org resolution + warm-path quality; people by semantic relevance + path + strength + recency; principal factors present in the response.
- **Done**: no opaque-score-only output.

### T3.3 Synthesis + citations
- **Trace**: FR-9.5, FR-9.6, FR-11.4, SC-3
- **Files**: `backend/app/services/query/synthesis.py`, `backend/app/services/query/citations.py`
- **Deps**: T3.2
- **Tests**: public and private evidence never share one citation list; every relationship claim carries a private interaction + locator; every open-role claim carries a URL + source domain + `checked_at` from the current run; an unsupported claim degrades to partial/no-result; a deleted source renders the citation unavailable rather than fabricated; brand facts labelled `external_enrichment`.
- **Verify**: `pytest backend/tests/test_grounding.py -q` over the 5 predefined questions
- **Done**: SC-3 thresholds met on the labelled set.

### T3.4 Degraded query paths [P]
- **Trace**: FR-9.6, US-9, SC-8, api.md partial responses
- **Files**: `backend/app/services/query/degraded.py`
- **Deps**: T3.1
- **Tests**: Context.dev failure → `opportunities: []` + `network_candidates` + `degraded_components: ["context_dev_search"]`; Convex failure → opportunities only + `["convex"]`; both fail → `insufficient` with an explanation of what is missing; ingestion stays available in every case.
- **Done**: cached or unverified results are never presented as current vacancies.

### T3.5 Relationship-grounded draft
- **Trace**: FR-9.7, FR-9.8, SC-1, api.md `POST /api/people/{person_id}/draft`
- **Files**: `backend/app/api/drafts.py`, `backend/app/services/draft_service.py`, `backend/app/domain/ports.py`
- **Deps**: T3.3, T1.6
- **Tests (behavioural)**: response always has `send_supported: false`, `apply_supported: false`, `allowed_actions = [edit, copy, open_external_client, create_reminder, save_opportunity]`; `action: "send"` or `"apply"` → 400; a spy on every registered outbound port records **zero** calls across the whole draft flow; the draft cites both a private interaction and the opportunity's public URL.
- **Verify**: `pytest backend/tests/test_draft_no_send.py -q`
- **Done**: no outbound port is invoked; the assertion is on behaviour, not on module imports.

### T3.6 Follow-ups / reminders [P]
- **Trace**: FR-10.1, FR-10.5, US-7, api.md `/api/followups`
- **Files**: `backend/app/api/followups.py`, `backend/app/services/followup_service.py`
- **Deps**: T0.4
- **Tests**: create/edit/complete/skip/reopen; dashboard sorted by overdue/due date then priority with provenance; `UNIQUE (owner_id, source, source_key)` makes creation idempotent (reused by T4.3).
- **Done**: a draft reminder routes through `POST /api/followups`.

### T3.7 People/interactions read APIs [P]
- **Trace**: FR-11.1, FR-11.2, FR-11.4, NFR-1, api.md People/Interactions
- **Files**: `backend/app/api/people.py`, `backend/app/api/interactions.py`
- **Deps**: T2.10, T2.5
- **Tests**: directory search/filter by tag/status; profile returns identities, employments, relationship components, timeline, documents, follow-ups, source badges; a multi-participant interaction appears on every profile without duplicating the canonical event; manual override beats sync value and is provenance-tagged; p95 <2s over 20 warm runs.
- **Done**: response shapes match api.md.

### T3.8 Warm-path + citation UI
- **Trace**: FR-9.3, FR-9.5, US-2, demo.md Steps 5–6, BRANDBOOK.md §5 Graph
- **Files**: `frontend/components/WarmPath.tsx`, `frontend/components/RelationshipGraph.tsx`, `frontend/components/CitationBlock.tsx`, `frontend/components/DraftPanel.tsx`, `frontend/app/query/page.tsx`
- **Deps**: T3.1, T3.4, T3.5, T3.6, T1.7
- **Graph rules** (from `05-graph-dark.png`): nodes sized by relationship strength with the avatar inside, orange ring on path members, white ring on the you-node, 1px `--bd` edges, introduction path as a dashed orange edge using `sbdash`. Cold relationships use `--idle`, never orange.
- **Tests**: public and private citations render in **separate** labelled blocks; "no warm path found" renders explicitly; degraded banner appears for each `degraded_components` value; there is no send or apply control in the DOM; draft is editable with copy and reminder actions; the full flow is keyboard-navigable with visible focus and WCAG AA contrast.
- **Verify**: `cd frontend && npm run build && npm run lint`, then walk the Dubai PM flow
- **Done**: **M3 exit gate** — the entire `demo.md` Pipeline B narrative works against the prepared corpus.

### T3.9 People directory + profile UI [P]
- **Trace**: FR-11.1–FR-11.4, US-1
- **Files**: `frontend/app/people/page.tsx`, `frontend/app/people/[id]/page.tsx`
- **Deps**: T3.7
- **Done**: cross-source timeline with source badges, identities, relationship explanation, document links; citation deep-links open and highlight the cited record.

---

## M4 — Real ingestion pipelines

Only start here once M3 is green. Each connector is independently demoable and independently cuttable.

### T4.1 Connector framework + contract suite
- **Trace**: FR-1.1–FR-1.5, FR-12.1, FR-12.2, FR-12.5, SC-7
- **Files**: `backend/app/connectors/base.py`, `registry.py`, `normalize.py`, `errors.py`, `backend/app/services/sync_service.py`, `backend/tests/connectors/contract.py`
- **Deps**: T2.3
- **Tests**: `SourceConnector` / `OAuthConnector` / `WebhookReceiver` split (SOLID-I); source types are extensible strings resolved by the registry; every artifact carries required provenance; replay with an equal content hash is a no-op and a changed hash bumps `content_version`; one shared `CursorInvalidated` covers Gmail 404 and Calendar 410 with a **bounded** resync; failure isolation and disconnect covered. The parameterized suite runs against an in-repo `FakeConnector` fixture — **no Outlook connector is built**.
- **Verify**: `pytest backend/tests/connectors -q`
- **Done**: adding a connector needs one registry line and zero core edits; SC-7 evidenced by the fake connector passing the suite unchanged.

### T4.2 Google: OAuth + Gmail + Calendar + Drive
- **Trace**: FR-2.1–FR-2.7, US-1, US-5, api.md connections
- **Files**: `backend/app/connectors/google/{oauth,gmail,calendar,drive,tokens}.py`, `backend/app/api/connections.py`
- **Deps**: T4.1
- **Tests**: state mismatch → 400; exact redirect URI; only `gmail.readonly`, `calendar.readonly`, `drive.metadata.readonly`; Gmail initial `q=after:<90d>` bounded then `history.list` delta with `historyId` cursor; Calendar `syncToken` delta, 410 → bounded resync; Drive `sharedWithMe` metadata-only with manual NDA→person link; `invalid_grant` → `reauth_required` with data and cursor preserved.
- **Verify**: live OAuth roundtrip, then a 100-message delta in <2 min
- **Done**: no send/modify scope is reachable.

### T4.3 Collabute: OAuth + MCP + meeting → follow-up
- **Trace**: FR-4.1–FR-4.8, US-3, SC-5
- **Files**: `backend/app/connectors/collabute/{oauth,mcp_client,normalize,limits}.py`, `specs/001-second-brain-crm/contracts/collabute-tools-list.fixture.json`
- **Deps**: T4.1, T3.6
- **Tests (default CI)**: adapter validated against the **committed fixture**; meeting ID/title/time, participants, summary, decisions, action items mapped with optional-field tolerance; two consecutive syncs → exactly one follow-up per action item (`source_key` = stable Collabute ID else deterministic content hash); refresh at 80% `expires_in`; 401/403 → `needs_reauth` with cursor preserved; 429 honours `Retry-After`; 60 rpm bucket.
- **Live drift check (separate job, not default CI)**: `pytest -m live_contract` compares live `tools/list` against the fixture and is also invoked by demo preflight. Default CI needs no OAuth secrets.
- **Verify**: `python -m backend.scripts.capture_collabute_tools` once after the first human OAuth, then `pytest backend/tests/contracts -q`
- **Done**: PKCE + human AuthKit login never automated; `Mcp-Session-Id` behaviour recorded in `contracts/collabute-mcp.md`; session closed on success and on error.

### T4.4 WhatsApp: Evolution infra + REST + webhook
- **Trace**: FR-3.1–FR-3.12, US-4, SC-6, NFR-2
- **Files**: `docker/evolution/*`, `docker/evolution/patches/sanitize-logs.patch`, `backend/app/connectors/whatsapp/{rest,qr,normalize}.py`, `backend/app/api/webhooks.py`, `scripts/check_logs.sh`
- **Deps**: T4.1
- **Tests**: pinned 2.3.7 / commit `fa09d37…`; invalid secret → 401, wrong instance → 404, oversized payload → 413; **3× replay of one `key.id` → exactly one `interaction_event`**; echoed `apikey` stripped before persistence and logging; 200 only after durable dedup+enqueue; `MESSAGES_SET` batches until `isLatest=true` with monotonic progress; `MESSAGES_UPSERT` normalizes `key.id`, `remoteJid`, `remoteJidAlt`, participant, `fromMe`, timestamp, type, text/caption, quoted ref; group keeps group + participant; `@lid` stored as identity, never coerced to a phone; media metadata only; QR never logged and rotation is recoverable.
- **Verify**: `docker compose logs evolution-api | ./scripts/check_logs.sh`; live message visible in <3s p95
- **Done**: no send path exists anywhere in the module.

### T4.5 Connections + data-controls UI [P]
- **Trace**: FR-13.1, FR-13.2, FR-3.3, US-4, US-8
- **Files**: `frontend/app/settings/connections/page.tsx`, `frontend/app/settings/data/page.tsx`
- **Deps**: T4.2, T4.4, T4.3, T2.5
- **Done**: OAuth redirect, QR render + rotation, sync progress with processed/skipped/error counts, status badges, consent disclosure before first sync, pause/resume/disconnect/delete.

### T4.6 Merge review (deterministic-first) [P]
- **Trace**: FR-6.3–FR-6.5, US-6, SC-2
- **Files**: `backend/migrations/versions/0005_merge.py`, `backend/app/services/merge_service.py`, `backend/app/api/merges.py`, `frontend/app/merges/page.tsx`
- **Deps**: T4.2
- **Tests**: an AI proposal always lands as `MergeCandidate(status='pending')` and never auto-merges regardless of reported confidence, stored as a band not a probability; accept writes a `MergeOperation` reassignment ledger; undo restores every reassigned record; source identities and raw snapshots immutable.
- **Verify**: `pytest backend/tests/test_merge_undo.py -q`
- **Done**: one prepared ambiguous match is reviewable and reversible for Pipeline A.

---

## M5 — Deployment + demo hardening

### T5.1 Production deployment ← *this was missing entirely*
- **Trace**: SC-10, NFR-2
- **Files**: `docker/Dockerfile.backend`, `docker/Dockerfile.frontend`, `deploy/README.md`, `.env.production.example`
- **Deps**: T3.8
- **Scope**: managed PostgreSQL + Redis; backend and frontend deployed behind HTTPS; CORS allowlist and cookie `Domain`/`SameSite` set for the real origin; production callback URIs registered for Google and Collabute; Convex production deployment URL; secrets injected from the platform, never baked into images.
- **Tests**: `/api/health/deps` green on the deployed URL; login and the Dubai PM query work from a clean browser profile.
- **Verify**: `curl -sf https://<domain>/api/health/deps | jq`
- **Done**: no dependency on a developer's localhost.

### T5.2 Evolution secure tunnel [P]
- **Trace**: Assumptions (Evolution reachable only through an authenticated HTTPS route), FR-3.1
- **Files**: `deploy/evolution-tunnel.md`
- **Deps**: T5.1, T4.4
- **Done**: the deployed backend reaches self-hosted Evolution over an authenticated HTTPS tunnel; the webhook URL registered with Evolution is the public backend route; secret rotated for production.

### T5.3 Preflight completion + disclosed fallback
- **Trace**: NFR-3, FR-16 fallback clause
- **Files**: `backend/app/services/preflight.py`, `scripts/snapshot_demo_data.py`
- **Deps**: T5.1, T4.3
- **Tests**: preflight verifies PostgreSQL, Redis, Convex, OpenRouter, Evolution, Google credentials/scopes, Collabute auth + live `tools/list`, `context_dev.credits_remaining ≥ 200`, and a Collabute meeting newer than 7 days.
- **Done**: the fallback snapshot is real connector output, clearly disclosed in the UI; fabricated responses are impossible to present as live.

### T5.4 Demo scripts
- **Trace**: FR-16, SC-1, demo.md
- **Files**: `scripts/demo_pipeline_a.md`, `scripts/demo_pipeline_b.md`
- **Deps**: T4.5, T4.6, T3.8, T5.3
- **Done**: Pipeline A = preflight → Google OAuth → bounded Gmail/Calendar/Drive → Evolution QR → history progress → live message → deterministic link + one reviewed merge → unified profile → PG/Convex parity → tombstone check. Pipeline B = Collabute OAuth + tool discovery → meeting → one cited follow-up → Dubai PM goal → verified opportunities with public citations → resolved orgs → warm paths with private citations → one opportunity with no warm path → draft copied/saved/converted to a reminder, nothing sent.

### T5.5 Three rehearsals + degradation drill
- **Trace**: SC-8
- **Files**: `scripts/rehearsal_log.md`
- **Deps**: T5.4
- **Verify**: both pipelines three consecutive times; disable Convex, then Context.dev, then one source.
- **Done**: 3/3 logged; every degradation shows a clear state with zero source-data loss; recovery drains the indexing backlog.

---

## Deferred (explicitly not P0)

Cut from the previous task list. Each is defensible post-hackathon work, none is needed for the `demo.md` narrative.

| Dropped | Why it is safe to drop | Replaced by |
|---|---|---|
| Outlook fixture connector | Outlook is post-hackathon; the value was architectural proof | `FakeConnector` in T4.1 still evidences SC-7 |
| Online reindex / version migration | One embedding version suffices for a bounded corpus | `embedding_version` recorded in T2.4 |
| Purge cron | Tombstone + canonical re-check already prevent serving deleted content | T2.5 |
| Memory fact extraction | Interactions and Collabute action items give enough context | — |
| Calendar↔Collabute deduplication | Show Collabute as a distinct source with its own badge | T4.3 badge |
| Cold-relationship suggestion worker | Irrelevant to the job-search flow | manual + Collabute follow-ups in T3.6/T4.3 |
| Dedicated multi-account dedup task | Falls out of deterministic matching | T2.3 covers US-5 |
| Standalone AI-merge task on the critical path | Deterministic matching plus one prepared ambiguous case is enough | folded into T4.6, off the critical path |

If schedule pressure returns, cut in this order: **T4.6 → T4.4 → T4.2 → T3.9 → T4.3**. Never cut T1.3, T1.5, T2.4, T2.9, T2.10, T3.1, T3.3, T3.5 — they carry the `demo.md` flow, the Convex critical-path requirement, and the grounding guarantees.

---

## Critical path

```text
T0.1 ─── T0.4 ─ T0.5 ─┬─ T0.7               (M0 gate: page reads PostgreSQL)
T0.2 ─ T0.8 ─ T0.9 ───┘
       T1.1 ─ T1.3 ─ T1.4 ─ T1.5 ─ T1.6 ─┬─ T1.7   (M1 gate: verified cited vacancies)
                              T0.9 ─ T1.8 ─┘
       T2.1 ─ T2.4 ─┬─ T2.2b ─ T2.2c ─┐
       T2.2 ─ T2.3 ─┴─ T2.7 ─ T2.9 ───┴─ T2.10
       T3.2 ─ T3.3 ─┬─ T3.1 ─ T3.8                (M3 gate: full demo.md flow)
       T3.5 ────────┘
       T5.1 ─ T5.4 ─ T5.5                          (M5 gate: HTTPS demo, 3 rehearsals)
```

M4 hangs off this chain and is not a prerequisite for any gate before T5.4.

## Traceability

| Requirement | Tasks |
|---|---|
| US-1 | T4.2, T2.3, T4.6, T3.7, T3.9, T5.4 |
| US-2 | T2.6, T3.1, T2.10, T3.2, T3.3, T1.7, T1.8, T3.8 |
| US-3 | T4.3 |
| US-4 | T4.4, T4.5 |
| US-5 | T2.3, T4.2 |
| US-6 | T4.6 |
| US-7 | T3.6, T4.3 |
| US-8 | T2.5, T4.5 |
| US-9 | T3.4, T5.5 |
| FR-1 | T4.1 |
| FR-2 | T4.2 |
| FR-3 | T4.4 |
| FR-4 | T4.3 |
| FR-5 | T1.1, T1.3, T1.4, T1.5, T2.8 |
| FR-6 | T2.3, T4.6, T3.7 |
| FR-7 | T2.10, T2.7 |
| FR-8 | T2.1, T2.4, T2.5, T2.9 |
| FR-9 | T2.6, T3.1–T3.5 |
| FR-10 | T3.6, T4.3 |
| FR-11 | T3.7, T3.9, T0.7 |
| BRANDBOOK reconciliation | T0.8 (rows 2,3,6,8,9), T1.8 (row 10), T2.2 (row 7), T0.2 (row 4) |
| FR-12 | T4.1, T4.2, T4.3, T4.4 |
| FR-13 | T2.5, T4.5 |
| FR-14 | T0.5, T4.2 |
| FR-15 | not tasked (P1) |
| FR-17 | T2.2b, T2.2c |
| FR-16 | T5.3, T5.4 |
| SC-1 | T5.4 |
| SC-2 | T2.3, T4.6 |
| SC-3 | T3.3 |
| SC-4 | T2.1, T2.4, T2.5, T2.9 |
| SC-5 | T4.3 |
| SC-6 | T4.4 |
| SC-7 | T4.1 |
| SC-8 | T3.4, T5.5 |
| SC-9 | T2.5 |
| SC-10 | T5.1, T5.2, T0.6 |
| SC-11 | T1.3, T1.4, T1.5, T2.10 |
