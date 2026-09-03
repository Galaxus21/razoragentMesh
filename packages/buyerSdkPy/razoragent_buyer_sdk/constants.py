"""Protocol constants for RazorAgent Buyer SDK."""

# Identity & Cryptography Constants
didPrefix: str = "did:agent:"
keyHexLength: int = 64
signatureHexLength: int = 128
utf8Encoding: str = "utf-8"

# Currency & Financial Constants
defaultCurrency: str = "INR"
defaultInitialEscrowHoldPaise: int = 5000
# POST /api/v1/mesh/escrow answers 201 Created, not 200. Both are accepted so a gateway
# that ever relaxes to 200 does not break the client, and so that treating the documented
# success code as a failure -- which is what this client used to do -- cannot recur.
escrowCreateSuccessStatuses: frozenset = frozenset({200, 201})

# Temporal & Validity Windows
defaultIntentValiditySeconds: int = 86400
defaultLockTtlSeconds: int = 60

# Proof of Work (PoW) Constants
defaultPowDifficulty: int = 4
maxPowSolveIterations: int = 10000000

# HTTP Headers
headerPowChallenge: str = "X-Mesh-Pow-Challenge"
headerPowSolution: str = "X-Mesh-Pow-Solution"
headerEscrowToken: str = "X-Mesh-Escrow-Token"
headerBuyerAgentDid: str = "X-Buyer-Agent-Did"
headerContentType: str = "Content-Type"
headerAccept: str = "Accept"
mimeTypeJson: str = "application/json"

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
    "defaultCurrency",
    "defaultInitialEscrowHoldPaise",
    "escrowCreateSuccessStatuses",
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
    "headerAccept",
    "headerBuyerAgentDid",
    "headerContentType",
    "headerEscrowToken",
    "headerPowChallenge",
    "headerPowSolution",
    "keyHexLength",
    "maxPowSolveIterations",
    "mimeTypeJson",
    "signatureHexLength",
    "utf8Encoding",
]
