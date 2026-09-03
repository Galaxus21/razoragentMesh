export const defaultCurrency = "INR" as const;
export const didPrefix = "did:agent:";
export const keyHexLength = 64;
export const seedByteLength = 32;
export const signatureHexLength = 128;

// The category a merchant asserts when it does not classify the SKU. Must equal the Python
// spelling in mandateEngine/mandates/cartMandateSchema.py and razoragent_buyer_sdk/mandateModels.py:
// the value lands in the JCS-canonicalized payload, so a divergence makes the same cart hash
// differently in the two SDKs and every cross-SDK signature fails. It is a real string rather
// than an omitted key because Python emits the field always and JSON.stringify drops undefined.
export const uncategorizedCartItemCategory = "uncategorized" as const;

export const defaultIntentValiditySeconds = 86400;
// Matches Python SDK and MCP server (packages/mcpServer/src/constants/protocolConstants.ts:53).
// Both SDKs call the same /api/v1/lock endpoint, so the hold window must match.
export const defaultLockTtlSeconds = 60;
export const defaultPowDifficultyZeros = 4;
export const maxNegotiationTurns = 5;
export const microFeePerTurnPaise = 50;

export const defaultMandateEngineUrl = "http://localhost:8000";
export const defaultMcpServerUrl = "http://localhost:4001";
export const defaultX402GatewayUrl = "http://localhost:4003";

export const endpointQuote = "/api/v1/quote" as const;
export const endpointLock = "/api/v1/lock" as const;
export const endpointSla = "/api/v1/sla" as const;
export const endpointSettlementExecute = "/api/v1/settlement/execute" as const;

export const defaultPurchaseQuantity = 1;
export const defaultSlaWeightGrams = 500;
export const defaultPowChunkSize = 10000;
export const millisPerSecond = 1000;

export const mandateIntentPrefix = "mandate_intent_" as const;
export const mandateCartPrefix = "cart_" as const;
export const mandateExecPrefix = "mandate_exec_" as const;
export const mandateAmendPrefix = "mandate_amend_" as const;
export const mandateCartAmendedPrefix = "cart_amended_" as const;

export const defaultProtocolFeeAccount = "acc_protocol_fees";
export const defaultProtocolFeePaise = 50;

export const hexEncoding = "hex" as const;
export const utf8Encoding = "utf-8" as const;

export const headerPowChallenge = "X-Mesh-Pow-Challenge" as const;
export const headerPowSolution = "X-Mesh-Pow-Solution" as const;
export const headerEscrowToken = "X-Mesh-Escrow-Token" as const;
export const headerBuyerAgentDid = "X-Buyer-Agent-Did" as const;

export const mediaTypeApplicationJson = "application/json" as const;
export const httpMethodGet = "GET" as const;
export const httpMethodPost = "POST" as const;

export const signatureFieldKeys = Object.freeze([
  "userSignature",
  "merchantSignature",
  "agentSignature"
] as const);
