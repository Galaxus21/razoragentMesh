"""Rubinstein-Stahl bounded bargaining state machine for Layer 2 negotiation."""

from typing import List, Optional

from razoragentMesh.packages.mandateEngine.verification.arithmeticEnclave import validateIntegerPaise
from ..constants.negotiationConstants import (
    maxNegotiationTurns,
    microFeePerTurnPaise,
    minConcessionPaise,
)
from ..gatewayExceptions import (
    NegotiationExhaustedException,
)
from ..schemas.bidRequestSchema import (
    NegotiationStatus,
    NegotiationStepResult,
)
from .convergenceChecker import (
    checkConvergence,
    computeSpread,
    validateMonotonicity,
)
from .marginEvaluator import computeSellerCounterAsk


class RubinsteinStahlNegotiator:
    """Rubinstein-Stahl bounded bargaining state machine with x402 micro-metering."""

    def __init__(
        self,
        skuId: str,
        quantity: int,
        escrowBalancePaise: int,
        sellerCostFloorPaise: Optional[int] = None,
    ) -> None:
        validateIntegerPaise(quantity, "quantity")
        validateIntegerPaise(escrowBalancePaise, "escrowBalancePaise")
        self.skuId = skuId
        self.quantity = quantity
        self.escrowBalancePaise = escrowBalancePaise
        self.sellerCostFloorPaise = sellerCostFloorPaise
        self.cumulativeMicroFeesPaise = 0
        self.turnHistory: List[NegotiationStepResult] = []
        self.status = NegotiationStatus.IN_PROGRESS

    def _validateMonotonicity(self, buyerBidPaise: int, sellerAskPaise: int) -> None:
        """Enforces monotonic concession rules for buyer and seller."""
        if not self.turnHistory:
            return
        lastTurn = self.turnHistory[-1]
        validateMonotonicity(
            currentBuyerBidPaise=buyerBidPaise,
            currentSellerAskPaise=sellerAskPaise,
            previousBuyerBidPaise=lastTurn.buyerBidPaise,
            previousSellerAskPaise=lastTurn.sellerAskPaise,
        )

    def executeTurn(
        self,
        turnNumber: int,
        buyerBidPaise: int,
        sellerAskPaise: int,
    ) -> NegotiationStepResult:
        """Executes a single negotiation turn, debits micro-fee, and evaluates convergence."""
        validateIntegerPaise(buyerBidPaise, "buyerBidPaise")
        validateIntegerPaise(sellerAskPaise, "sellerAskPaise")
        validateIntegerPaise(turnNumber, "turnNumber")

        if turnNumber > maxNegotiationTurns:
            self.status = NegotiationStatus.NEGOTIATION_EXHAUSTED
            raise NegotiationExhaustedException("Maximum negotiation turns exceeded")

        self._validateMonotonicity(buyerBidPaise, sellerAskPaise)

        self.escrowBalancePaise -= microFeePerTurnPaise
        self.cumulativeMicroFeesPaise += microFeePerTurnPaise

        spread = computeSpread(sellerAskPaise, buyerBidPaise)
        converged = checkConvergence(buyerBidPaise, sellerAskPaise)

        if converged:
            self.status = NegotiationStatus.CONVERGED
        elif turnNumber == maxNegotiationTurns:
            self.status = NegotiationStatus.NEGOTIATION_EXHAUSTED

        stepResult = NegotiationStepResult(
            turnNumber=turnNumber,
            buyerBidPaise=buyerBidPaise,
            sellerAskPaise=sellerAskPaise,
            spreadPaise=spread,
            isConverged=converged,
            cumulativeMicroFeesPaise=self.cumulativeMicroFeesPaise,
        )
        self.turnHistory.append(stepResult)
        return stepResult

    def computeSellerCounterAsk(
        self,
        initialAskPaise: int,
        buyerBidPaise: int,
        turnIndex: int,
    ) -> int:
        """Calculates deterministic seller concession based on turn progression."""
        return computeSellerCounterAsk(
            initialAskPaise=initialAskPaise,
            buyerBidPaise=buyerBidPaise,
            turnIndex=turnIndex,
            stepConcessionPaise=minConcessionPaise,
            costFloorPaise=self.sellerCostFloorPaise,
        )


__all__ = [
    "NegotiationStatus",
    "NegotiationStepResult",
    "RubinsteinStahlNegotiator",
]
