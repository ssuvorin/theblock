# Project Constitution: Second Brain CRM

## Purpose

This constitution defines the inviolable engineering principles and constraints for the Second Brain / Intelligent CRM project. All code, architecture decisions, and specifications MUST comply with these principles.

## Engineering Principles

### OOP (Object-Oriented Programming)

- Model domain entities as objects with encapsulated state and behavior.
- Favor composition over inheritance.
- Use abstract base classes / protocols to define contracts, not to share code.
- Each class has a single responsibility (see SOLID below).

### SOLID

- **S — Single Responsibility:** Each class/module has one reason to change. A `PersonResolver` resolves identities; it does not send emails.
- **O — Open/Closed:** Extend behavior through new implementations of protocols, not by modifying existing classes. Use dependency injection.
- **L — Liskov Substitution:** Any subclass/implementation must be substitutable for its parent/protocol without breaking behavior.
- **I — Interface Segregation:** Clients depend only on the protocols they use. Split fat interfaces into role-specific protocols.
- **D — Dependency Inversion:** High-level modules depend on abstractions (protocols/ABCs), not concrete implementations. Inject dependencies via constructors.

### YAGNI (You Aren't Gonna Need It)

- Build only what the current spec requires.
- Do not pre-build integrations, abstractions, or features for hypothetical future needs.
- A clean architecture makes adding later cheap; pre-building makes everything expensive now.

### KISS (Keep It Simple, Stupid)

- Choose the simplest solution that satisfies the requirement.
- Prefer explicit over clever. Prefer readable over compact.
- If a design needs more than one paragraph to justify, simplify it.

### DRY (Don't Repeat Yourself)

- Every piece of knowledge has a single, unambiguous representation.
- Duplicate logic → extract to a shared function/protocol.
- Duplicate data → normalize to a single source of truth.
- Exception: test fixtures may duplicate for clarity.

### CLink (Composition over Inheritance + Loose Coupling)

- Prefer composition: inject collaborators via constructor.
- Loose coupling: modules communicate through protocols/interfaces, never through concrete classes.
- Tight cohesion: things that change together live together.

### IsDry (Idempotent External Processing)

- All retryable external operations (syncs, imports, webhooks, indexing jobs) MUST be idempotent.
- Reprocessing the same source event produces no duplicate active canonical record, follow-up, or semantic chunk.
- Canonical entities use internal UUIDs. Canonical source artifacts use documented unique idempotency keys based on owner/source connection plus source-native IDs; source versions/content hashes decide whether processing is a no-op or an audited update.
- Interactive owner edits are ordinary versioned state changes; API-level idempotency keys are required only where a client may safely retry the same command.

## Size Guards

These limits are HARD constraints enforced by CI. A PR that violates them is blocked.

| Unit | Max Lines | Rationale |
|------|-----------|-----------|
| File | 700 | Navigable in one screen-pair; forces module decomposition |
| Class | 300 | Single responsibility stays honest; testable in isolation |
| Function | 80 | One function = one mental chunk; readable top-to-bottom |

### Enforcement

- **Ruff** (Python lint + format, replaces Black + isort + flake8)
- **ESLint + Prettier** (TypeScript / Next.js)
- **CI gate:** script counts lines per file/class/function; fails if any exceed limits.
- **Refactor trigger:** when a unit approaches 80% of its limit, extract a new unit.

## Tech Stack Constraints

- **Backend:** Python 3.12+ / FastAPI
- **Frontend:** Next.js 16.3.3 (App Router) + Tailwind CSS v4, dark-first per `mockups/BRANDBOOK.md`
- **Containerization:** Docker + Docker Compose
- **Canonical Database:** PostgreSQL (via PgBouncer connection pooling)
- **Task Queue:** Redis + Celery, used only where durable asynchronous work is required
- **Semantic Store:** Convex vector search; PostgreSQL remains canonical and synchronization is explicit/eventually consistent
- **Embeddings:** OpenRouter `openai/text-embedding-3-small`, 1536 dimensions, versioned for reindexing
- **LLM:** OpenRouter (multi-model routing and cited answer generation)
- **Lint/Format:** Ruff (Python) + ESLint/Prettier (TS)
- **No premature optimization:** profile first, optimize second.
- **No magic:** explicit is better than implicit. No metaclass tricks, no `__getattr__` chains.
