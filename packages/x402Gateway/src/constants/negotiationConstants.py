"""Gateway constants for Layer 2 x402-INR negotiation protocol."""

# Negotiation Turn Limits & Concessions
maxNegotiationTurns: int = 5
minConcessionPaise: int = 500  # ₹5.00 minimum concession step
sellerMarginFloorBps: int = 500  # 5.00% minimum profit margin above wholesale
microFeePerTurnPaise: int = 50  # ₹0.50 per turn
initialEscrowPoolPaise: int = 5000  # ₹50.00 initial pre-auth block

# Proof-of-Work Parameters
powLeadingZeros: int = 4
requiredLeadingPrefix: str = "0000"
powChallengeTtlSeconds: int = 300  # 5 minutes challenge validity
powReplayCacheTtlSeconds: int = 600  # 10 minutes replay tracking

# Protocol Identifiers & Headers
protocolName: str = "x402-INR"
currencyInr: str = "INR"
defaultGstRatePercent: int = 18
headerPowChallenge: str = "X-Mesh-Pow-Challenge"
headerPowSolution: str = "X-Mesh-Pow-Solution"
headerEscrowToken: str = "X-Mesh-Escrow-Token"
headerAuthenticate: str = "WWW-Authenticate"
headerBuyerAgentDid: str = "X-Buyer-Agent-Did"

# Default Timing
defaultSessionTtlSeconds: int = 600

# Basis Points Divisor
basisPointsDivisor: int = 10000

# Default Gateway Secrets
defaultGatewaySecret: str = "rzp_test_escrow_secret_key_32bytes"

# Network & Host Defaults
defaultClientHost: str = "127.0.0.1"

# Endpoint Paths
endpointHealth: str = "/api/v1/mesh/health"
endpointChallenge: str = "/api/v1/mesh/challenge"
endpointEscrow: str = "/api/v1/mesh/escrow"
endpointEscrowRelease: str = "/api/v1/mesh/escrow/release"
endpointNegotiate: str = "/api/v1/mesh/negotiate"

__all__ = [
    "basisPointsDivisor",
    "currencyInr",
    "defaultClientHost",
    "defaultGatewaySecret",
    "defaultGstRatePercent",
    "defaultSessionTtlSeconds",
    "endpointChallenge",
    "endpointEscrow",
    "endpointEscrowRelease",
    "endpointHealth",
    "endpointNegotiate",
    "headerAuthenticate",
    "headerBuyerAgentDid",
    "headerEscrowToken",
    "headerPowChallenge",
    "headerPowSolution",
    "initialEscrowPoolPaise",
    "maxNegotiationTurns",
    "microFeePerTurnPaise",
    "minConcessionPaise",
    "powChallengeTtlSeconds",
    "powLeadingZeros",
    "powReplayCacheTtlSeconds",
    "protocolName",
    "requiredLeadingPrefix",
    "sellerMarginFloorBps",
]
