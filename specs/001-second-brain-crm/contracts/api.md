# API Contract: Second Brain CRM Backend (FastAPI)

**Base URL**: `http://localhost:8000` (dev) / `https://<api-domain>` (prod)
**Auth**: JWT bearer token (owner session)
**Content-Type**: `application/json`

All endpoints scoped by authenticated owner. `owner_id` injected server-side.

---

## Authentication

### POST /api/auth/session

Owner login (P0: single hardcoded owner or simple credential).

**Request**: `{ email, password }`
**Response 200**: `{ access_token, token_type: "bearer", expires_in }`

---

## Source Connections

### GET /api/connections

List all source connections for the owner.

**Response 200**: `{ connections: SourceConnection[] }`

```json
{
  "connections": [
    {
      "id": "uuid",
      "source": "gmail",
      "external_account_id": "demo@example.com",
      "status": "connected",
      "last_sync_at": "2026-08-30T10:00:00Z",
      "last_error": null,
      "capabilities": { "scopes": ["gmail.readonly", "calendar.readonly"] }
    }
  ]
}
```

### POST /api/connections/{source}/connect

Initiate OAuth/connect flow for a source.

**Path params**: `source` = `gmail` | `whatsapp` | `collabute`

**Response 200** (Google/Collabute): `{ redirect_url: "https://..." }`
**Response 200** (WhatsApp): `{ qr_code_base64: "data:image/png;base64,...", instance_name: "..." }`

### GET /api/connections/{source}/callback

OAuth callback endpoint (Google, Collabute). Validates `state`, exchanges code, stores tokens.

**Query params**: `code`, `state`
**Response 302**: Redirect to frontend `/settings/connections?status=ok|error`

### GET /api/connections/{id}/status

Get connection status and sync info.

**Response 200**: `{ id, source, status, sync_cursor, last_sync_at, last_error, sync_runs: SyncRun[] }`

### POST /api/connections/{id}/sync

Trigger a manual sync.

**Response 202**: `{ sync_run_id: "uuid", status: "running" }`

### DELETE /api/connections/{id}

Disconnect a source. Optionally delete imported data.

**Query params**: `delete_data=true|false`
**Response 200**: `{ id, status: "disconnected", data_deleted: true|false }`

---

## People

### GET /api/people

Searchable directory of people.

**Query params**: `q` (search), `tag`, `status` (active/cold/dormant), `page`, `limit`
**Response 200**: `{ people: PersonSummary[], total, page }`

```json
{
  "people": [
    {
      "id": "uuid",
      "display_name": "Sergey S.",
      "current_title": "CTO",
      "current_org": "Acme Corp",
      "relationship_status": "active",
      "last_interaction_at": "2026-08-28T14:00:00Z",
      "tags": ["web3", "investor"],
      "sources": ["gmail", "whatsapp", "collabute"]
    }
  ]
}
```

### GET /api/people/{id}

Full person profile.

**Response 200**: `{ person: PersonProfile }`

```json
{
  "person": {
    "id": "uuid",
    "display_name": "Sergey S.",
    "photo_url": null,
    "current_title": "CTO",
    "current_org": { "id": "uuid", "name": "Acme Corp", "domain": "acme.com" },
    "identities": [
      { "kind": "email", "value": "s***@acme.com", "source": "gmail", "verified": true },
      { "kind": "whatsapp_jid", "value": "971***@s.whatsapp.net", "source": "whatsapp" }
    ],
    "employments": [
      { "title": "CTO", "org": "Acme Corp", "start": "2024-01", "current": true }
    ],
    "relationship": {
      "status": "active",
      "strength_score": 0.72,
      "strength_components": { "recency": 0.8, "frequency": 0.6, "channel_diversity": 0.7, "manual_adjust": 0.0 },
      "last_interaction_at": "2026-08-28T14:00:00Z",
      "total_interactions": 47
    },
    "interactions": [
      {
        "id": "uuid",
        "type": "email",
        "source": "gmail",
        "subject": "Re: Partnership",
        "occurred_at": "2026-08-28T14:00:00Z",
        "direction": "incoming",
        "snippet": "..."
      }
    ],
    "documents": [
      { "id": "uuid", "name": "NDA.pdf", "relationship_type": "nda", "url": "..." }
    ],
    "memory_facts": [
      { "type": "decision", "value": "Agreed to Q4 pilot", "confidence": "high", "status": "accepted" }
    ],
    "follow_ups": [
      { "id": "uuid", "reason": "Send pilot proposal", "due_date": "2026-09-05", "status": "pending" }
    ],
    "source_badges": ["gmail", "whatsapp", "collabute", "calendar"]
  }
}
```

### PATCH /api/people/{id}

Manual edit of person fields. Manual overrides take precedence over sync data.

**Request**: `{ display_name?, current_title?, tags? }`
**Response 200**: `{ person: PersonProfile }`

---

## Interactions

### GET /api/people/{person_id}/interactions

Paginated interaction timeline for a person.

**Query params**: `source` (filter), `page`, `limit`
**Response 200**: `{ interactions: InteractionEvent[], total, page }`

### GET /api/interactions/{id}

Full interaction detail with participants and citation locator.

**Response 200**: `{ interaction: InteractionDetail }`

### DELETE /api/interactions/{id}

Delete an interaction and trigger semantic cleanup.

**Response 200**: `{ id, deleted: true }`

---

## Merge Review

### GET /api/merges

List pending merge candidates.

**Response 200**: `{ candidates: MergeCandidate[] }`

### POST /api/merges/{id}/accept

Accept a merge proposal. Creates MergeOperation, reassigns records.

**Response 200**: `{ survivor_person_id, merged_person_id, merge_operation_id }`

### POST /api/merges/{id}/reject

Reject a merge proposal.

**Response 200**: `{ id, status: "rejected" }`

### POST /api/merges/operations/{id}/undo

Reverse an accepted merge.

**Response 200**: `{ merge_operation_id, reversed: true }`

---

## Follow-ups

### GET /api/followups

Dashboard of follow-ups.

**Query params**: `status` (pending/done/skipped), `sort` (due_date/priority)
**Response 200**: `{ follow_ups: FollowUp[] }`

### POST /api/followups

Create a manual follow-up.

**Request**: `{ person_id, reason, due_date?, priority? }`
**Response 201**: `{ follow_up: FollowUp }`

### PATCH /api/followups/{id}

Update follow-up status.

**Request**: `{ status?, due_date?, priority? }`
**Response 200**: `{ follow_up: FollowUp }`

---

## Opportunity-First Job and Network Query

### POST /api/query

Search current public opportunities first, then connect them to people and warm paths in the owner’s private network.

**Request**:
```json
{
  "question": "I’m looking for a Product Manager role at a crypto company in Dubai. Which relevant companies are hiring now, who in my network could help, and which warm paths should I follow?"
}
```

**Response 200**:
```json
{
  "answer": {
    "summary": "Three current or high-confidence opportunities were found. Two have evidence-backed warm paths in your network.",
    "goal": {
      "role": "Product Manager",
      "related_roles": ["Senior Product Manager", "Product Lead"],
      "industry": ["crypto", "web3", "digital assets"],
      "location": ["Dubai", "UAE"]
    },
    "search": {
      "provider": "context.dev",
      "country": "ae",
      "freshness": "last_month",
      "checked_at": "2026-08-30T12:00:00Z",
      "credits_consumed": 2
    },
    "opportunities": [
      {
        "opportunity_id": "uuid",
        "verification_status": "verified_open_role",
        "role_title": "Product Manager",
        "organization": { "id": "uuid", "name": "Company X", "domain": "company.example" },
        "location": "Dubai",
        "goal_fit": "strong",
        "public_citations": [
          {
            "url": "https://company.example/careers/product-manager-dubai",
            "title": "Product Manager — Dubai",
            "source_domain": "company.example",
            "checked_at": "2026-08-30T12:00:00Z",
            "excerpt": "..."
          }
        ],
        "warm_paths": [
          {
            "person_id": "uuid",
            "display_name": "Marta",
            "current_role": "VP Product at Company X",
            "path": ["You", "Marta", "Company X"],
            "relevance_reason": "Direct relationship, product leadership, and company match",
            "suggested_action": "Reconnect and ask for perspective on the role and team",
            "confidence_band": "high",
            "private_citations": [
              {
                "interaction_id": "uuid",
                "source": "gmail",
                "subject": "TOKEN2049 follow-up",
                "occurred_at": "2026-01-05T14:00:00Z",
                "snippet": "..."
              }
            ]
          }
        ]
      }
    ],
    "evidence_quality": "sufficient",
    "degraded": false
  }
}
```

An opportunity with no relationship path returns `"warm_paths": []` and remains visible. The service never invents a contact.

**Response 200 (partial — market search failed)**:
```json
{
  "answer": {
    "summary": "Current vacancy search is temporarily unavailable. Showing relevant people from your network only.",
    "opportunities": [],
    "network_candidates": [...],
    "evidence_quality": "partial",
    "degraded": true,
    "degraded_components": ["context_dev_search"]
  }
}
```

**Response 200 (partial — private retrieval failed)**:
```json
{
  "answer": {
    "summary": "Current opportunities were found, but warm-path search is temporarily unavailable.",
    "opportunities": [...],
    "evidence_quality": "partial",
    "degraded": true,
    "degraded_components": ["convex"]
  }
}
```

**Response 200 (no evidence)**:
```json
{
  "answer": {
    "summary": "No verified opportunities or supported network paths were found for this goal.",
    "opportunities": [],
    "network_candidates": [],
    "evidence_quality": "insufficient",
    "degraded": false
  }
}
```

---

## Opportunities

### GET /api/opportunities

List discovered opportunities for the owner.

**Query params**: `verification_status`, `saved`, `organization_id`, `page`, `limit`  
**Response 200**: `{ opportunities: Opportunity[], total, page }`

### GET /api/opportunities/{id}

Return normalized opportunity, public evidence history, resolved organization, and current warm paths.

### PATCH /api/opportunities/{id}

Save/unsave or mark a result dismissed without changing provider evidence.

**Request**: `{ saved?: boolean, dismissed?: boolean }`  
**Response 200**: `{ opportunity: Opportunity }`

---

## Relationship-grounded Drafts

### POST /api/people/{person_id}/draft

Generate an editable draft from the owner’s current goal and cited relationship evidence. This endpoint never sends a message.

**Request**:
```json
{
  "goal": "Find a Product Manager role at a crypto company in Dubai",
  "opportunity_id": "uuid",
  "action": "reconnect",
  "channel": "generic"
}
```

**Response 200**:
```json
{
  "draft": {
    "text": "Hi Marta, it has been a while since TOKEN2049...",
    "person_id": "uuid",
    "opportunity_id": "uuid",
    "send_supported": false,
    "apply_supported": false,
    "allowed_actions": ["edit", "copy", "open_external_client", "create_reminder", "save_opportunity"],
    "private_citations": [
      { "interaction_id": "uuid", "source": "gmail", "occurred_at": "2026-01-05T14:00:00Z" }
    ],
    "public_citations": [
      { "url": "https://company.example/careers/product-manager-dubai", "checked_at": "2026-08-30T12:00:00Z" }
    ]
  }
}
```

The backend rejects unsupported send/deliver actions. Copy and external-client handoff are explicit client-side actions. A reminder uses `POST /api/followups`.

---

## Webhooks

### POST /api/webhooks/evolution/{instance_name}

Evolution API webhook receiver. Validates `x-webhook-secret` header. Deduplicates by `(instance_name, data.key.id)`. Returns 200 immediately after durable enqueue.

**Headers**: `x-webhook-secret: <shared secret>`
**Body**: Evolution webhook envelope (see contracts/evolution-api.md)

**Response 200**: `{ ack: true }`

---

## Health

### GET /api/health

Application health.

**Response 200**: `{ status: "healthy", version: "..." }`

### GET /api/health/deps

Dependency preflight check.

**Response 200**:
```json
{
  "postgresql": "healthy",
  "redis": "healthy",
  "convex": "healthy",
  "openrouter": "healthy",
  "evolution": "healthy",
  "google_oauth": "configured",
  "collabute": "needs_reauth",
  "context_dev": { "web_search": "ready", "brand_retrieve": "ready", "credits_remaining": 450 }
}
```
