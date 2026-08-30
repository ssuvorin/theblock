# Integration Contract: Convex Semantic Memory

**Role**: Critical-path semantic vector store. PostgreSQL is canonical; Convex is derived.
**Embedding**: OpenRouter `openai/text-embedding-3-small`, 1536 dimensions.
**Python client**: `convex` PyPI package (v0.7.0), synchronous — wrap in `asyncio.to_thread` for async routes.

---

## Convex Schema (TypeScript)

```typescript
// convex/schema.ts
import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

export default defineSchema({
  semanticChunks: defineTable({
    chunk_key: v.string(),         // sha256(interaction_id:content_version:ordinal)
    owner_id: v.string(),
    owner_scope: v.string(),       // composite: "{owner_id}:{embedding_version}:active"
    interaction_id: v.string(),
    person_ids: v.array(v.string()),
    source: v.string(),
    occurred_at: v.number(),       // epoch ms
    ordinal: v.number(),
    text: v.string(),
    text_hash: v.string(),
    citation_locator: v.string(),
    embedding_model: v.string(),   // "openai/text-embedding-3-small"
    embedding_version: v.string(), // "v1"
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

---

## Convex Functions

### chunks:upsertBatch (internalMutation)

Idempotent upsert keyed on `(chunk_key, embedding_version)`. Called by the outbox worker after computing embeddings.

```typescript
export const upsertBatch = internalMutation({
  args: { chunks: v.array(v.object({ /* all SemanticChunk fields */ })) },
  handler: async (ctx, args) => {
    for (const c of args.chunks) {
      const existing = await ctx.db.query("semanticChunks")
        .withIndex("by_chunk_key", (q) =>
          q.eq("chunk_key", c.chunk_key).eq("embedding_version", c.embedding_version))
        .unique();
      if (existing === null) {
        await ctx.db.insert("semanticChunks", { ...c, active: true, indexed_at: Date.now() });
      } else if (existing.text_hash !== c.text_hash || !existing.active) {
        await ctx.db.replace("semanticChunks", existing._id, { ...c, active: true, indexed_at: Date.now() });
      }
      // else: identical content — no-op (retry safe)
    }
  },
});
```

**Batch limit**: ≤50 chunks per call (~600 KiB of vectors) to stay under transaction limits.

### chunks:tombstoneInteraction (internalMutation)

```typescript
export const tombstoneInteraction = internalMutation({
  args: { owner_id: v.string(), interaction_id: v.string() },
  handler: async (ctx, args) => {
    const docs = await ctx.db.query("semanticChunks")
      .withIndex("by_interaction", (q) =>
        q.eq("owner_id", args.owner_id).eq("interaction_id", args.interaction_id))
      .collect();
    for (const d of docs) {
      await ctx.db.patch("semanticChunks", d._id, { active: false, tombstoned_at: Date.now() });
    }
    return docs.length;
  },
});
```

### chunks:purgeTombstoned (internalMutation)

```typescript
export const purgeTombstoned = internalMutation({
  args: { olderThan: v.number(), batch: v.number() },
  handler: async (ctx, args) => {
    const docs = await ctx.db.query("semanticChunks")
      .withIndex("by_tombstoned", (q) => q.eq("active", false).lt("tombstoned_at", args.olderThan))
      .take(args.batch);
    for (const d of docs) await ctx.db.delete("semanticChunks", d._id);
    return docs.length;
  },
});
```

### chunks:search (action)

```typescript
export const search = action({
  args: {
    vector: v.array(v.float64()),
    owner_id: v.string(),
    embedding_version: v.string(),
    sources: v.optional(v.array(v.string())),
    occurred_after: v.optional(v.number()),
    occurred_before: v.optional(v.number()),
    limit: v.optional(v.number()),
  },
  handler: async (ctx, args) => {
    const ownerScope = `${args.owner_id}:${args.embedding_version}:active`;
    const results = await ctx.vectorSearch("semanticChunks", "by_embedding", {
      vector: args.vector,
      limit: Math.min(args.limit ?? 32, 256),
      filter: (q) => q.eq("owner_scope", ownerScope),
    });
    const docs = await ctx.runQuery(internal.chunks.fetchResults, {
      ids: results.map((r) => r._id),
    });
    const scores = new Map(results.map((r) => [r._id, r._score]));
    return docs
      .filter((d) =>
        (args.occurred_after === undefined || d.occurred_at >= args.occurred_after) &&
        (args.occurred_before === undefined || d.occurred_at <= args.occurred_before))
      .map((d) => ({ ...d, score: scores.get(d._id) }));
  },
});
```

### chunks:fetchResults (internalQuery)

```typescript
export const fetchResults = internalQuery({
  args: { ids: v.array(v.id("semanticChunks")) },
  handler: async (ctx, args) => {
    const out = [];
    for (const id of args.ids) {
      const doc = await ctx.db.get("semanticChunks", id);
      if (doc === null || !doc.active) continue;  // tombstone re-check
      const { embedding, ...meta } = doc;          // never return vectors
      out.push(meta);
    }
    return out;
  },
});
```

---

## Python Integration

```python
from convex import ConvexClient

client = ConvexClient(deployment_url)
client.set_admin_auth(deploy_key)  # access internal functions

# Upsert (from Celery worker, sync is fine)
client.mutation("chunks:upsertBatch", {"chunks": chunk_payloads})

# Search (from FastAPI async route, wrap in thread)
import asyncio
results = await asyncio.to_thread(
    client.action, "chunks:search",
    {"vector": query_vector, "owner_id": owner_id, "embedding_version": "v1", "limit": 32}
)
```

**HTTP API fallback** (for async without thread wrapping):
```python
POST <CONVEX_URL>/api/action
Authorization: Convex <deploy_key>
{"path": "chunks:search", "args": {...}, "format": "json"}
```

---

## PostgreSQL Outbox Pattern

### Write Path

```
1. PG transaction: INSERT interaction_event + INSERT semantic_index_outbox (op='upsert')
2. Both commit atomically (FR-8.5)
3. Celery worker: SELECT ... FOR UPDATE SKIP LOCKED
4. Load interaction, chunk text deterministically
5. Batch OpenRouter embeddings (text-embedding-3-small, 1536 dims)
6. Call Convex chunks:upsertBatch
7. UPDATE outbox SET status='done'
```

### Delete Path

```
1. PG transaction: UPDATE interaction_event SET is_deleted=true + INSERT outbox (op='tombstone')
2. Celery worker: call Convex chunks:tombstoneInteraction
3. Periodic purge: chunks:purgeTombstoned (older than grace window)
```

### Reindex Path

```
1. Bump ACTIVE_EMBEDDING_VERSION config (e.g. "v1" → "v2")
2. INSERT INTO outbox SELECT interaction_id, new_version, 'upsert' FROM interaction_event WHERE is_deleted=false
3. Worker processes new version chunks alongside old
4. Flip config when backfill drains
5. Purge old-version chunks
```

---

## Limits

| Constraint | Value |
|-----------|-------|
| Vector dimensions | 1536 (text-embedding-3-small) |
| filterFields per index | ≤16 (using 2: owner_scope, source) |
| Vector indexes per table | ≤4 (using 1) |
| Filter expressions per search | ≤64 |
| Search limit | 1–256 (default 32) |
| Filter type | equality / OR only (no ranges) |
| Doc size | ~1 MiB (1536 float64s ≈ 12 KiB) |
| Upsert batch | ≤50 chunks per mutation call |
