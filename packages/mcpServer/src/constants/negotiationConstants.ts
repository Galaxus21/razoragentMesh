// Config for the negotiate_price tool -- the buyer half of the x402-INR negotiation protocol.
//
// Why this exists: the x402-INR gateway has run alternating-offer negotiation over HTTP since it
// was built (POST /api/v1/mesh/negotiate, gated by proof-of-work and a micro-escrow debit per
// turn), but nothing on the MCP surface could reach it. An external agent could buy at list price and
// nothing else, and the dashboard's Negotiation Chart only ever rendered seeded rows because
// BID_TURN_COMPLETED was never emitted by a live run.
//
// The route strings must stay identical to `x402Gateway/src/constants/negotiationConstants.py`
// and to `buyerSdkTs/src/sdkConstants.ts`. Resolved at call time, not module load, so the compose
// service name works inside Docker and localhost works for a developer outside it.

export const x402GatewayUrlEnvVar = "X402_GATEWAY_URL";
export const fallbackX402GatewayUrl = "http://localhost:4003";

export const powChallengePath = "/api/v1/mesh/challenge";
export const escrowCreatePath = "/api/v1/mesh/escrow";
export const escrowReleasePath = "/api/v1/mesh/escrow/release";
export const negotiateTurnPath = "/api/v1/mesh/negotiate";

// Mirrors x402Gateway/src/constants/negotiationConstants.py. A divergence here does not corrupt
// anything -- the gateway is authoritative and refuses a turn past its own limit -- but it would
// make this tool promise a turn budget the server will not honour.
export const maxNegotiationTurns = 5;
export const microFeePerTurnPaise = 50;
export const initialEscrowPoolPaise = 5000;
export const minConcessionPaise = 500;
export const basisPointsDivisor = 10000;

// The headers the gateway reads. Same three the buyer SDK's generatePowHeaders emits.
export const headerPowChallenge = "X-Mesh-Pow-Challenge";
export const headerPowSolution = "X-Mesh-Pow-Solution";
export const headerEscrowToken = "X-Mesh-Escrow-Token";

// How much of the open spread each side gives up per turn, floored at minConcessionPaise.
//
// The gateway ships computeSellerCounterAsk (negotiation/marginEvaluator.py), whose ladder is a
// FLAT minConcessionPaise * turnIndex -- so a seller concedes at most 500 * 5 = 2500 paise over a
// whole negotiation. On a four-figure item that is a 0.25% move and the two sides never meet, so
// every negotiation would report EXHAUSTED. minConcessionPaise is documented in that file as a
// MINIMUM step, not the step, so conceding a share of the live spread and flooring at the minimum
// honours the constant rather than contradicting it. The gateway itself is indifferent: it takes
// both numbers from the request and only enforces that the bid never falls and the ask never rises.
export const sellerConcessionRateBps = 3000;
export const buyerConcessionRateBps = 3000;

// A negotiation is a single tool call, so the whole loop has to finish inside one MCP request.
// Difficulty is per-IP dynamic in the gateway's anti-spam shield, so a solve is not a fixed cost:
// this bounds the total, and the tool returns the turns it did complete rather than hanging.
export const powSolveBudgetMs = 15_000;
export const negotiationHttpTimeoutMs = 10_000;

// Refused by the request schema before any escrow is created or any fee is charged.
export const errorCeilingBelowOpeningBid =
  "max_unit_price_paise must be greater than or equal to opening_bid_paise";
export const errorUnknownSku =
  "negotiate_price could not find that sku_id in the catalog. Call browse_catalog or " +
  "search_catalog first, then negotiate on a sku_id the mesh actually sells.";

export function resolveX402GatewayUrl(): string {
  const configured = process.env[x402GatewayUrlEnvVar]?.trim();
  return configured && configured.length > 0 ? configured : fallbackX402GatewayUrl;
}
