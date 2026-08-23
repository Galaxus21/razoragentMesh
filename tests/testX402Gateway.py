"""Comprehensive unit and integration tests for Layer 2 x402Gateway."""

import time
import pytest
from httpx import ASGITransport, AsyncClient

from razoragentMesh.packages.x402Gateway.src.compiler.astContractCompiler import (
    CommercialContractAst,
    compileCommercialContractAst,
)
from razoragentMesh.packages.x402Gateway.src.negotiation.bidStateMachine import (
    NegotiationStatus,
    RubinsteinStahlNegotiator,
)
from razoragentMesh.packages.x402Gateway.src.gatewayApp import app
from razoragentMesh.packages.x402Gateway.src.constants.negotiationConstants import (
    headerEscrowToken,
    headerPowChallenge,
    headerPowSolution,
    initialEscrowPoolPaise,
    maxNegotiationTurns,
    microFeePerTurnPaise,
)
from razoragentMesh.packages.x402Gateway.src.gatewayExceptions import (
    EscrowSessionNotFoundException,
    InsufficientEscrowBalanceException,
    InvalidProofOfWorkException,
    NegotiationExhaustedException,
    NonMonotonicConcessionViolation,
    PowReplayDetectedException,
)
from razoragentMesh.packages.x402Gateway.src.escrow.microEscrowClient import MicroEscrowClient
from razoragentMesh.packages.x402Gateway.src.middleware.proofOfWorkMiddleware import (
    IngressAntiSpamShield,
    solvePoWChallenge,
)


def testProofOfWorkGenerationAndVerification() -> None:
    """Verifies that PoW challenges are generated, solved, and verified correctly."""
    shield = IngressAntiSpamShield()
    challenge = shield.generateChallenge(clientIp="127.0.0.1")

    assert challenge.statusCode == 402
    assert challenge.tokenCostPaise == microFeePerTurnPaise
    assert challenge.powDifficultyZeros == 4

    # Solve challenge
    nonce = solvePoWChallenge(challenge.challengeToken)
    assert shield.verifyPoWSolution(challenge.challengeToken, nonce) is True

    # Validate full submission
    result = shield.validatePoWSubmission(challenge.challengeToken, nonce)
    assert result.isValid is True
    assert result.computedDigest.startswith("0000")

    # Verify replay defense
    with pytest.raises(PowReplayDetectedException):
        shield.validatePoWSubmission(challenge.challengeToken, nonce)


def testProofOfWorkInvalidSolutionRejection() -> None:
    """Verifies that invalid PoW solutions are rejected."""
    shield = IngressAntiSpamShield()
    challenge = shield.generateChallenge(clientIp="10.0.0.2")

    with pytest.raises(InvalidProofOfWorkException):
        shield.validatePoWSubmission(challenge.challengeToken, 99999999)


@pytest.mark.asyncio
async def testMicroEscrowLifecycle() -> None:
    """Verifies complete micro-escrow lifecycle: create, debit turns, release refund."""
    client = MicroEscrowClient()
    session = await client.createEscrowSession(buyerAgentDid="did:agent:test_buyer_01")

    assert session.initialHoldPaise == initialEscrowPoolPaise
    assert session.remainingBalancePaise == initialEscrowPoolPaise
    assert session.debitedTotalPaise == 0

    # Turn 1 Debit
    receipt1 = await client.debitTurnFee(session.sessionToken, turnIndex=1)
    assert receipt1.debitAmountPaise == microFeePerTurnPaise
    assert receipt1.remainingBalancePaise == initialEscrowPoolPaise - microFeePerTurnPaise
    assert len(receipt1.receiptSignatureHex) == 64

    # Turn 2 Debit
    receipt2 = await client.debitTurnFee(session.sessionToken, turnIndex=2)
    assert receipt2.debitAmountPaise == microFeePerTurnPaise
    assert receipt2.remainingBalancePaise == initialEscrowPoolPaise - (2 * microFeePerTurnPaise)

    # Release unspent escrow
    refund = await client.releaseUnspentEscrow(session.sessionToken)
    assert refund.totalDebitedPaise == 100
    assert refund.refundedBalancePaise == 4900

    # Verify cannot debit after release
    with pytest.raises(EscrowSessionNotFoundException):
        await client.debitTurnFee(session.sessionToken, turnIndex=3)


@pytest.mark.asyncio
async def testMicroEscrowInsufficientBalance() -> None:
    """Verifies that debiting beyond escrow balance raises InsufficientEscrowBalanceException."""
    client = MicroEscrowClient()
    session = await client.createEscrowSession(
        buyerAgentDid="did:agent:test_buyer_02",
        initialHoldPaise=50,  # Only 50 paise hold
    )

    await client.debitTurnFee(session.sessionToken, turnIndex=1)
    with pytest.raises(InsufficientEscrowBalanceException):
        await client.debitTurnFee(session.sessionToken, turnIndex=2)


def testRubinsteinStahlNegotiationFlow() -> None:
    """Verifies multi-turn Rubinstein-Stahl convergence and monotonic enforcement."""
    negotiator = RubinsteinStahlNegotiator(
        skuId="SKU-CHAIR-001",
        quantity=20,
        escrowBalancePaise=5000,
    )

    turn1 = negotiator.executeTurn(1, 330000, 345000)
    assert turn1.spreadPaise == 15000
    assert not turn1.isConverged
    assert negotiator.cumulativeMicroFeesPaise == 50

    turn2 = negotiator.executeTurn(2, 333000, 338000)
    assert turn2.spreadPaise == 5000
    assert not turn2.isConverged
    assert negotiator.cumulativeMicroFeesPaise == 100

    turn3 = negotiator.executeTurn(3, 335000, 335000)
    assert turn3.spreadPaise == 0
    assert turn3.isConverged
    assert negotiator.status == NegotiationStatus.CONVERGED


def testRubinsteinStahlNonMonotonicViolation() -> None:
    """Verifies that non-monotonic buyer concessions raise NonMonotonicConcessionViolation."""
    negotiator = RubinsteinStahlNegotiator(
        skuId="SKU-CHAIR-001",
        quantity=10,
        escrowBalancePaise=5000,
    )
    negotiator.executeTurn(1, 330000, 345000)

    # Decreasing bid on turn 2 -> Violation
    with pytest.raises(NonMonotonicConcessionViolation):
        negotiator.executeTurn(2, 329000, 340000)


def testRubinsteinStahlMaxTurnsExhaustion() -> None:
    """Verifies that exceeding max turns raises NegotiationExhaustedException."""
    negotiator = RubinsteinStahlNegotiator(
        skuId="SKU-CHAIR-001",
        quantity=10,
        escrowBalancePaise=5000,
    )
    for t in range(1, maxNegotiationTurns + 1):
        negotiator.executeTurn(t, 300000 + (t * 1000), 400000 - (t * 1000))

    assert negotiator.status == NegotiationStatus.NEGOTIATION_EXHAUSTED
    with pytest.raises(NegotiationExhaustedException):
        negotiator.executeTurn(6, 310000, 390000)


def testAstContractCompilation() -> None:
    """Verifies AST contract compilation and JCS canonical hashing."""
    now = int(time.time())
    ast, astHash = compileCommercialContractAst(
        skuId="SKU-CHAIR-001",
        quantity=10,
        agreedUnitPrice=335000,
        turns=3,
        buyerDid="did:agent:buyer123",
        merchantDid="did:agent:merchant456",
        timestamp=now,
        gstRate=18,
        isIntraState=True,
    )

    assert ast.skuId == "SKU-CHAIR-001"
    assert ast.quantity == 10
    assert ast.agreedUnitPricePaise == 335000
    assert ast.taxableSubtotalPaise == 3350000
    assert ast.totalTaxPaise == 603000
    assert ast.totalGrossPaise == 3953000
    assert len(astHash) == 64


@pytest.mark.asyncio
async def testGatewayAppEndpoints() -> None:
    """Integration test for FastAPI gateway application endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Health check
        respHealth = await client.get("/api/v1/mesh/health")
        assert respHealth.status_code == 200
        assert respHealth.json()["status"] == "healthy"

        # 2. Challenge endpoint
        respChal = await client.get("/api/v1/mesh/challenge")
        assert respChal.status_code == 200
        chalData = respChal.json()
        challengeToken = chalData["challengeToken"]

        # 3. Create Escrow Session
        respEscrow = await client.post(
            "/api/v1/mesh/escrow",
            json={"buyerAgentDid": "did:agent:app_buyer", "initialHoldPaise": 5000},
        )
        assert respEscrow.status_code == 200
        escrowToken = respEscrow.json()["sessionToken"]

        # 4. Attempt negotiate without PoW -> 402/403
        respNegFail = await client.post(
            "/api/v1/mesh/negotiate",
            json={
                "skuId": "SKU-CHAIR-001",
                "quantity": 5,
                "turnNumber": 1,
                "buyerBidPaise": 330000,
                "sellerAskPaise": 345000,
                "buyerAgentDid": "did:agent:app_buyer",
                "merchantDid": "did:agent:app_merchant",
            },
        )
        assert respNegFail.status_code == 402

        # 5. Solve PoW and negotiate
        solNonce = solvePoWChallenge(challengeToken)
        headers = {
            headerPowChallenge: challengeToken,
            headerPowSolution: str(solNonce),
            headerEscrowToken: escrowToken,
        }
        respNeg1 = await client.post(
            "/api/v1/mesh/negotiate",
            json={
                "skuId": "SKU-CHAIR-001",
                "quantity": 5,
                "turnNumber": 1,
                "buyerBidPaise": 330000,
                "sellerAskPaise": 345000,
                "buyerAgentDid": "did:agent:app_buyer",
                "merchantDid": "did:agent:app_merchant",
            },
            headers=headers,
        )
        assert respNeg1.status_code == 200
        stepData = respNeg1.json()["stepResult"]
        assert stepData["turnNumber"] == 1
        assert not stepData["isConverged"]

        # 6. Release unspent escrow
        respRel = await client.post(
            "/api/v1/mesh/escrow/release",
            headers={headerEscrowToken: escrowToken},
        )
        assert respRel.status_code == 200
        assert respRel.json()["totalDebitedPaise"] == 50
        assert respRel.json()["refundedBalancePaise"] == 4950
