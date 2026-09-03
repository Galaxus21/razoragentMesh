// Wire schema for search_catalog. See establishDelegationSchema.ts for why the tools' schemas
// live here rather than inline beside their tools.
//
// This tool is deliberately LENIENT where the other seven are strict, and the leniency is
// preserved exactly rather than tidied away, because agents already call it successfully:
//
//   - Both `query_text` and `queryText` name the same value. Tool inputs across this package are
//     snake_case, but the merchantApi endpoint behind this one is camelCase, and agents have
//     been observed sending either.
//   - `limit` is CLAMPED into [1, maxSearchLimit] rather than rejected. A request for 500 hits
//     is a reasonable thing for an agent to ask; refusing it outright would fail a call that has
//     an obvious correct answer.
//
// A plain `z.object(...)` would have started rejecting both. The preprocess step below keeps the
// existing contract and the object schema behind it is the safety net.

import { z } from "zod";
import {
  defaultSearchLimit,
  errorEmptyQueryText,
  maxSearchLimit
} from "../constants/catalogSearchConstants.js";

/** What an agent may send. Both spellings of the query are accepted. */
export interface CatalogSearchArguments {
  readonly query_text?: string;
  readonly queryText?: string;
  /** Accepted alias. Agents guess this spelling, and a refusal over a field name reads as a bug. */
  readonly query?: string;
  readonly limit?: number;
}

const minSearchLimit = 1;

const normalizedSearchSchema = z.object({
  queryText: z.string().min(1),
  limit: z.number().int().min(minSearchLimit).max(maxSearchLimit)
});

/**
 * Resolves the requested page size.
 *
 * A non-numeric limit falls back to the default, as it always has. NaN now does too: it is a
 * number by typeof, so it previously survived Math.trunc/max/min as NaN and serialised to
 * `null` on the wire, which the catalog endpoint rejects. No input that works today changes.
 */
function resolveLimit(requested: unknown): number {
  if (typeof requested !== "number" || Number.isNaN(requested)) {
    return defaultSearchLimit;
  }
  const truncated = Math.trunc(requested);
  return Math.min(Math.max(truncated, minSearchLimit), maxSearchLimit);
}

function normalizeSearchArguments(rawArguments: unknown): unknown {
  const args = (rawArguments ?? {}) as CatalogSearchArguments;
  // `query` is accepted alongside the two documented spellings because a live buyer agent
  // guessed it and was refused for a field name rather than for anything about its search.
  const queryText = (args.query_text ?? args.queryText ?? args.query ?? "").trim();
  // Thrown here rather than left to zod so the agent reads the same sentence it always has,
  // instead of a ZodError naming a field it never sent.
  if (queryText.length === 0) {
    throw new Error(errorEmptyQueryText);
  }
  return { queryText, limit: resolveLimit(args.limit) };
}

export const catalogSearchRequestSchema = z.preprocess(
  normalizeSearchArguments,
  normalizedSearchSchema
);

/** The normalized request, after both spellings collapse and the limit is clamped. */
export type CatalogSearchRequest = z.infer<typeof normalizedSearchSchema>;

export const catalogSearchHitSchema = z
  .object({
    skuId: z.string(),
    title: z.string(),
    category: z.string(),
    baseUnitPricePaise: z.number().int().min(0),
    availableStock: z.number().int().min(0),
    gstRatePercent: z.number(),
    hsnCode: z.string(),
    merchantDid: z.string(),
    score: z.number()
  })
  // The ranking is produced by merchantApi, which owns the payload; an added field must not
  // fail a search that otherwise worked.
  .passthrough();

export type CatalogSearchHitSchema = z.infer<typeof catalogSearchHitSchema>;

export const catalogSearchResponseSchema = z.object({
  query_text: z.string().min(1),
  results: z.array(catalogSearchHitSchema),
  result_count: z.number().int().min(0),
  // Passed through deliberately. 'hash' means the ranking came from a character hash rather than
  // a language model, so its order carries no meaning and picking the top hit is not a reasoned
  // choice. An agent acting on these results has to be told which produced them.
  embedding_mode: z.string(),
  ranking_quality: z.string(),
  index_available: z.boolean()
});

export type CatalogSearchResponse = z.infer<typeof catalogSearchResponseSchema>;
