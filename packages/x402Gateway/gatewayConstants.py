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
