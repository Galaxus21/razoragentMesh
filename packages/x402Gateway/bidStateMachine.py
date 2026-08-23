"""Rubinstein-Stahl bounded bargaining state machine for Layer 2 negotiation."""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from razoragentMesh.packages.mandateEngine.arithmeticEnclave import validateIntegerPaise
from razoragentMesh.packages.x402Gateway.gatewayConstants import (
    maxNegotiationTurns,
    microFeePerTurnPaise,
    minConcessionPaise,
    sellerMarginFloorBps,
)
from razoragentMesh.packages.x402Gateway.gatewayExceptions import (
    NegotiationExhaustedException,
    NonMonotonicConcessionViolation,
)


class NegotiationStatus(str, Enum):
    """Lifecycle statuses for negotiation session."""

    IN_PROGRESS = "IN_PROGRESS"
    CONVERGED = "CONVERGED"
    REJECTED = "REJECTED"
    NEGOTIATION_EXHAUSTED = "NEGOTIATION_EXHAUSTED"


class NegotiationStepResult(BaseModel):
    """Step result recorded at each negotiation turn."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    turnNumber: int = Field(ge=1, le=maxNegotiationTurns)
    buyerBidPaise: int = Field(gt=0)
    sellerAskPaise: int = Field(gt=0)
    spreadPaise: int = Field(ge=0)
    isConverged: bool
    cumulativeMicroFeesPaise: int = Field(gt=0)


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
        if buyerBidPaise < lastTurn.buyerBidPaise:
            raise NonMonotonicConcessionViolation("Buyer bid cannot decrease")
        if sellerAskPaise > lastTurn.sellerAskPaise:
            raise NonMonotonicConcessionViolation("Seller ask cannot increase")

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

        spread = max(0, sellerAskPaise - buyerBidPaise)
        converged = buyerBidPaise >= sellerAskPaise

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
        stepConcession = minConcessionPaise * turnIndex
        counterAsk = max(initialAskPaise - stepConcession, buyerBidPaise)
        if self.sellerCostFloorPaise is not None:
            counterAsk = max(counterAsk, self.sellerCostFloorPaise)
        return counterAsk
