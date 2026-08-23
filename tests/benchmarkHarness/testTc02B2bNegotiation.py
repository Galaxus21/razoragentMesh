import hashlib
import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
import pytest

from razoragentMesh.packages.mandateEngine.arithmeticEnclave import (
    computeCartSettlementTotal,
    computeGstBreakdown,
    computeLineItemTotal,
    validateIntegerPaise,
)
from razoragentMesh.packages.mandateEngine.jcsCanonicalizer import (
    canonicalizeJson,
    computeSha256Digest,
)

# Benchmark Constants
initialBuyerBidPaise = 330000
initialSellerAskPaise = 345000
agreedUnitPricePaise = 335000
negotiationQuantity = 50
gstRatePercent = 18
microFeePerTurnPaise = 50
initialEscrowPoolPaise = 5000
maxAllowedTurns = 5


class NonMonotonicConcessionViolation(Exception):
    """Raised when an agent violates monotonic concession rules."""


class NegotiationStepResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    turnNumber: int = Field(ge=1, le=maxAllowedTurns)
    buyerBidPaise: int = Field(gt=0)
    sellerAskPaise: int = Field(gt=0)
    spreadPaise: int = Field(ge=0)
    isConverged: bool
    cumulativeMicroFeesPaise: int = Field(gt=0)


class CommercialContractAst(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    skuId: str = Field(min_length=1)
    quantity: int = Field(gt=0)
    agreedUnitPricePaise: int = Field(gt=0)
    taxableSubtotalPaise: int = Field(gt=0)
    totalTaxPaise: int = Field(ge=0)
    totalGrossPaise: int = Field(gt=0)
    settlementTurns: int = Field(ge=1)
    buyerAgentDid: str = Field(min_length=1)
    merchantDid: str = Field(min_length=1)
    contractTimestamp: int = Field(gt=0)


class RubinsteinStahlNegotiator:
    """Rubinstein-Stahl bounded bargaining state machine with x402 micro-metering."""

    def __init__(self, skuId: str, quantity: int, escrowBalancePaise: int) -> None:
        self.skuId = skuId
        self.quantity = quantity
        self.escrowBalancePaise = escrowBalancePaise
        self.cumulativeMicroFeesPaise = 0
        self.turnHistory: List[NegotiationStepResult] = []

    def executeTurn(
        self,
        turnNumber: int,
        buyerBidPaise: int,
        sellerAskPaise: int,
    ) -> NegotiationStepResult:
        validateIntegerPaise(buyerBidPaise, "buyerBidPaise")
        validateIntegerPaise(sellerAskPaise, "sellerAskPaise")

        # Monotonicity checks
        if self.turnHistory:
            lastTurn = self.turnHistory[-1]
            if buyerBidPaise < lastTurn.buyerBidPaise:
                raise NonMonotonicConcessionViolation("Buyer bid cannot decrease")
            if sellerAskPaise > lastTurn.sellerAskPaise:
                raise NonMonotonicConcessionViolation("Seller ask cannot increase")

        # Debit x402 micro-metering fee
        self.escrowBalancePaise -= microFeePerTurnPaise
        self.cumulativeMicroFeesPaise += microFeePerTurnPaise

        spread = max(0, sellerAskPaise - buyerBidPaise)
        converged = buyerBidPaise >= sellerAskPaise

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


def compileCommercialContractAst(
    skuId: str,
    quantity: int,
    agreedUnitPrice: int,
    turns: int,
    buyerDid: str,
    merchantDid: str,
    timestamp: int,
) -> tuple[CommercialContractAst, str]:
    """Compiles negotiated terms into immutable AST and computes canonical JCS SHA-256 hash."""
    taxable = computeLineItemTotal(agreedUnitPrice, quantity)
    gst = computeGstBreakdown(taxable, gstRatePercent, isIntraState=True)
    gross = computeCartSettlementTotal(taxable, gst["totalTaxPaise"])

    ast = CommercialContractAst(
        skuId=skuId,
        quantity=quantity,
        agreedUnitPricePaise=agreedUnitPrice,
        taxableSubtotalPaise=taxable,
        totalTaxPaise=gst["totalTaxPaise"],
        totalGrossPaise=gross,
        settlementTurns=turns,
        buyerAgentDid=buyerDid,
        merchantDid=merchantDid,
        contractTimestamp=timestamp,
    )
    canonicalBytes = canonicalizeJson(ast)
    astHash = computeSha256Digest(canonicalBytes)
    return ast, astHash


def testTc02MultiTurnNegotiationConvergence(
    agentKeyFixtures: Dict[str, Any],
) -> None:
    """TC-02: B2B Dynamic Multi-Turn Negotiation — 3-turn Rubinstein-Stahl convergence at ₹3,350."""
    buyerKey = agentKeyFixtures["buyerAgent"]
    merchantKey = agentKeyFixtures["merchantNode"]

    negotiator = RubinsteinStahlNegotiator(
        skuId="SKU-104",
        quantity=negotiationQuantity,
        escrowBalancePaise=initialEscrowPoolPaise,
    )

    # Turn 1: Buyer ₹3,300, Seller ₹3,450 (Spread: ₹150)
    turn1 = negotiator.executeTurn(1, 330000, 345000)
    assert turn1.turnNumber == 1
    assert turn1.spreadPaise == 15000
    assert not turn1.isConverged

    # Turn 2: Buyer ₹3,330, Seller ₹3,380 (Spread: ₹50)
    turn2 = negotiator.executeTurn(2, 333000, 338000)
    assert turn2.turnNumber == 2
    assert turn2.spreadPaise == 5000
    assert not turn2.isConverged

    # Turn 3: Buyer ₹3,350, Seller ₹3,350 (Converged)
    turn3 = negotiator.executeTurn(3, agreedUnitPricePaise, agreedUnitPricePaise)
    assert turn3.turnNumber == 3
    assert turn3.spreadPaise == 0
    assert turn3.isConverged

    # Micro-escrow accounting assertions
    assert negotiator.cumulativeMicroFeesPaise == 150
    assert negotiator.escrowBalancePaise == 4850

    # Compile AST & Verify Deterministic Total
    ast, astHash = compileCommercialContractAst(
        skuId="SKU-104",
        quantity=negotiationQuantity,
        agreedUnitPrice=agreedUnitPricePaise,
        turns=3,
        buyerDid=buyerKey["did"],
        merchantDid=merchantKey["did"],
        timestamp=1755936000,
    )

    assert ast.agreedUnitPricePaise == 335000
    assert ast.taxableSubtotalPaise == 16750000
    assert ast.totalTaxPaise == 3015000
    assert ast.totalGrossPaise == 19765000
    assert len(astHash) == 64


def testTc02NonMonotonicConcessionViolation() -> None:
    """Verifies that attempting a non-monotonic bid raises NonMonotonicConcessionViolation."""
    negotiator = RubinsteinStahlNegotiator(
        skuId="SKU-104",
        quantity=10,
        escrowBalancePaise=initialEscrowPoolPaise,
    )
    negotiator.executeTurn(1, 330000, 345000)

    # Buyer decreases bid on Turn 2 -> Violation!
    with pytest.raises(NonMonotonicConcessionViolation):
        negotiator.executeTurn(2, 325000, 340000)
