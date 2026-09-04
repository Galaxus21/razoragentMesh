// Shared constants for the vector index panel.
//
// The collection name is Qdrant's, declared in packages/merchantApi/src/constants/
// merchantConstants.py as defaultCollectionName. It is repeated rather than imported because
// the dashboard must not reach into a sibling package -- `next build` typechecks this tree, and
// a cross-package import breaks the image build. If that constant moves, this one moves with it.

export const catalogCollectionName = "razoragent_catalog";

export const vectorScrollPageSize = 256;
export const vectorUpstreamTimeoutMs = 10_000;

// What the merchant API reports about which producer made the vectors. 'model' is the
// all-MiniLM-L6-v2 embedding; 'hash' is the deterministic character-hash fallback used when
// fastembed cannot load, whose cosine scores are NOT semantic similarity.
export const embeddingModeModel = "model";
export const embeddingModeHash = "hash";

export const defaultSearchLimit = 5;
export const maxSearchLimit = 20;

// Layer 3's defaults, matching oosHealingRoute.py so the healing panel shows the thresholds the
// mesh will actually apply. The price ceiling is the one that usually decides the outcome: a
// no_qualifying_substitute is far more often a 15%-delta rejection than a similarity miss.
export const defaultSimilarityFloor = 0.85;
export const defaultMaxPriceDeltaPercent = 15;
