# Data Model: Second Brain CRM

**Canonical store**: PostgreSQL (via PgBouncer).
**Semantic store**: Convex (derived, eventually consistent).
**Embedding**: OpenRouter `openai/text-embedding-3-small`, 1536 dimensions.

All user-owned tables carry `owner_id` (UUID) for future multi-tenant isolation even in single-owner P0. Provider-wide cache/budget tables contain no private relationship content.
All timestamps are `TIMESTAMPTZ`, default `now()`.
All UUIDs are `UUID DEFAULT gen_random_uuid()`.

The snippets describe the target schema, not executable migration order. Alembic migrations MUST create dependency roots first and add circular/convenience foreign keys (for example `owner.self_person_id`, `person.current_org_id`, and `opportunity_person_path.relationship_id`) after the referenced tables exist.

---

## PostgreSQL Schema

### owner

```sql
CREATE TABLE owner (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  display_name  TEXT NOT NULL,
  email         TEXT NOT NULL UNIQUE,
  timezone      TEXT NOT NULL DEFAULT 'UTC',
  location      TEXT,
  current_goal  TEXT,
  self_person_id UUID REFERENCES person(id),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### person

```sql
CREATE TABLE person (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id      UUID NOT NULL REFERENCES owner(id),
  display_name  TEXT NOT NULL,
  photo_url     TEXT,
  current_title TEXT,
  current_org_id UUID REFERENCES organization(id),
  tags          TEXT[] NOT NULL DEFAULT '{}',
  manual_overrides JSONB NOT NULL DEFAULT '{}',
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_person_owner ON person (owner_id);
CREATE INDEX idx_person_tags ON person USING GIN (tags);
```

**Notes**: `current_org_id` is a convenience cache, not source of truth — `Employment` table is canonical. `manual_overrides` stores field-level overrides with provenance: `{"display_name": {"value": "...", "source": "manual", "set_at": "..."}}`.

### person_identity

```sql
CREATE TABLE person_identity (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id             UUID NOT NULL REFERENCES owner(id),
  person_id            UUID NOT NULL REFERENCES person(id),
  source_connection_id UUID NOT NULL REFERENCES source_connection(id),
  kind                 TEXT NOT NULL,  -- email|phone|linkedin_url|telegram_username|whatsapp_jid|whatsapp_lid
  raw_value            TEXT NOT NULL,
  normalized_value     TEXT NOT NULL,
  is_verified          BOOLEAN NOT NULL DEFAULT false,
  is_primary           BOOLEAN NOT NULL DEFAULT false,
  first_seen_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_seen_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX idx_identity_norm ON person_identity (kind, normalized_value, owner_id);
CREATE INDEX idx_identity_person ON person_identity (person_id);
```

**Notes**: Source identity is never destroyed by merge. `normalized_value` is canonicalized (email lowercase, phone E.164, URL canonical). Unique on `(kind, normalized_value)` scoped to owner — prevents duplicate identities.

### organization

```sql
CREATE TABLE organization (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id      UUID NOT NULL REFERENCES owner(id),
  name          TEXT NOT NULL,
  domain        TEXT,
  logo_url      TEXT,
  description   TEXT,
  industry      TEXT,
  socials       JSONB NOT NULL DEFAULT '{}',
  address       JSONB NOT NULL DEFAULT '{}',
  enriched_fields JSONB NOT NULL DEFAULT '{}',  -- field-level provenance
  enriched_at   TIMESTAMPTZ,
  enrichment_provider TEXT,  -- 'context.dev'
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_org_owner ON organization (owner_id);
CREATE INDEX idx_org_domain ON organization (domain);
```

### enrichment_cache

```sql
CREATE TABLE enrichment_cache (
  domain          TEXT PRIMARY KEY,
  outcome         TEXT NOT NULL CHECK (outcome IN ('found','not_found','website_unreachable','skipped_free_email','budget_exhausted')),
  brand_data      JSONB,
  error_code      TEXT,
  credits_consumed INTEGER NOT NULL DEFAULT 0,
  retrieved_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### context_credit_budget and context_credit_usage

```sql
CREATE TABLE context_credit_budget (
  id                   INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
  total_cap            INTEGER NOT NULL DEFAULT 500,
  brand_cap            INTEGER NOT NULL DEFAULT 200,
  market_search_cap    INTEGER NOT NULL DEFAULT 100,
  reserve_floor        INTEGER NOT NULL DEFAULT 200,
  credits_used         INTEGER NOT NULL DEFAULT 0,
  brand_credits_used   INTEGER NOT NULL DEFAULT 0,
  search_credits_used  INTEGER NOT NULL DEFAULT 0,
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
INSERT INTO context_credit_budget (id) VALUES (1) ON CONFLICT DO NOTHING;

CREATE TABLE context_credit_usage (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id             UUID NOT NULL REFERENCES owner(id),
  category             TEXT NOT NULL CHECK (category IN ('brand','market_search')),
  request_key          TEXT NOT NULL,
  credits_reserved     INTEGER NOT NULL,
  credits_consumed     INTEGER,
  status               TEXT NOT NULL CHECK (status IN ('reserved','reconciled','failed')),
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  reconciled_at        TIMESTAMPTZ,
  UNIQUE (category, request_key)
);
```

### market_search_run

```sql
CREATE TABLE market_search_run (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id             UUID NOT NULL REFERENCES owner(id),
  goal                 TEXT NOT NULL,
  query                TEXT NOT NULL,
  query_fingerprint    TEXT NOT NULL,
  country              TEXT,
  freshness            TEXT,
  num_results          INTEGER NOT NULL CHECK (num_results BETWEEN 10 AND 30),
  status               TEXT NOT NULL CHECK (status IN ('pending','running','success','partial','failed')),
  credits_consumed     INTEGER NOT NULL DEFAULT 0,
  last_error           TEXT,
  started_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at          TIMESTAMPTZ,
  UNIQUE (owner_id, query_fingerprint)
);
CREATE INDEX idx_market_search_owner ON market_search_run (owner_id, started_at DESC);
```

### opportunity

```sql
CREATE TABLE opportunity (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id             UUID NOT NULL REFERENCES owner(id),
  organization_id      UUID REFERENCES organization(id),
  canonical_url        TEXT NOT NULL,
  source_domain        TEXT NOT NULL,
  role_title           TEXT,
  location             TEXT,
  summary              TEXT,
  verification_status  TEXT NOT NULL
                       CHECK (verification_status IN ('verified_open_role','hiring_signal','unverified','stale')),
  published_at         TIMESTAMPTZ,
  discovered_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  checked_at           TIMESTAMPTZ NOT NULL,
  saved_at             TIMESTAMPTZ,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (owner_id, canonical_url)
);
CREATE INDEX idx_opportunity_owner_status ON opportunity (owner_id, verification_status, checked_at DESC);
CREATE INDEX idx_opportunity_org ON opportunity (organization_id);
```

### opportunity_evidence

```sql
CREATE TABLE opportunity_evidence (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id             UUID NOT NULL REFERENCES owner(id),
  opportunity_id       UUID NOT NULL REFERENCES opportunity(id),
  search_run_id        UUID NOT NULL REFERENCES market_search_run(id),
  url                  TEXT NOT NULL,
  title                TEXT,
  excerpt              TEXT,
  markdown_ref         TEXT,
  content_hash         TEXT NOT NULL,
  evidence_type        TEXT NOT NULL
                       CHECK (evidence_type IN ('vacancy','careers_page','expansion','funding','office','other')),
  published_at         TIMESTAMPTZ,
  checked_at           TIMESTAMPTZ NOT NULL,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (opportunity_id, url, content_hash)
);
CREATE INDEX idx_opportunity_evidence ON opportunity_evidence (opportunity_id, checked_at DESC);
```

### opportunity_person_path

```sql
CREATE TABLE opportunity_person_path (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id             UUID NOT NULL REFERENCES owner(id),
  opportunity_id       UUID NOT NULL REFERENCES opportunity(id),
  person_id            UUID NOT NULL REFERENCES person(id),
  relationship_id      UUID REFERENCES relationship(id),
  private_evidence_id  UUID REFERENCES interaction_event(id),
  path_type            TEXT NOT NULL CHECK (path_type IN ('direct','introduction','organization','reconnection')),
  path_score           FLOAT NOT NULL,
  rationale            TEXT NOT NULL,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (opportunity_id, person_id, path_type)
);
CREATE INDEX idx_opp_path_opportunity ON opportunity_person_path (opportunity_id, path_score DESC);
```

### employment

```sql
CREATE TABLE employment (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id        UUID NOT NULL REFERENCES owner(id),
  person_id       UUID NOT NULL REFERENCES person(id),
  organization_id UUID NOT NULL REFERENCES organization(id),
  title           TEXT,
  start_date      DATE,
  end_date        DATE,
  is_current      BOOLEAN NOT NULL DEFAULT true,
  evidence_source TEXT,  -- source_connection_id or 'manual'
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_employment_person ON employment (person_id);
CREATE INDEX idx_employment_org ON employment (organization_id);
```

### source_connection

```sql
CREATE TABLE source_connection (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id          UUID NOT NULL REFERENCES owner(id),
  source            TEXT NOT NULL,  -- extensible string: gmail|calendar|drive|whatsapp|collabute|context_dev
  external_account_id TEXT,         -- Google email, Evolution instance name, Collabute workspace ID
  auth_ref          TEXT NOT NULL,  -- reference to encrypted secret storage
  status            TEXT NOT NULL DEFAULT 'disconnected'
                    CHECK (status IN ('disconnected','authorizing','connected','syncing','degraded','reauth_required','error')),
  capabilities      JSONB NOT NULL DEFAULT '{}',
  sync_cursor       JSONB,          -- per-source cursor (historyId, syncToken, etc.)
  last_sync_at      TIMESTAMPTZ,
  last_error        TEXT,           -- sanitized
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_conn_owner ON source_connection (owner_id);
CREATE INDEX idx_conn_source ON source_connection (source);
```

### conversation

```sql
CREATE TABLE conversation (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id             UUID NOT NULL REFERENCES owner(id),
  source_connection_id UUID NOT NULL REFERENCES source_connection(id),
  external_id          TEXT NOT NULL,
  type                 TEXT NOT NULL,  -- email_thread|whatsapp_chat|telegram_dialog|meeting
  title                TEXT,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (source_connection_id, external_id)
);
CREATE INDEX idx_conv_owner ON conversation (owner_id);
```

### interaction_event

```sql
CREATE TABLE interaction_event (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id             UUID NOT NULL REFERENCES owner(id),
  source_connection_id UUID NOT NULL REFERENCES source_connection(id),
  conversation_id      UUID REFERENCES conversation(id),
  external_id          TEXT NOT NULL,
  content_version      INTEGER NOT NULL DEFAULT 1,
  type                 TEXT NOT NULL,  -- email|message|meeting|call|document_shared
  direction            TEXT,           -- incoming|outgoing
  occurred_at          TIMESTAMPTZ NOT NULL,
  subject              TEXT,
  body_text            TEXT,
  metadata             JSONB NOT NULL DEFAULT '{}',
  raw_ref              TEXT,           -- opaque reference to immutable raw record
  is_deleted           BOOLEAN NOT NULL DEFAULT false,
  indexing_state       TEXT NOT NULL DEFAULT 'pending'
                       CHECK (indexing_state IN ('pending','indexing','indexed','failed','tombstoned')),
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (source_connection_id, external_id)
);
CREATE INDEX idx_interaction_owner ON interaction_event (owner_id);
CREATE INDEX idx_interaction_person ON interaction_event (owner_id, occurred_at DESC);
CREATE INDEX idx_interaction_deleted ON interaction_event (is_deleted) WHERE is_deleted = false;
```

**Notes**: `(source_connection_id, external_id)` is the idempotency boundary. `content_version` increments on audited source updates (drives chunk re-indexing). `indexing_state` tracks Convex sync.

### interaction_participant

```sql
CREATE TABLE interaction_participant (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id        UUID NOT NULL REFERENCES owner(id),
  interaction_id  UUID NOT NULL REFERENCES interaction_event(id),
  person_id       UUID REFERENCES person(id),
  identity_id     UUID REFERENCES person_identity(id),
  source_address  TEXT NOT NULL,  -- raw from/to/cc/jid/username
  role            TEXT NOT NULL,  -- sender|recipient|cc|attendee|organizer|group_member
  UNIQUE (interaction_id, source_address, role)
);
CREATE INDEX idx_participant_interaction ON interaction_participant (interaction_id);
CREATE INDEX idx_participant_person ON interaction_participant (person_id);
```

### document

```sql
CREATE TABLE document (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id             UUID NOT NULL REFERENCES owner(id),
  source_connection_id UUID NOT NULL REFERENCES source_connection(id),
  external_id          TEXT NOT NULL,
  name                 TEXT NOT NULL,
  mime_type            TEXT,
  url                  TEXT,          -- webViewLink
  modified_at          TIMESTAMPTZ,
  metadata             JSONB NOT NULL DEFAULT '{}',
  provenance           TEXT,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (source_connection_id, external_id)
);
CREATE INDEX idx_doc_owner ON document (owner_id);
```

### document_person_link

```sql
CREATE TABLE document_person_link (
  owner_id        UUID NOT NULL REFERENCES owner(id),
  document_id      UUID NOT NULL REFERENCES document(id),
  person_id        UUID NOT NULL REFERENCES person(id),
  relationship_type TEXT NOT NULL,  -- nda|contract|proposal|shared_with|other
  provenance       TEXT NOT NULL,   -- manual|drive_metadata
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (document_id, person_id)
);
```

### relationship

```sql
CREATE TABLE relationship (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id          UUID NOT NULL REFERENCES owner(id),
  person_a_id       UUID NOT NULL REFERENCES person(id),  -- always the owner's self_person
  person_b_id       UUID NOT NULL REFERENCES person(id),
  type              TEXT NOT NULL DEFAULT 'contact',
  strength_score    FLOAT NOT NULL DEFAULT 0.0,
  strength_components JSONB NOT NULL DEFAULT '{}',  -- {recency, frequency, channel_diversity, manual_adjust}
  status            TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active','cold','dormant')),
  last_interaction_at TIMESTAMPTZ,
  total_interactions INTEGER NOT NULL DEFAULT 0,
  introduced_by     UUID REFERENCES person(id),
  manual_adjustment FLOAT NOT NULL DEFAULT 0.0,
  evidence          JSONB NOT NULL DEFAULT '[]',
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (owner_id, person_a_id, person_b_id)
);
CREATE INDEX idx_rel_owner ON relationship (owner_id);
CREATE INDEX idx_rel_status ON relationship (owner_id, status);
```

### memory_fact

```sql
CREATE TABLE memory_fact (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id        UUID NOT NULL REFERENCES owner(id),
  person_id       UUID NOT NULL REFERENCES person(id),
  type            TEXT NOT NULL,  -- promise|need|decision|interest|personal_update
  value           TEXT NOT NULL,
  confidence_band TEXT NOT NULL CHECK (confidence_band IN ('high','medium','low')),
  status          TEXT NOT NULL DEFAULT 'suggested'
                  CHECK (status IN ('suggested','accepted','rejected')),
  evidence_interaction_id UUID REFERENCES interaction_event(id),
  valid_from      TIMESTAMPTZ,
  valid_to        TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_fact_person ON memory_fact (person_id);
CREATE INDEX idx_fact_status ON memory_fact (status);
```

### follow_up

```sql
CREATE TABLE follow_up (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id        UUID NOT NULL REFERENCES owner(id),
  person_id       UUID NOT NULL REFERENCES person(id),
  reason          TEXT NOT NULL,
  due_date        DATE,
  due_timezone    TEXT,
  source          TEXT NOT NULL,  -- manual|collabute|cold_relationship
  source_key      TEXT,           -- stable Collabute action ID or content hash
  evidence_interaction_id UUID REFERENCES interaction_event(id),
  priority        INTEGER NOT NULL DEFAULT 0,
  status          TEXT NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending','done','skipped')),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (owner_id, source, source_key)  -- idempotent follow-up creation
);
CREATE INDEX idx_followup_owner ON follow_up (owner_id, status, due_date);
```

### merge_candidate

```sql
CREATE TABLE merge_candidate (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id        UUID NOT NULL REFERENCES owner(id),
  person_a_id     UUID NOT NULL REFERENCES person(id),
  person_b_id     UUID NOT NULL REFERENCES person(id),
  method          TEXT NOT NULL,  -- email|phone|linkedin_url|ai
  evidence        JSONB NOT NULL DEFAULT '{}',
  confidence_band TEXT NOT NULL CHECK (confidence_band IN ('high','medium','low')),
  status          TEXT NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending','accepted','rejected','auto_merged')),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  reviewed_at     TIMESTAMPTZ
);
CREATE INDEX idx_merge_status ON merge_candidate (owner_id, status);
```

### merge_operation

```sql
CREATE TABLE merge_operation (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id        UUID NOT NULL REFERENCES owner(id),
  survivor_person_id  UUID NOT NULL REFERENCES person(id),
  merged_person_id    UUID NOT NULL REFERENCES person(id),
  reassignment_ledger JSONB NOT NULL,  -- snapshot of all reassigned records
  actor           TEXT NOT NULL,       -- owner|system
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  reversed_at     TIMESTAMPTZ
);
CREATE INDEX idx_merge_op_survivor ON merge_operation (survivor_person_id);
```

### sync_run

```sql
CREATE TABLE sync_run (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id        UUID NOT NULL REFERENCES owner(id),
  connection_id   UUID NOT NULL REFERENCES source_connection(id),
  mode            TEXT NOT NULL,  -- initial|delta
  checkpoint      JSONB,
  status          TEXT NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending','running','success','failed','partial')),
  processed_count INTEGER NOT NULL DEFAULT 0,
  skipped_count   INTEGER NOT NULL DEFAULT 0,
  error_count     INTEGER NOT NULL DEFAULT 0,
  last_error      TEXT,           -- sanitized
  started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at     TIMESTAMPTZ
);
CREATE INDEX idx_syncrun_conn ON sync_run (connection_id, status);
```

### semantic_index_outbox

```sql
CREATE TABLE semantic_index_outbox (
  id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  owner_id        UUID NOT NULL REFERENCES owner(id),
  interaction_id  UUID NOT NULL REFERENCES interaction_event(id),
  content_version INTEGER NOT NULL,
  op              TEXT NOT NULL CHECK (op IN ('upsert','tombstone','delete')),
  status          TEXT NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending','processing','done','failed')),
  attempts        INTEGER NOT NULL DEFAULT 0,
  next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_error      TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (interaction_id, content_version, op)
);
CREATE INDEX idx_outbox_pending ON semantic_index_outbox (next_attempt_at)
  WHERE status IN ('pending','failed');
```

---

## Convex Schema (TypeScript)

```typescript
// convex/schema.ts
import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

export default defineSchema({
  semanticChunks: defineTable({
    chunk_key: v.string(),
    owner_id: v.string(),
    owner_scope: v.string(),  // composite: "{owner_id}:{embedding_version}:active"
    interaction_id: v.string(),
    person_ids: v.array(v.string()),
    source: v.string(),
    occurred_at: v.number(),
    ordinal: v.number(),
    text: v.string(),
    text_hash: v.string(),
    citation_locator: v.string(),
    embedding_model: v.string(),
    embedding_version: v.string(),
    embedding: v.array(v.float64()),
    active: v.boolean(),
    tombstoned_at: v.optional(v.number()),
    indexed_at: v.number(),
  })
    .index("by_chunk_key", ["chunk_key", "embedding_version"])
    .index("by_interaction", ["owner_id", "interaction_id"])
    .index("by_tombstoned", ["active", "tombstoned_at"])
    .vectorIndex("by_embedding", {
      vectorField: "embedding",
      dimensions: 1536,
      filterFields: ["owner_scope", "source"],
    }),
});
```

**Notes**: `owner_scope` composite field enables single `q.eq("owner_scope", "{owner_id}:{version}:active")` filter — safest encoding given Convex filter API is `eq`/`or` only. Documents with `active=false` and no valid embedding are silently excluded from the vector index.

---

## Entity Relationship Summary

```
Owner 1───* Person 1───* PersonIdentity
  │             │
  │             *───* Employment *───1 Organization
  │             │                         │
  │             *───* Relationship        *───* Opportunity
  │             │                                  │
  │             *───* MemoryFact                   *───* OpportunityEvidence
  │             │                                  │
  │             *───* FollowUp                     *───* OpportunityPersonPath *───1 Person
  │             │
  │             *───* MergeCandidate
  │             │
  │             *───* InteractionEvent *───* InteractionParticipant
  │                                       │
  │                                       *───1 Conversation ───1 SourceConnection
  │             │
  │             *───* Document *───* DocumentPersonLink
  │
  *───* MarketSearchRun *───* OpportunityEvidence

MergeOperation (ledger: survivor + merged → reversible)
SyncRun (per-connection sync history)
SemanticIndexOutbox (PG → Convex indexing queue)
EnrichmentCache + ContextCreditBudget/Usage (Context.dev)
```

---

## State Transitions

### SourceConnection.status

```
disconnected → authorizing → connected → syncing → connected
                                   │           │
                                   ↓           ↓
                              degraded     reauth_required
                                   │           │
                                   ↓           ↓
                                 error       error
```

### InteractionEvent.indexing_state

```
pending → indexing → indexed
              │
              ↓
           failed → indexing (retry)
```

On deletion: `indexed → tombstoned` (triggers Convex tombstone via outbox).

### MergeCandidate.status

```
pending → accepted (creates MergeOperation)
pending → rejected
accepted → (reversible via MergeOperation.reversed_at)
```

### FollowUp.status

```
pending → done
pending → skipped
done → pending (reopen)
skipped → pending (reopen)
```

### Opportunity.verification_status

```text
unverified → verified_open_role
unverified → hiring_signal
verified_open_role → stale
hiring_signal → verified_open_role
hiring_signal → stale
stale → verified_open_role (fresh re-check)
```

Only a fresh public evidence check can enter or restore `verified_open_role`.
