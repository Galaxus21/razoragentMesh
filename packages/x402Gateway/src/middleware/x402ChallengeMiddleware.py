"""x402-INR HTTP challenge and payment negotiation middleware."""

from typing import Any, Callable, Optional
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from ..constants.negotiationConstants import (
    headerAuthenticate,
    headerEscrowToken,
    initialEscrowPoolPaise,
    microFeePerTurnPaise,
    protocolName,
)
from ..escrow.microEscrowClient import MicroEscrowClient


class X402ChallengeMiddleware(BaseHTTPMiddleware):
    """FastAPI/Starlette middleware enforcing x402-INR micro-escrow header and debiting."""

    def __init__(
        self,
        app: Any,
        escrowClient: MicroEscrowClient,
        protectedPaths: Optional[list[str]] = None,
    ) -> None:
        super().__init__(app)
        self.escrowClient = escrowClient
        self.protectedPaths = protectedPaths or ["/api/v1/mesh/negotiate"]

    def _isPathProtected(self, path: str) -> bool:
        """Determines if the request path requires x402 micro-escrow authentication."""
        return any(path.startswith(p) for p in self.protectedPaths)

    def _build402ChallengeResponse(self) -> JSONResponse:
        """Constructs canonical HTTP 402 Payment Required response."""
        challengeHeaderValue = (
            f'{protocolName} tokenCostPaise="{microFeePerTurnPaise}", '
            f'escrowEndpoint="/api/v1/mesh/escrow"'
        )
        body = {
            "status": 402,
            "error": "PAYMENT_REQUIRED",
            "protocol": protocolName,
            "tokenCostPaise": microFeePerTurnPaise,
            "escrowBlockRequiredPaise": initialEscrowPoolPaise,
            "message": "Dynamic negotiation requires ₹0.50 micro-escrow debit per turn",
        }
        return JSONResponse(
            status_code=402,
            content=body,
            headers={headerAuthenticate: challengeHeaderValue},
        )

    async def dispatch(self, request: Request, call_next: Callable[..., Any]) -> Response:
        """Intercepts requests to protected negotiation routes and verifies micro-escrow."""
        if not self._isPathProtected(request.url.path):
            return await call_next(request)

        escrowToken = request.headers.get(headerEscrowToken)
        if not escrowToken:
            return self._build402ChallengeResponse()

        try:
            session = await self.escrowClient.getSession(escrowToken)
            if session.remainingBalancePaise < microFeePerTurnPaise:
                return self._build402ChallengeResponse()
            request.state.escrowSession = session
        except Exception:
            return self._build402ChallengeResponse()

        response = await call_next(request)
        return response


__all__ = [
    "X402ChallengeMiddleware",
]
