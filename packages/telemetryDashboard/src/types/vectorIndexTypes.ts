// Wire shapes for the vector index panel.
//
// Declared here rather than exported from the route module so a client component can import the
// type without pulling a server route into its module graph.

export interface VectorIndexPoint {
  readonly pointId: string;
  readonly skuId: string;
  readonly title: string;
  readonly brand: string | null;
  readonly category: string;
  readonly pricePaise: number | null;
  readonly availableStock: number | null;
  readonly hsnCode: string | null;
  // Coordinates in [0, 1] on the two leading principal components of the real embeddings.
  readonly x: number;
  readonly y: number;
}

export interface VectorIndexResponse {
  readonly collection: string;
  readonly reachable: boolean;
  readonly status: string | null;
  readonly pointCount: number;
  readonly indexedVectorCount: number | null;
  readonly dimension: number | null;
  readonly distance: string | null;
  readonly hnswM: number | null;
  readonly hnswEfConstruct: number | null;
  readonly explainedVariance: readonly [number, number];
  readonly points: readonly VectorIndexPoint[];
  readonly detail?: string;
}

/** One ranked hit from POST /api/v1/catalog/search, as the merchant API returns it. */
export interface CatalogSearchHit {
  readonly skuId?: string | null;
  readonly title?: string | null;
  readonly category?: string | null;
  readonly baseUnitPricePaise?: number | null;
  readonly availableStock?: number | null;
  readonly hsnCode?: string | null;
  readonly score?: number | null;
}

export interface CatalogSearchResponse {
  readonly results: readonly CatalogSearchHit[];
  readonly resultCount: number;
  // "model" or "hash". A ranking produced in hash mode is not semantic similarity, and the page
  // must say so rather than presenting the scores as meaning.
  readonly embeddingMode: string;
  readonly rankingQuality: string;
  readonly indexAvailable: boolean;
}

export interface OosHealingResponse {
  readonly healed: boolean;
  readonly failedSkuId: string;
  readonly substituteSkuId?: string | null;
  readonly substitutePayload?: Record<string, unknown> | null;
  readonly cosineScore?: number | null;
  readonly healingDurationMs: number;
  readonly embeddingMode: string;
  readonly reason?: string | null;
}
