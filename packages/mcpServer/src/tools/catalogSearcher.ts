// Tool 4: search_catalog -- natural-language product discovery.
//
// Why this exists: the mesh had no discovery primitive. An agent could quote a SKU id someone
// had already handed it, but nothing could answer "find me an office chair", so a third-party
// agent could not start a purchase on its own. This is the entry point to every other tool.
//
// The ranking runs in merchantApi, which owns the embedding model and the Qdrant client; this
// package is TypeScript and has no embedder. The tool forwards and preserves the honesty
// fields, so an agent is told when a ranking is not actually semantic.

import {
  resolveMerchantApiUrl,
  catalogSearchPath,
  catalogSearchTimeoutMs,
  degradedEmbeddingMode
} from "../constants/catalogSearchConstants.js";
import { catalogSearchRequestSchema } from "../schemas/catalogSearchSchema.js";

interface UpstreamSearchResponse {
  readonly results?: ReadonlyArray<Record<string, unknown>>;
  readonly resultCount?: number;
  readonly embeddingMode?: string;
  readonly rankingQuality?: string;
  readonly indexAvailable?: boolean;
}

/**
 * Ranks catalog entries against a plain-language description.
 *
 * A failure is thrown rather than returned as an empty list: "nothing matched" and "search is
 * down" are different answers, and an agent told the former would conclude the product does
 * not exist and give up.
 */
export async function searchCatalog(rawArguments: unknown): Promise<Record<string, unknown>> {
  const { queryText, limit } = catalogSearchRequestSchema.parse(rawArguments);
  const url = `${resolveMerchantApiUrl()}${catalogSearchPath}`;

  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ queryText, limit }),
      signal: AbortSignal.timeout(catalogSearchTimeoutMs)
    });
  } catch (error: unknown) {
    const detail = error instanceof Error ? error.message : String(error);
    throw new Error(`Catalog search is unavailable at ${url}: ${detail}`);
  }

  if (!response.ok) {
    throw new Error(`Catalog search failed with HTTP ${response.status}`);
  }

  const body = (await response.json()) as UpstreamSearchResponse;
  const embeddingMode = body.embeddingMode ?? degradedEmbeddingMode;

  return {
    query_text: queryText,
    results: body.results ?? [],
    result_count: body.resultCount ?? (body.results?.length ?? 0),
    // Passed through deliberately. An agent choosing what to buy should know when the ranking
    // came from a character hash rather than a language model, because in that mode the order
    // carries no meaning and picking the top hit is not a reasoned choice.
    embedding_mode: embeddingMode,
    ranking_quality: body.rankingQuality ?? "",
    index_available: body.indexAvailable ?? false
  };
}
