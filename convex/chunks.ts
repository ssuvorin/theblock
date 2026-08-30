import {
  actionGeneric as action,
  mutationGeneric as mutation,
  queryGeneric as query,
  makeFunctionReference,
} from "convex/server";
import { GenericId, v } from "convex/values";

const DIMENSIONS = 1536;
type SearchDocument = Record<string, unknown> & {
  _id: GenericId<"semanticChunks">;
  source: string;
  occurred_at: number;
};
const MAX_BATCH = 50;
const chunkValue = v.object({
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
});

function activeScope(ownerId: string, version: string): string {
  return `${ownerId}:${version}:active`;
}

function assertVector(vector: number[]): void {
  if (vector.length !== DIMENSIONS) {
    throw new Error(`embedding must have ${DIMENSIONS} dimensions`);
  }
}

export const upsertBatch = mutation({
  args: { chunks: v.array(chunkValue) },
  handler: async (ctx, args) => {
    if (args.chunks.length > MAX_BATCH) {
      throw new Error(`upsertBatch accepts at most ${MAX_BATCH} chunks`);
    }
    let changed = 0;
    for (const chunk of args.chunks) {
      assertVector(chunk.embedding);
      const expectedScope = activeScope(chunk.owner_id, chunk.embedding_version);
      if (chunk.owner_scope !== expectedScope) {
        throw new Error("owner_scope does not match owner and embedding version");
      }
      const existing = await ctx.db
        .query("semanticChunks")
        .withIndex("by_chunk_key", (query) =>
          (query as any)
            .eq("chunk_key", chunk.chunk_key)
            .eq("embedding_version", chunk.embedding_version),
        )
        .unique();
      if (existing === null) {
        await ctx.db.insert("semanticChunks", {
          ...chunk,
          active: true,
          indexed_at: Date.now(),
        });
        changed += 1;
      } else if (existing.text_hash !== chunk.text_hash || !existing.active) {
        await ctx.db.replace(existing._id, {
          ...chunk,
          active: true,
          indexed_at: Date.now(),
        });
        changed += 1;
      }
    }
    return changed;
  },
});

export const tombstoneInteraction = mutation({
  args: { owner_id: v.string(), interaction_id: v.string() },
  handler: async (ctx, args) => {
    const documents = await ctx.db
      .query("semanticChunks")
      .withIndex("by_interaction", (query) =>
        (query as any)
          .eq("owner_id", args.owner_id)
          .eq("interaction_id", args.interaction_id),
      )
      .collect();
    const tombstonedAt = Date.now();
    for (const document of documents) {
      await ctx.db.patch(document._id, {
        active: false,
        owner_scope: `${document.owner_id}:${document.embedding_version}:deleted`,
        tombstoned_at: tombstonedAt,
      });
    }
    return documents.length;
  },
});

export const fetchResults = query({
  args: { ids: v.array(v.id("semanticChunks")) },
  handler: async (ctx, args) => {
    const output = [];
    for (const id of args.ids) {
      const document = await ctx.db.get(id);
      if (document === null || !document.active) {
        continue;
      }
      const { embedding, ...metadata } = document;
      void embedding;
      output.push(metadata);
    }
    return output;
  },
});

const fetchResultsReference = makeFunctionReference<
  "query",
  { ids: GenericId<"semanticChunks">[] },
  SearchDocument[]
>("chunks:fetchResults");

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
    assertVector(args.vector);
    const limit = Math.max(1, Math.min(args.limit ?? 32, 256));
    const ownerScope = activeScope(args.owner_id, args.embedding_version);
    const results = await ctx.vectorSearch("semanticChunks", "by_embedding", {
      vector: args.vector,
      limit,
      filter: (query) => query.eq("owner_scope", ownerScope),
    });
    const documents = await ctx.runQuery(fetchResultsReference, {
      ids: results.map((result) => result._id),
    });
    const scores = new Map(results.map((result) => [result._id, result._score]));
    return documents
      .filter(
        (document) =>
          (args.sources === undefined || args.sources.includes(document.source)) &&
          (args.occurred_after === undefined ||
            document.occurred_at >= args.occurred_after) &&
          (args.occurred_before === undefined ||
            document.occurred_at <= args.occurred_before),
      )
      .map((document) => ({ ...document, score: scores.get(document._id) }));
  },
});
