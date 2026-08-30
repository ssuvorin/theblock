# Integration Contract: Context.dev Market Search and Organization Enrichment

**Base URL**: `https://api.context.dev/v1`  
**Auth**: `Authorization: Bearer <key>` from runtime secret `CONTEXT_DEV_API_KEY`  
**Total assumed budget**: 500 credits

Budget allocation:

- up to 100 credits for bounded on-demand web searches;
- up to 200 credits for 20 successful brand retrievals;
- at least 200 credits retained as demo/retry reserve.

`key_metadata.credits_consumed` and `credits_remaining` are authoritative. The application never logs the key or full private query context.

---

## Web Search — Primary Demo Entry Point

### POST /web/search

Search public current opportunities before looking for warm paths in the private network.

```http
POST https://api.context.dev/v1/web/search
Authorization: Bearer <API_KEY>
Content-Type: application/json

{
  "query": "(Product Manager OR Product Lead) (crypto OR web3 OR digital assets) (Dubai OR UAE) (jobs OR careers OR hiring)",
  "numResults": 20,
  "country": "ae",
  "freshness": "last_month",
  "queryFanout": true,
  "excludeDomains": ["linkedin.com"],
  "markdownOptions": {
    "enabled": false
  }
}
```

### Request constraints

| Field | P0 rule |
|---|---|
| `query` | Natural language or operators, 1–500 characters; no private message text |
| `numResults` | 10–30 even though provider supports up to 100 |
| `country` | `ae` for the Dubai/UAE demo |
| `freshness` | Explicitly `last_week`, `last_month`, or `last_year` |
| `queryFanout` | Optional and credit-budgeted |
| `includeDomains` | Optional allowlist for selected public ATS/career domains |
| `excludeDomains` | Exclude sources that cannot be safely verified/scraped, including LinkedIn |
| `markdownOptions.enabled` | False for broad discovery; true only for shortlisted results needing verification |

### Normalized result

Every result is mapped to an immutable public evidence record:

```json
{
  "url": "https://company.example/careers/product-manager-dubai",
  "title": "Product Manager — Dubai",
  "source_domain": "company.example",
  "excerpt": "...",
  "markdown": null,
  "published_at": null,
  "discovered_at": "2026-08-30T12:00:00Z",
  "checked_at": "2026-08-30T12:00:00Z",
  "query_fingerprint": "sha256:...",
  "provider_cache_metadata": {},
  "credits_consumed": 2
}
```

### Opportunity verification

A result is `verified_open_role` only when the checked public evidence explicitly confirms:

1. role/title;
2. company identity;
3. Dubai/UAE location or applicable remote eligibility;
4. open vacancy/application state;
5. accessible source URL at `checked_at`.

Other states:

- `hiring_signal`: expansion, funding, UAE office, product-team growth, or careers evidence without a matching confirmed role;
- `unverified`: ambiguous/snippet-only result or incomplete fields;
- `stale`: previously verified source is unavailable or no longer open.

Brand enrichment is never used as proof of an open role. Public web citations and private relationship citations remain separate.

---

## Brand Retrieval — Organization Resolution

### POST /brand/retrieve

```http
POST https://api.context.dev/v1/brand/retrieve
Authorization: Bearer <API_KEY>
Content-Type: application/json

{
  "type": "by_domain",
  "domain": "company.example",
  "timeoutMS": 60000,
  "tags": ["hackathon-demo"]
}
```

The CRM uses `by_domain` for P0. It stores brand title/domain, description, logos, socials, address, EIC industries, provider provenance, retrieval time, cache metadata, and key metadata.

NAICS/SIC require separate calls and are outside the P0 budget.

---

## Error Mapping

| HTTP | Error | Action |
|---|---|---|
| 400 | `NOT_FOUND`, `WEBSITE_NOT_FOUND`, `WEBSITE_ACCESS_ERROR` | Cache terminal miss where applicable |
| 400/422 | `INPUT_VALIDATION_ERROR` | Treat as adapter/query bug; do not retry |
| 401/403 | Unauthorized/permission | Mark integration error; require credential correction |
| 408/5xx | Timeout/provider failure | Bounded retry with backoff |
| 429 | Rate limited | Honor `Retry-After`, then bounded retry |

A market-search failure returns valid network-only results with a visible degraded/partial state. It never converts cached or unverified results into current vacancies.

---

## Caching and Idempotency

- Brand hits and misses are cached by normalized domain for at least 24 hours.
- Market searches are cached by owner-safe query fingerprint, country, freshness, and requested result count for the demo freshness period.
- Opportunity evidence is upserted by canonical URL plus checked content/version hash.
- Repeating the same search updates checked time and evidence state without duplicating active opportunities.
- A disappeared/closed source changes the opportunity to `stale`; historical evidence is retained for audit until user deletion.

---

## Budget Enforcement

Use a PostgreSQL credit ledger rather than a call counter:

1. atomically reserve the expected credits for a request category;
2. reject or defer the request if it would cross that category or total cap;
3. reconcile the reservation with response `key_metadata.credits_consumed`;
4. expose remaining demo budget in dependency preflight;
5. never run continuous or bulk market crawling in P0.

The default web-search assumption is 1 credit per 10 requested results. Provider response metadata overrides estimates.

---

## Python

Use the official `context.dev` SDK when it exposes the required web-search response fields; otherwise use `httpx` against the documented endpoints. Validate all responses at the adapter boundary and implement application-level retry/budget logic.
