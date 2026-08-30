import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

export default defineSchema({
  semanticChunks: defineTable({
    chunk_key: v.string(),
    owner_id: v.string(),
    owner_scope: v.string(),
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
