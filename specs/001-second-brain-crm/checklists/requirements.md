# Specification Quality Checklist: Second Brain / Intelligent CRM

**Purpose**: Validate specification completeness and readiness before implementation planning  
**Updated**: 2026-08-30  
**Feature**: [spec.md](../spec.md)

## Product and Scope

- [x] Core user problem, primary persona, and user value are explicit.
- [x] P0, stretch, post-hackathon, and out-of-scope work are separated.
- [x] Two required demo pipelines and the canonical `demo.md` presentation flow are defined with live-vs-fallback rules.
- [x] The Dubai Product Manager demo starts with bounded Context.dev vacancy search, then connects public opportunities to helpful people and warm paths in the owner’s network.
- [x] Verified open roles, weaker hiring signals, stale results, and no-warm-path opportunities have explicit evidence rules.
- [x] Telegram cannot block P0; LinkedIn is no longer ambiguously both in scope and roadmap-only.
- [x] Screenshots, full document content, media, automatic sending/applications, and continuous opportunity monitoring have explicit scope decisions.
- [x] Relationship-grounded draft/edit/copy/reminder actions are included without automatic sending.
- [x] Sponsor integrations are tied to product value rather than isolated demonstrations.

## Requirements and Acceptance

- [x] P0 user scenarios have Given/When/Then acceptance outcomes.
- [x] Functional requirements use stable FR numbering and testable MUST language where required.
- [x] Success criteria define datasets, repetitions, precision/recall, latency, citation, idempotency, deletion, and deployment outcomes.
- [x] Failure, reauthorization, replay, partial-sync, stale-index, and no-evidence cases are covered.
- [x] No `[NEEDS CLARIFICATION]` markers remain.
- [x] Assumptions that require pre-hackathon validation are explicitly identified.

## Data Model and Consistency

- [x] Owner, source identity/provenance, multi-participant interactions, employment history, documents, memory facts, merge ledger, sync runs, semantic chunks, market searches, opportunities, public evidence, and opportunity-person paths are modeled.
- [x] A first-class `Document` model supports the NDA demo.
- [x] Reversible merges are implementable without destroying source records.
- [x] PostgreSQL is canonical and Convex is derived semantic state with an explicit durable handoff, update, tombstone, and reindex model.
- [x] Idempotency boundaries use source connection plus source-native identifiers rather than conflicting canonical deterministic IDs.
- [x] All canonical and semantic data is scoped by `owner_id` despite single-owner P0.

## Integration Readiness

- [x] Evolution API requirements are grounded in pinned source version/commit and actual QR, history, webhook, retry, message-key, JID/LID, and lifecycle behavior.
- [x] Evolution webhook authentication is explicitly configured rather than assuming a default body signature.
- [x] Evolution PII/secret logging is a release blocker with a required source/configuration remediation.
- [x] Collabute is mandatory, uses the Coding Tools Streamable HTTP MCP endpoint, requires human OAuth, and performs runtime tool discovery.
- [x] Capturing authenticated Collabute `tools/list` and a representative fixture is identified as a planning/implementation prerequisite.
- [x] Convex is in the critical path of every evaluated network query and owns chunk retrieval/citation metadata.
- [x] OpenRouter embedding model and vector dimension are pinned; model migration requires reindexing.
- [x] Google initial/delta sync, bounded recovery, readonly scopes, and testing-mode constraints are specified.
- [x] Context.dev `/web/search` and `/brand/retrieve` contracts, opportunity verification, credit allocation, caching, `NOT_FOUND`, and rate-limit behavior are specified.

## Privacy, Security, and Operations

- [x] Source consent, lookback, third-party processor disclosure, pause/disconnect/delete, and derived-data cleanup are required.
- [x] OAuth state, session security, secret storage, webhook validation, least privilege, and log redaction are covered.
- [x] Demo data is limited to team-controlled synthetic or consented accounts.
- [x] Performance criteria state corpus/run conditions and distinguish durable ingestion from eventual semantic indexing.
- [x] Dependency preflight, degraded modes, backlog recovery, rate/cost telemetry, and HTTPS deployment are required.
- [x] Core accessibility and browser target requirements are defined.

## Deliberate Specification Style Decision

- [x] The specification intentionally contains implementation details for named sponsor/platform contracts (Evolution API, Collabute MCP, Convex, Context.dev, OpenRouter, Google). This is necessary to make integration requirements testable and supersedes the generic template preference for a fully technology-agnostic feature spec.
- [x] Product success criteria remain outcome-oriented, while sponsor-specific criteria verify that required integrations are real and meaningful.

## Readiness Decision

- [x] Specification, research, data model, contracts, quickstart, and implementation plan are ready for `/speckit-tasks`; tasks must begin with validation spikes for authenticated Collabute `tools/list`, Google test OAuth, the sanitized pinned Evolution build, and live Convex/OpenRouter/Context.dev preflight.
- [x] `/speckit-tasks` must preserve the P0/P1 boundary, the opportunity-first `demo.md` flow, and must not promote Telegram, LinkedIn scraping, raw media, full document indexing, automatic sending, or continuous vacancy monitoring into the critical path.
