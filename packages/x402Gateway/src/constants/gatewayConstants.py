"""HTTP gateway constants, status codes, headers, and metadata."""

# Application & Gateway Metadata
defaultGatewayTitle: str = "RazorAgent x402 Gateway"
defaultGatewayVersion: str = "2.0.0"
defaultGatewayDescription: str = (
    "HTTP 402-INR micro-metered negotiation and AST compilation service"
)

# Basis Points Divisor
basisPointsDivisor: int = 10000

# HTTP Status Codes
httpStatusOk: int = 200
httpStatusCreated: int = 201
httpStatusBadRequest: int = 400
httpStatusPaymentRequired: int = 402
httpStatusForbidden: int = 403
httpStatusNotFound: int = 404
httpStatusConflict: int = 409
httpStatusUnprocessableEntity: int = 422
httpStatusInternalServerError: int = 500

# Standard & Protocol HTTP Headers
headerAuthenticate: str = "WWW-Authenticate"
headerBuyerAgentDid: str = "X-Buyer-Agent-Did"
headerContentType: str = "Content-Type"
headerEscrowToken: str = "X-Mesh-Escrow-Token"
headerPowChallenge: str = "X-Mesh-Pow-Challenge"
headerPowSolution: str = "X-Mesh-Pow-Solution"

# Media Types
mediaTypeJson: str = "application/json"

__all__ = [
    "basisPointsDivisor",
    "defaultGatewayDescription",
    "defaultGatewayTitle",
    "defaultGatewayVersion",
    "headerAuthenticate",
    "headerBuyerAgentDid",
    "headerContentType",
    "headerEscrowToken",
    "headerPowChallenge",
    "headerPowSolution",
    "httpStatusBadRequest",
    "httpStatusConflict",
    "httpStatusCreated",
    "httpStatusForbidden",
    "httpStatusInternalServerError",
    "httpStatusNotFound",
    "httpStatusOk",
    "httpStatusPaymentRequired",
    "httpStatusUnprocessableEntity",
    "mediaTypeJson",
]
