// Config for the search_catalog tool.
//
// Ranking lives in merchantApi because that is where fastembed and the Qdrant client already
// are; this package has no embedder. Resolved at call time rather than module load so the
// compose service name works inside Docker and localhost works for a developer outside it.

export const merchantApiUrlEnvVar = "MERCHANT_API_URL";
export const fallbackMerchantApiUrl = "http://localhost:4002";
export const catalogSearchPath = "/api/v1/catalog/search";

// Thrown verbatim by the request schema. Named here so a test can assert the exact wording an
// agent sees rather than re-typing the string.
export const errorEmptyQueryText = "search_catalog requires a non-empty query_text";

export const defaultSearchLimit = 5;
export const maxSearchLimit = 25;

// Generous: the first search after a cold start pays for the embedding model loading.
export const catalogSearchTimeoutMs = 30_000;

export const catalogHealPath = "/api/v1/catalog/heal-oos";

// Deliberately short, and much shorter than catalogSearchTimeoutMs. This runs on a refusal path
// that has already failed: an agent waiting 30s to be told "out of stock" is worse served than
// one told immediately without a suggestion.
export const catalogHealTimeoutMs = 4_000;

// Assumed when the upstream response omits the field -- the pessimistic choice, so a missing
// value is never mistaken for a confirmed semantic ranking.
export const degradedEmbeddingMode = "hash";

export function resolveMerchantApiUrl(): string {
  const configured = process.env[merchantApiUrlEnvVar]?.trim();
  return configured && configured.length > 0 ? configured : fallbackMerchantApiUrl;
}
