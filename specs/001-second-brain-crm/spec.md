# Feature: Second Brain / Intelligent CRM

## Overview

Second Brain is a personal relationship-memory system that collects evidence from fragmented communication channels, resolves identities, builds a relationship graph, and answers natural-language questions about the user's own network with traceable citations.

The hackathon deliverable is a reusable skeleton plus two real end-to-end demo pipelines. Gmail, Google Calendar/Drive metadata, WhatsApp through Evolution API, Collabute through its Coding Tools MCP endpoint, Context.dev, PostgreSQL, Convex, and OpenRouter are used in the working product rather than shown as disconnected sponsor demos.

PostgreSQL is the canonical store for identities, relationships, source provenance, and workflow state. Convex is a critical-path semantic-memory subsystem: interaction chunks and their metadata are indexed there and retrieved for every network question. OpenRouter generates embeddings and cited answers. The product remains useful for profile browsing and ingestion if semantic indexing or answer generation is temporarily unavailable.

## Scope and Priorities

### P0 — Required for the hackathon demo

- Single CRM owner with authenticated web access.
- Gmail OAuth, one or more Google accounts, Calendar events, and Drive document metadata.
- WhatsApp QR connection, bounded history import, and new-message ingestion through a self-hosted Evolution API instance.
- Collabute OAuth and Streamable HTTP MCP integration for recent meeting context and action items.
- Context.dev organization enrichment for a bounded set of demonstrated companies.
- Identity resolution, reversible merge review, relationship graph, unified profile, and follow-up dashboard.
- Convex semantic indexing, graph-assisted network query, and source citations.
- Two repeatable demo pipelines defined in FR-16.

### P1 — Stretch goals; not part of demo success criteria

- Telegram history through Telethon, including 2FA and encrypted session storage.
- Media text extraction, screenshot upload/OCR, and full-text document indexing.
- Message edit/delete reconciliation and richer group-chat semantics.
- Automated commitment extraction beyond Collabute action items.

### Post-hackathon

LinkedIn, Outlook, X, Instagram, Snapchat, external opportunity discovery, outreach, multi-user tenancy, billing, and commercial operations.

## Users / Personas

### Primary: The Connector

A professional maintaining many relationships across platforms who needs to:

- remember who a person is, how they met, and what happened;
- recover promises, needs, decisions, documents, and pending follow-ups;
- find people relevant to a current job, investment, introduction, or sales goal;
- understand why a recommendation was made and inspect its evidence;
- correct the system when two identities were merged incorrectly.

### Secondary: Hackathon audience

Judges should see one coherent story: fragmented relationship data becomes a trusted profile, meeting actions become follow-ups, and the user's network becomes searchable through evidence-backed questions.

## User Scenarios and Acceptance Scenarios

### US-1 [P0]: Assemble one relationship across sources

**Given** a test person appears in Gmail, WhatsApp, Calendar, Drive metadata, and a recent Collabute meeting, **when** the required syncs complete and an ambiguous merge is approved, **then** the product shows one profile containing a chronological cross-source timeline, organization/role, source badges, linked NDA metadata, meeting evidence, and follow-ups without duplicate interactions.

### US-2 [P0]: Ask who can make an introduction

**Given** at least five contacts have relevant interaction evidence and relationship edges, **when** the owner asks “Who could introduce me to Web3 investors?”, **then** the product returns a ranked list with relationship context, last contact, relevance explanation, suggested next action, and clickable citations for every factual relationship claim. If evidence is insufficient, the answer says so instead of inventing a contact or path.

### US-3 [P0]: Turn a Collabute meeting into relationship memory

**Given** the owner has authorized Collabute and a meeting exists within the accessible history window, **when** the Collabute sync runs, **then** participants, decisions, and action items are normalized into CRM records; each resolvable participant is linked to a profile; and each action item creates at most one follow-up with Collabute provenance.

### US-4 [P0]: Connect and sync WhatsApp safely

**Given** Evolution API is healthy, **when** the owner creates a WhatsApp connection and scans a current QR code, **then** the UI reaches `connected`, displays initial-history progress, imports incoming and outgoing messages, and continues receiving new messages. Replayed webhooks do not create duplicates, and QR expiry or logout results in a recoverable UI state.

### US-5 [P0]: Connect a second Google account

**Given** a person appears in two Google accounts, **when** the second account syncs, **then** exact high-trust identifiers attach its interactions to the existing person while both source connections and original records remain visible.

### US-6 [P0]: Review and reverse a merge

**Given** two provisional people are similar but do not share a high-trust identifier, **when** AI proposes a merge, **then** no automatic merge occurs; the owner can compare evidence, accept or reject the proposal, and later undo an accepted merge without losing original source identities or interactions.

### US-7 [P0]: Manage a follow-up

**Given** a manual request, a Collabute action item, or a cold-relationship rule, **when** a follow-up is created, **then** it appears once in the dashboard with person, reason, provenance, due date when known, and `pending`, `done`, or `skipped` state.

### US-8 [P0]: Disconnect and delete source data

**Given** a source is connected, **when** the owner disconnects it, **then** further synchronization stops and credentials are revoked or destroyed. The owner chooses whether imported records are retained or deleted; deletion also removes derived graph evidence and Convex chunks while preserving unrelated sources.

### US-9 [P0]: Degrade gracefully

**Given** one external source, Convex, or OpenRouter is unavailable, **when** the owner uses the product, **then** unaffected profiles and sources continue working, the failed operation has a visible retryable state, and no acknowledged source event is silently lost.

## Functional Requirements

### FR-1: Source integration contract

- FR-1.1: Each source adapter MUST implement a common `SourceConnector` contract for capabilities, authentication lifecycle, initial sync, incremental sync, normalization, health, and disconnect.
- FR-1.2: Source types MUST be registered through dependency injection and stored as extensible strings rather than requiring changes to a core enum.
- FR-1.3: Every normalized source artifact MUST include `owner_id`, `source_connection_id`, a source-native external ID, applicable occurred/updated timestamps and participants, provenance, and an immutable raw-record reference or sanitized snapshot.
- FR-1.4: Every connector MUST expose `disconnected`, `authorizing`, `connected`, `syncing`, `degraded`, `reauth_required`, and `error` states where applicable.
- FR-1.5: Initial and incremental syncs MUST be independently retryable and idempotent. The canonical uniqueness boundary is `(source_connection_id, external_id)` or a documented source-specific equivalent; a source version/content hash determines whether replay is a no-op or an audited update.
- FR-1.6: Adding an Outlook fixture connector MUST pass the connector contract tests without changing entity resolution, profile, or query code.

### FR-2: Google Workspace

- FR-2.1: The UI MUST support OAuth authorization for multiple Google accounts using state validation, least-privilege scopes, and server-side token exchange.
- FR-2.2: Hackathon scopes are `gmail.readonly`, `calendar.readonly`, and `drive.metadata.readonly`; sending, modifying, and deleting Google data are prohibited.
- FR-2.3: The demo OAuth app MUST run in testing mode with explicit test users; public restricted-scope verification is not a hackathon dependency.
- FR-2.4: Gmail initial sync MUST use a configurable bounded lookback, default 90 days, followed by history-ID delta sync. An expired/invalid history cursor triggers a bounded resync, not an unbounded mailbox import.
- FR-2.5: Gmail normalization MUST retain thread/message IDs, From/To/Cc participant roles, timestamps, subject, plain text, direction, and account provenance. Attachments are metadata-only in P0.
- FR-2.6: Calendar sync MUST retain event ID, title, description, start/end/timezone, organizer, attendees, and cancellation/update state.
- FR-2.7: Drive sync MUST retain file ID, name, MIME type, owner/shared-with metadata, modified time, and source URL. The owner MUST be able to link/unlink metadata such as an NDA to a person manually.

### FR-3: WhatsApp through Evolution API

The integration contract is validated against Evolution API `2.3.7`, source commit `fa09d37892cdbb1d65a250155d293d92230c5b30`. Upgrades require rerunning adapter contract tests.

- FR-3.1: Evolution API MUST run as an isolated service; the CRM connector communicates through its REST and webhook interfaces and never exposes the global `apikey` or per-instance token to the browser.
- FR-3.2: One CRM `SourceConnection` MUST map to one Evolution instance with explicit create, connect, connection-state, logout, and delete lifecycle operations.
- FR-3.3: The UI MUST render the returned QR base64, refresh it after expiry/rotation, show connection state, and offer retry/logout. A QR value MUST never be persisted in application logs.
- FR-3.4: P0 event subscriptions are `QRCODE_UPDATED`, `CONNECTION_UPDATE`, `MESSAGES_SET`, and `MESSAGES_UPSERT`.
- FR-3.5: Initial history MUST enable `syncFullHistory` only for the bounded demo account and consume `MESSAGES_SET` batches until `isLatest=true`; progress MUST be visible in the UI.
- FR-3.6: Live and historical messages MUST normalize `key.id`, `remoteJid`, `remoteJidAlt`, participant identifiers, `fromMe`, timestamp, message type, text/caption, quoted-message reference, and source payload version.
- FR-3.7: Incoming and outgoing messages are distinguished by `key.fromMe`; no CRM message sending is allowed.
- FR-3.8: Webhook authentication MUST be explicitly configured with Evolution’s `jwt_key` Authorization mechanism or an equivalent rotated secret header. The receiver MUST validate the credential, expected instance, timestamp/expiry where available, payload size, and content type before acknowledgement. Any `apikey` echoed in the webhook body is treated as a secret and MUST be discarded before persistence, logging, or downstream processing.
- FR-3.9: The idempotency key MUST derive from the CRM connection/instance plus WhatsApp `key.id`; webhook envelope retries are expected and are not assumed to contain a unique event ID.
- FR-3.10: Group messages MUST identify both the group conversation and actual participant when available. `@lid`/alternate JIDs MUST be retained as identities and not assumed to be phone numbers.
- FR-3.11: P0 stores media metadata/captions only. Raw media, deleted-message reconciliation, reactions, polls, newsletters, and status broadcasts are out of P0.
- FR-3.12: The pinned Evolution build/configuration MUST not emit message bodies, QR values, API keys, or full webhook payloads to logs. Source-level unsanitized `console.log` statements MUST be patched or the build rejected before real data is used.

### FR-4: Collabute Coding Tools MCP

- FR-4.1: Collabute is a mandatory sponsor-critical integration using Streamable HTTP MCP at `https://api.collabute.ai/api/mcp` with human-completed OAuth.
- FR-4.2: The CRM MUST implement the OAuth connect, callback, token refresh/reauthorization, disconnect, and connection-status lifecycle. Agents MUST NOT automate the human AuthKit login step.
- FR-4.3: After authorization, the adapter MUST call MCP capability/tool discovery and bind only to tools returned by the workspace. Tool names and response schemas MUST be captured as a versioned adapter fixture before implementation is considered complete.
- FR-4.4: The P0 read path MUST retrieve at least one recent meeting and normalize meeting ID, title/time, participants, summary, decisions, owners, and action items when those fields are available.
- FR-4.5: Action-item deduplication MUST use stable Collabute workspace/resource/action identifiers or a deterministic content hash when the tool supplies no stable action ID.
- FR-4.6: Collabute evidence MUST remain distinguishable from Google Calendar evidence for the same meeting and be linked rather than duplicated when a stable match exists.
- FR-4.7: OAuth 401/403 states require visible reauthorization; rate limits and temporary failures use bounded exponential backoff and preserve the prior successful sync.
- FR-4.8: For the free-tier demo, the meeting fixture MUST be recent enough for the available context-history window and prepared before demo preflight.

### FR-5: Context.dev organization enrichment

- FR-5.1: Enrichment MUST target an `Organization`, not overwrite unverified person fields, and run only when a normalized work domain is available or the owner explicitly requests it.
- FR-5.2: The adapter uses `POST /brand/retrieve` and stores returned brand title/domain, description, logo, socials, address, and industry classifications with provider provenance and retrieval time.
- FR-5.3: `NOT_FOUND` is a normal terminal result; HTTP 429 uses bounded backoff; successful results and misses are cached for at least 24 hours.
- FR-5.4: The hackathon budget is capped at 50 successful brand retrievals under the assumed 500-credit allocation and current 10-credit successful-call cost. Batch enrichment of the whole network is prohibited.

### FR-6: Identity resolution and merge safety

- FR-6.1: Normalization MUST canonicalize emails, E.164 phones, Telegram usernames, WhatsApp JIDs/LIDs, and profile URLs while retaining the raw value and source.
- FR-6.2: Exact verified email, exact normalized personal phone, or exact stable profile URL MAY auto-link identities. Role addresses, shared phones, names, and company similarity MUST NOT auto-merge people.
- FR-6.3: AI may propose merges using name, organization/role overlap, signatures, co-participants, and context, but AI-only proposals always require owner confirmation in P0; an LLM confidence number is not treated as a calibrated probability.
- FR-6.4: The merge-review UI MUST display conflicting fields, supporting evidence, source identities, and the consequences of the merge.
- FR-6.5: Source identities and raw source snapshots are immutable. Canonical interactions may receive audited source-version updates. Accepted merges create a `MergeOperation` ledger entry so canonical reassignment can be fully reversed.
- FR-6.6: Manual owner edits have precedence over enrichment/sync values but MUST retain field-level provenance and may be explicitly reset.

### FR-7: Relationship graph and memory

- FR-7.1: The graph MUST support person-to-person relationships, person-to-organization employments, interactions with multiple participants, introducer paths, documents, facts, and follow-ups.
- FR-7.2: A relationship strength score MUST expose its recency, frequency, channel-diversity, and explicit-owner-adjustment components; the score is advisory and never presented as objective truth.
- FR-7.3: `active`, `cold`, and `dormant` states MUST be derived from an owner-configurable inactivity threshold, default 90 days, and may be manually overridden.
- FR-7.4: Personal updates, needs, promises, decisions, and interests MAY be stored as `MemoryFact` suggestions only when tied to cited evidence. Sensitive facts are not inferred from absence or protected attributes.
- FR-7.5: Graph traversal for introductions MUST return an evidence-backed path. Shared employment alone may suggest relevance but MUST NOT be stated as proof that an introduction is possible.

### FR-8: Convex semantic memory and RAG

- FR-8.1: PostgreSQL remains canonical; Convex stores searchable semantic chunks plus references needed to fetch canonical records and citations.
- FR-8.2: Every eligible interaction MUST be split into deterministic, bounded chunks preserving message/paragraph boundaries. A chunk key is derived from interaction ID, canonical content version, and ordinal.
- FR-8.3: Every Convex chunk MUST include `owner_id`, `interaction_id`, involved person IDs, source, occurred time, text hash, citation locator, embedding model/version, indexing state, and vector.
- FR-8.4: The default embedding model is `openai/text-embedding-3-small` through OpenRouter with 1536 dimensions. Provider routing MUST request data collection denial where supported. Model or dimension changes require a versioned reindex, never mixed vectors in one index.
- FR-8.5: Index writes MUST use a transactional outbox in PostgreSQL or an equivalent durable handoff. Saving an interaction succeeds before indexing; failed jobs remain retryable and observable.
- FR-8.6: Updates replace stale chunks idempotently. Deletion writes a tombstone immediately, excludes stale chunks from retrieval, and eventually removes them from Convex.
- FR-8.7: Every network query MUST use Convex retrieval in its critical path, with owner/source/time filters where applicable. Vector results MUST contribute to candidate scoring and citations, not merely decorate the final prompt.
- FR-8.8: Convex unavailability MUST not lose source ingestion. The UI marks semantic search degraded until backlog recovery completes.

### FR-9: Natural-language network query

- FR-9.1: The owner enters a goal or question; the query service retrieves semantic evidence from Convex, expands candidate paths through the canonical graph, ranks candidates, and synthesizes an answer through OpenRouter.
- FR-9.2: Default ranking MUST combine semantic relevance, evidence-backed graph path, relationship strength, and recency. The response exposes the principal factors rather than only an opaque score.
- FR-9.3: Each result contains person, current known role, last interaction, relevance reason, relationship/intro path when available, suggested action, confidence band, and citations.
- FR-9.4: Every factual claim about a relationship, meeting, role, promise, or topic MUST cite one or more source records. Context.dev company facts are labeled external enrichment, not relationship evidence.
- FR-9.5: The answer MUST distinguish “known from evidence,” “inferred,” and “unknown,” and MUST prefer an explicit no-result response over unsupported recommendations.
- FR-9.6: The service MUST never send a message or contact anyone as a side effect of a query.

### FR-10: Follow-up intelligence

- FR-10.1: The owner can create, edit, complete, skip, and reopen a follow-up with optional due date/timezone.
- FR-10.2: Collabute action items become idempotent follow-ups with meeting/action citations.
- FR-10.3: Cold-relationship suggestions are generated on a schedule but remain suggestions until accepted or dismissed.
- FR-10.4: Extracted promises without an explicit owner or due date MUST be suggestions, not silently created obligations.
- FR-10.5: The dashboard sorts by overdue/due date, then owner-adjusted priority, and displays provenance.

### FR-11: Unified profiles and navigation

- FR-11.1: The product MUST provide a searchable people directory and a person profile showing canonical identity, identifiers, organizations/roles, relationship status/score explanation, chronological interactions, documents, memory facts, follow-ups, and source provenance.
- FR-11.2: Multi-participant interactions appear on every participant profile without duplicating the canonical event.
- FR-11.3: The profile MUST expose manual edit/reset, merge review/undo, document link/unlink, and source filtering.
- FR-11.4: Citation links MUST open the relevant interaction and highlight or identify the cited message, meeting section, or document metadata.

### FR-12: Sync operations and recovery

- FR-12.1: Each connection exposes last successful sync, cursor/checkpoint, current run, processed/skipped/error counts, retry action, and human-readable error.
- FR-12.2: Sync runs MUST use bounded retries with exponential backoff and jitter; permanent authorization/validation failures are not retried automatically.
- FR-12.3: One source failure MUST not stop other connectors, profile browsing, or already-indexed queries.
- FR-12.4: Webhook acknowledgement occurs only after durable deduplication/enqueue. Long extraction, enrichment, and embedding work runs asynchronously.
- FR-12.5: A failed or restarted worker resumes from durable checkpoints without duplicating canonical records.

### FR-13: Data controls

- FR-13.1: Before first sync, the UI MUST show source, requested scopes/data types, lookback range, third-party processors, and whether content will be sent to OpenRouter, Convex, Context.dev, or Collabute.
- FR-13.2: The owner can pause, resume, disconnect, and delete each source connection.
- FR-13.3: Source deletion MUST remove source-only identities, interactions, documents, facts, follow-ups, merge evidence, and semantic chunks while preserving entities still supported by another source.
- FR-13.4: The owner can delete an individual interaction or person and trigger the same derived-data cleanup.
- FR-13.5: The demo MUST use team-controlled test accounts and synthetic/consented contacts; judges’ or unrelated contacts’ private communications MUST not be imported.

### FR-14: Authentication and authorization

- FR-14.1: All CRM endpoints require an authenticated owner session. OAuth callbacks validate state and exact redirect URI; cookies are secure, HTTP-only, same-site, and protected against CSRF where applicable.
- FR-14.2: Even though P0 is single-owner, every canonical and semantic record MUST carry `owner_id` so cross-owner leakage cannot be introduced accidentally.
- FR-14.3: Connector tokens, Telethon sessions, Evolution keys, Collabute tokens, and OpenRouter/Context.dev keys MUST remain server-side in encrypted secret storage referenced by `auth_ref`, never embedded in ordinary entity JSON.

### FR-15: Optional Telegram stretch connector

- FR-15.1: Telegram is not required for hackathon success and MUST NOT delay either P0 pipeline.
- FR-15.2: If implemented, login supports phone, code, optional 2FA password, encrypted session lifecycle, logout/revocation, incremental checkpoints, and `FLOOD_WAIT`/reauthorization states.
- FR-15.3: Dialog/message IDs, sender, participants, timestamp, direction, edits, and source account are normalized through the same connector contract.

### FR-16: Required demo pipelines

#### Pipeline A — Fragmented identity to unified profile

1. Run dependency preflight.
2. Connect a prepared Google test account through real OAuth.
3. Import bounded Gmail and Calendar data plus NDA Drive metadata.
4. Connect a prepared WhatsApp test account through a current Evolution QR.
5. Consume initial-history progress and at least one live message.
6. Resolve deterministic identities, review one ambiguous merge, and open the unified profile.
7. Show the same canonical interaction references and semantic chunks in the product/Convex diagnostics.

#### Pipeline B — Meeting evidence to network action

1. Connect Collabute through human OAuth and MCP tool discovery.
2. Import one recent meeting with participants, decision, and action item.
3. Resolve a participant and create one cited follow-up.
4. Enrich one participant organization through Context.dev.
5. Ask “Who could introduce me to Web3 investors?”
6. Show Convex retrieval, graph path/ranking factors, a ranked answer, and clickable citations.

A pre-synced snapshot produced by these real connectors MAY be used only as a clearly disclosed fallback after a live external outage; fabricated connector responses MUST NOT be presented as live.

## Non-Functional Requirements

### NFR-1: Performance and freshness

- With the demo corpus, profile and directory views reach usable content in <2 seconds at p95 over 20 warm runs.
- A valid Evolution `MESSAGES_UPSERT` is durably visible in the timeline in <3 seconds at p95; semantic searchability follows in <60 seconds at p95.
- A Gmail delta of 100 text messages is durably normalized in <2 minutes, excluding provider throttling; indexing progress may continue asynchronously.
- A network query returns or times out with a recoverable error in <10 seconds at p95 over 20 prepared evaluation queries.

### NFR-2: Security and privacy

- TLS is required for all non-local traffic. OAuth credentials and connector secrets use authenticated encryption at rest with a key outside the application database and a documented rotation procedure.
- Logs, traces, metrics, and exception reports MUST exclude message bodies, document names where sensitive, QR values, OAuth codes/tokens, API keys, phone/email values, and webhook payloads. Stable salted identifiers may be used for correlation.
- Evolution webhook authentication and replay/deduplication controls follow FR-3.8–FR-3.9.
- Third-party LLM/embedding requests contain only the minimum required chunks and use no-training/data-collection-denial controls where available.
- Backups and local developer fixtures follow the same deletion and secret-handling rules as production data.

### NFR-3: Reliability and consistency

- Source ingestion is at-least-once with application-level idempotency.
- PostgreSQL-to-Convex indexing is eventually consistent, observable, replayable, and protected from serving tombstoned content.
- External failure cannot corrupt the last successful cursor or delete previously imported data.
- Demo preflight checks PostgreSQL, Redis/Celery if used, Convex, OpenRouter, Evolution instance/webhook, Google credentials/scopes, Collabute authorization/tools, and Context.dev budget.

### NFR-4: Capacity and cost

- The design supports 10,000 people and 100,000 interactions for one owner, but hackathon verification uses a documented smaller corpus.
- Every external API integration has a request budget, timeout, concurrency limit, and cost/rate-limit telemetry without payload content.
- Context.dev follows the explicit cap in FR-5.4; embedding and generation usage is recorded per model.

### NFR-5: Observability

- Structured logs include request/run/connection IDs and sanitized error codes.
- Health/readiness endpoints distinguish application health from each external dependency’s status.
- The UI exposes sync and indexing backlogs without requiring shell access.
- Alerts are not required for P0, but failed P0 demo dependencies must be visible during preflight.

### NFR-6: Accessibility and compatibility

- Core connect, profile, merge-review, query, citation, and follow-up flows are keyboard usable with visible focus and text alternatives for status/color.
- Text and interactive controls meet WCAG AA contrast.
- The demo supports current stable Chrome; responsive desktop behavior is required, while a native/mobile app is not.

## Key Entities

| Entity | Required fields and relationships |
|---|---|
| `Owner` | `id`, `display_name`, `email`, `timezone`, optional `location`, optional `current_goal`, `self_person_id`, timestamps |
| `Person` | `id`, `owner_id`, `display_name`, photo, canonical title, manual field overrides with provenance, tags, timestamps |
| `PersonIdentity` | `id`, `person_id`, `source_connection_id`, `kind`, raw/normalized value, verified/primary flags, first/last seen; source identity is never destroyed by merge |
| `Organization` | `id`, `owner_id`, name, domain, enriched fields, field provenance, timestamps |
| `Employment` | `id`, `person_id`, `organization_id`, title, start/end, current flag, evidence source |
| `Conversation` | `id`, `owner_id`, `source_connection_id`, external ID, type, title, timestamps |
| `InteractionEvent` | `id`, `owner_id`, `source_connection_id`, conversation ID, external ID/version, type, direction, occurred time, subject/body, metadata, raw reference, deleted/indexing state |
| `InteractionParticipant` | `interaction_id`, optional `person_id`, optional `identity_id`, source address, role (`sender`, `recipient`, `cc`, `attendee`, `organizer`, `group_member`) |
| `Document` | `id`, `owner_id`, source connection/external ID, name, MIME type, URL, modified time, metadata, provenance; content absent in P0 |
| `DocumentPersonLink` | `document_id`, `person_id`, relationship type, source/manual provenance |
| `Relationship` | `id`, `owner_id`, `person_a_id`, `person_b_id`, type, strength components/score, status, last interaction, manual adjustment, evidence |
| `MemoryFact` | `id`, `owner_id`, `person_id`, type, value, confidence band, status, evidence interaction, valid-from/to |
| `FollowUp` | `id`, `owner_id`, `person_id`, reason, due date/timezone, source, source key, evidence, priority, status, timestamps |
| `MergeCandidate` | `id`, two person IDs, method, evidence, confidence band, status, created/reviewed timestamps |
| `MergeOperation` | `id`, survivor/merged person IDs, reassignment ledger/snapshot, actor, created/reversed timestamps |
| `SourceConnection` | `id`, `owner_id`, source string, external account/instance ID, `auth_ref`, status, capabilities, cursor, last sync/error, timestamps |
| `SyncRun` | `id`, connection ID, mode, checkpoint, status, counts, sanitized error, started/finished timestamps |
| `SemanticChunk` (Convex) | deterministic key, owner/interaction/person IDs, source/time, ordinal, text hash, locator, model/version, vector, tombstone/index timestamps |

### Required constraints

- Unique canonical source artifacts: `(source_connection_id, external_id)`; source version/content hash drives audited updates.
- Unique follow-up source keys when present: `(owner_id, source, source_key)`.
- Every canonical and Convex query is scoped by `owner_id`.
- Interactions and meetings support multiple participants through the join entity.
- Person-to-organization history uses `Employment`; `current_org_id` is not the source of truth.
- Semantic chunks cannot be the sole copy of source text or provenance.

## Edge Cases

- Same name and company but different people: never auto-merge.
- Shared/role email or family/company phone: never auto-merge solely on that value.
- A person changes company or role: preserve employment history and evidence dates.
- One event appears in Calendar and Collabute: link evidence, do not duplicate the meeting timeline item.
- Email has many To/Cc recipients or a meeting/group chat has many participants: retain all roles.
- Evolution retries the same payload or sends history and live copies: deduplicate by connection plus source message ID.
- WhatsApp exposes `@lid` instead of a phone JID: retain alternate identity and defer unsafe phone matching.
- Gmail history cursor expires: bounded recovery sync.
- OAuth token is revoked: mark `reauth_required` without deleting data.
- Convex contains stale chunks after canonical deletion: tombstone filters them immediately and cleanup retries.
- Embedding model changes dimension: create a versioned index/reindex rather than mixing vectors.
- Citation source is deleted: remove/recompute affected answer evidence and show unavailable citation for previously stored query output.
- Context.dev cannot resolve a free-email domain: skip enrichment without treating it as connector failure.
- No useful network evidence exists: return no result and explain what data is missing.
- Demo dependency fails: use unaffected live steps or disclosed pre-synced real data; never silently substitute mocks.

## Success Criteria

### SC-1: Two real pipelines

Both FR-16 pipelines complete against team-controlled accounts. Pipeline A includes a real Google OAuth sync and Evolution QR/message flow. Pipeline B includes a real Collabute MCP retrieval, follow-up creation, Convex retrieval, and cited answer.

### SC-2: Identity quality

On a labeled demo set containing at least 30 source identities mapped to at least 10 real/synthetic people, deterministic auto-links have 100% precision, overall accepted/proposed matches reach at least 90% precision and 80% recall, and every incorrect accepted merge can be reversed without record loss.

### SC-3: Query quality and grounding

Across at least five predefined network questions, at least 3 of the top 5 returned contacts are judged relevant where five relevant contacts exist; 100% of factual relationship claims have valid citations; and no contact absent from the owner’s canonical graph is presented as an existing relationship.

### SC-4: Convex is critical and demonstrable

Every evaluated network query retrieves Convex semantic chunks, uses them in ranking/context, and exposes their citations. Reindexing the same interaction produces no duplicate active chunks, and a deleted interaction becomes unretrievable immediately through tombstoning.

### SC-5: Collabute meeting-to-action

One recent real Collabute meeting produces linked participants, at least one decision or summary record, and exactly one follow-up per imported action item across two repeated syncs.

### SC-6: WhatsApp ingestion safety

One initial-history import reaches completion, one new incoming or outgoing message appears in the timeline, and replaying its webhook three times still yields exactly one canonical interaction. QR expiry, connection loss, and logout are visible and recoverable.

### SC-7: Source extensibility

An Outlook fixture adapter passes the common connector contract and feeds normalization without changes to entity resolution, profile rendering, or query orchestration.

### SC-8: Stability and graceful degradation

The full demo script passes three consecutive rehearsals. Disabling one nonessential source leaves the rest operational; disabling Convex/OpenRouter produces a clear degraded state without source-data loss; recovery drains the indexing backlog.

### SC-9: Data control

Disconnecting a source stops new ingestion and removes its credential. Choosing source deletion removes its source-only canonical records and active Convex chunks while preserving a person still supported by another source.

### SC-10: Deployability

The submitted web application is deployed at a stable HTTPS URL, starts from documented configuration, passes dependency preflight, and does not depend on a developer’s localhost except for explicitly tunneled/self-hosted Evolution infrastructure.

## Assumptions and Dependencies

- P0 is single-owner, but `owner_id` is mandatory for future isolation and current query safety.
- Team-controlled Google and WhatsApp test accounts contain synthetic or consented demo conversations.
- Google OAuth testing users and required readonly scopes are configured before implementation testing.
- Evolution API is built from the pinned reviewed source and receives the required PII-log sanitization patch/configuration.
- Collabute signup and human OAuth are completed; the demo meeting is within the free plan’s accessible history window.
- The Collabute adapter cannot be finalized until an authenticated `tools/list` response and representative meeting fixture are captured.
- Context.dev provides 500 credits; current successful brand retrieval cost is assumed to be 10 credits.
- Convex Cloud free/starter capacity is sufficient for the bounded demo corpus; special hackathon credits are not assumed.
- OpenRouter exposes `openai/text-embedding-3-small` through its embeddings API and at least one configured generation model.
- PostgreSQL is canonical and Convex is derived/searchable state; their consistency model is eventual and explicit.
- A fictional persona is acceptable, but core connector calls, persistence, retrieval, and citations are real.

## Out of Scope for P0

- Full LinkedIn credential automation or scraping; a future export-file importer is preferred over collecting LinkedIn passwords.
- Telegram unless P0 is complete, Outlook, X, Instagram, Snapchat, and other channels.
- Screenshots/OCR, raw WhatsApp media storage, audio transcription, and full document bodies.
- Message sending, automated outreach, sequences, or acting on recommendations.
- External job/company/opportunity crawling and claims that a company is hiring without imported evidence.
- Automatic AI-only person merges.
- Multi-owner collaboration, tenant administration, mobile/native apps, billing, and payments.
- Production Google restricted-scope verification/security assessment.
- A general graph database; the relationship graph is represented with canonical relational entities.
- Exactly-once delivery from external providers; the system implements at-least-once ingestion with idempotency.

## Clarifications

### Session 2026-08-30

- Main backend remains Python 3.12+/FastAPI; PostgreSQL is canonical. Convex is not a decorative vector call: it is the required semantic-memory index used by every network query.
- Convex does not generate vectors by itself in this design. OpenRouter `openai/text-embedding-3-small` generates 1536-dimensional vectors; model/version are stored and migrations require reindexing.
- Two P0 demos replace the previous conflicting pipeline definitions: identity-to-profile and Collabute-meeting-to-cited-action.
- Required P0 sources are Google, WhatsApp/Evolution, Collabute, Context.dev, Convex, and OpenRouter. Telegram is stretch; LinkedIn is post-hackathon.
- Identity resolution auto-links only high-trust deterministic identifiers. AI-only merges require review regardless of reported confidence.
- Evolution webhooks are not assumed to carry a generic event ID or mandatory body signature. The adapter configures explicit webhook authentication and deduplicates WhatsApp messages by connection/instance plus `key.id`.
- Collabute uses the Coding Tools Streamable HTTP MCP endpoint with human OAuth and runtime tool discovery; meeting tool schemas must be captured after authorization.
- Drive is metadata-only in P0, but a first-class `Document` entity and manual person link are required for the NDA demo.
- Source disconnect and source-data deletion are separate user choices and must propagate to derived semantic state.
- Next.js 15 App Router and Tailwind CSS v4 follow `DESIGN.md`; the primary demo target is desktop Chrome with keyboard-accessible core flows.
