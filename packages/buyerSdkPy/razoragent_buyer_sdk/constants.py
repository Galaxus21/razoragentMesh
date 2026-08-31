"""Protocol constants for RazorAgent Buyer SDK."""

# Identity & Cryptography Constants
didPrefix: str = "did:agent:"
keyHexLength: int = 64
signatureHexLength: int = 128
utf8Encoding: str = "utf-8"

# Currency & Financial Constants
defaultCurrency: str = "INR"
basisPointsDivisor: int = 10000
microFeePerTurnPaise: int = 50
defaultInitialEscrowHoldPaise: int = 5000

# Temporal & Validity Windows
defaultIntentValiditySeconds: int = 86400
defaultLockTtlSeconds: int = 60
minLockTtlSeconds: int = 10
maxLockTtlSeconds: int = 300
maxClockDriftSeconds: int = 5
futureClockDriftSeconds: int = 60
powChallengeTtlSeconds: int = 300

# Proof of Work (PoW) Constants
defaultPowDifficulty: int = 4
escalatedPowDifficulty: int = 5
maxPowSolveIterations: int = 10000000

# Quantity Constraints
minOrderQuantity: int = 1
maxOrderQuantity: int = 10000

# HTTP Headers
headerPowChallenge: str = "X-Mesh-Pow-Challenge"
headerPowSolution: str = "X-Mesh-Pow-Solution"
headerEscrowToken: str = "X-Mesh-Escrow-Token"
headerBuyerAgentDid: str = "X-Buyer-Agent-Did"
headerAuthenticate: str = "WWW-Authenticate"
headerContentType: str = "Content-Type"
headerAccept: str = "Accept"
mimeTypeJson: str = "application/json"
authHeaderPrefixX402: str = "x402-INR"

# Gateway & Service Endpoint Paths
endpointMeshChallenge: str = "/api/v1/mesh/challenge"
endpointMeshEscrow: str = "/api/v1/mesh/escrow"
endpointMeshEscrowRelease: str = "/api/v1/mesh/escrow/release"
endpointMeshNegotiate: str = "/api/v1/mesh/negotiate"
endpointPriceDropAlerts: str = "/api/v1/alerts/price-drop"
endpointSettlementExecute: str = "/api/v1/settlement/execute"
endpointLiveSkuQuote: str = "/api/v1/quote"
endpointInventoryLock: str = "/api/v1/lock"

# Default Network Timeouts
defaultRequestTimeoutSeconds: float = 30.0
defaultConnectTimeoutSeconds: float = 10.0

__all__ = [
    "authHeaderPrefixX402",
    "basisPointsDivisor",
    "defaultConnectTimeoutSeconds",
    "defaultCurrency",
    "defaultInitialEscrowHoldPaise",
    "defaultIntentValiditySeconds",
    "defaultLockTtlSeconds",
    "defaultPowDifficulty",
    "defaultRequestTimeoutSeconds",
    "didPrefix",
    "endpointInventoryLock",
    "endpointLiveSkuQuote",
    "endpointMeshChallenge",
    "endpointMeshEscrow",
    "endpointMeshEscrowRelease",
    "endpointMeshNegotiate",
    "endpointPriceDropAlerts",
    "endpointSettlementExecute",
    "escalatedPowDifficulty",
    "futureClockDriftSeconds",
    "headerAccept",
    "headerAuthenticate",
    "headerBuyerAgentDid",
    "headerContentType",
    "headerEscrowToken",
    "headerPowChallenge",
    "headerPowSolution",
    "keyHexLength",
    "maxClockDriftSeconds",
    "maxLockTtlSeconds",
    "maxOrderQuantity",
    "maxPowSolveIterations",
    "microFeePerTurnPaise",
    "mimeTypeJson",
    "minLockTtlSeconds",
    "minOrderQuantity",
    "powChallengeTtlSeconds",
    "signatureHexLength",
    "utf8Encoding",
]
