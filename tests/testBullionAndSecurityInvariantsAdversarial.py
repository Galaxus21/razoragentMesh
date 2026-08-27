"""Adversarial Benchmark: Dynamic PoW Escalation, AST Constraints, Bargaining Monotonicity, and Micro-Escrow."""

from typing import Any, Dict, List
import pytest

from razoragentMesh.packages.vectorHealer.src.constraints.constraintFilter import (
    NegativeConstraintFilter,
)
from razoragentMesh.packages.vectorHealer.src.constraints.negativeManifestSchema import (
    NegativeConstraintManifest,
)
from razoragentMesh.packages.x402Gateway.src.escrow.escrowSessionManager import (
    EscrowSessionManager,
)
from razoragentMesh.packages.x402Gateway.src.gatewayExceptions import (
    InsufficientEscrowBalanceException,
    InvalidProofOfWorkException,
    NonMonotonicConcessionViolation,
)
from razoragentMesh.packages.x402Gateway.src.middleware.proofOfWorkMiddleware import (
    IngressAntiSpamShield,
    solvePoWChallenge,
)
from razoragentMesh.packages.x402Gateway.src.negotiation.bidStateMachine import (
    RubinsteinStahlNegotiator,
)

testClientIpAddress: str = "192.168.1.100"
testBuyerAgentDid: str = "did:agent:buyer-procurement-01"


def testTc21DynamicPowDifficultyEscalation() -> None:
    """TC-21: Dynamic PoW difficulty escalation from 4 to 5 leading zeros under rapid ingress load."""
    shield = IngressAntiSpamShield()
    baselineChallenge = shield.generateChallenge(clientIp=testClientIpAddress)
    assert baselineChallenge.powDifficultyZeros == 4

    escalatedChallenge = shield.generateChallenge(clientIp=testClientIpAddress, requestCount=100)
    assert escalatedChallenge.powDifficultyZeros == 5

    validNonce = solvePoWChallenge(escalatedChallenge.challengeToken, difficultyZeros=5)
    result = shield.validatePoWSubmission(escalatedChallenge.challengeToken, validNonce)
    assert result.isValid is True and result.computedDigest.startswith("00000")

    challengeToken = shield.generateChallenge(clientIp=testClientIpAddress, requestCount=101).challengeToken
    insufficientNonce = solvePoWChallenge(challengeToken, difficultyZeros=4)
    if not shield.verifyPoWSolution(challengeToken, insufficientNonce, difficultyZeros=5):
        with pytest.raises(InvalidProofOfWorkException):
            shield.validatePoWSubmission(challengeToken, insufficientNonce, requiredDifficulty=5)


def _getCandidateSkus() -> List[Dict[str, Any]]:
    return [
        {"skuId": "SKU-01", "brand": "BrandA", "attributes": {"allergens": ["peanut"], "weightGrams": 200, "isVeg": True}},
        {"skuId": "SKU-02", "brand": "BrandB", "attributes": {"allergens": ["gluten"], "weightGrams": 300, "isVeg": True}},
        {"skuId": "SKU-03", "brand": "PharmaA", "pharmaFacet": {"activeSalt": "paracetamol"}, "attributes": {"weightGrams": 100, "isVeg": True}},
        {"skuId": "SKU-04", "brand": "PharmaB", "pharmaFacet": {"prescriptionRequired": True}, "attributes": {"weightGrams": 150, "isVeg": True}},
        {"skuId": "SKU-05", "brand": "FoodA", "fmcgFacet": {"isVeg": False}, "attributes": {"weightGrams": 250}},
        {"skuId": "SKU-06", "brand": "FoodB", "fmcgFacet": {}, "attributes": {"weightGrams": 200}},
        {"skuId": "SKU-07", "brand": "ItemA", "attributes": {"allergens": [], "weightGrams": 650, "isVeg": True}},
        {"skuId": "SKU-08", "brand": "ItemB", "attributes": {"allergens": ["peanut"], "weightGrams": 750, "isVeg": False}},
        {"skuId": "SKU-09", "brand": "SafeFoodA", "attributes": {"allergens": [], "weightGrams": 250, "isVeg": True}},
        {"skuId": "SKU-10", "brand": "SafeFoodB", "attributes": {"allergens": [], "weightGrams": 450, "isVeg": True}},
    ]


def testTc22CombinatorialAstConstraintSatisfaction() -> None:
    """TC-22: 5-dimension combinatorial AST constraint satisfaction over 10 SKU candidates."""
    manifest = NegativeConstraintManifest(
        excludedAllergens=["peanut", "gluten"], excludedActiveSalts=["paracetamol"],
        requireOtcOnly=True, requireVeg=True, maxWeightGrams=500,
    )
    filterEngine = NegativeConstraintFilter(manifest)
    results = [filterEngine.evaluateCandidate(sku) for sku in _getCandidateSkus()]
    allowed = [res for res in results if res.isAllowed]
    rejected = [res for res in results if not res.isAllowed]

    assert len(allowed) == 2 and len(rejected) == 8
    assert {c.skuId for c in allowed} == {"SKU-09", "SKU-10"}

    rejections = {res.skuId: res.rejectionReason for res in rejected}
    assert "ALLERGEN_BREACH:peanut" in str(rejections["SKU-01"])
    assert "ALLERGEN_BREACH:gluten" in str(rejections["SKU-02"])
    assert "ACTIVE_SALT_EXCLUDED:paracetamol" in str(rejections["SKU-03"])
    assert "PRESCRIPTION_REQUIRED_BREACH" in str(rejections["SKU-04"])
    assert "NON_VEG_EXCLUDED" in str(rejections["SKU-05"])
    assert "NON_VEG_EXCLUDED" in str(rejections["SKU-06"])
    assert "WEIGHT_LIMIT_EXCEEDED:650g" in str(rejections["SKU-07"])


def testTc23RubinsteinStahlMonotonicityInversion() -> None:
    """TC-23: Monotonicity violation detection and state corruption defense in B2B bargaining."""
    negotiator = RubinsteinStahlNegotiator(
        skuId="SKU-CHAIR-001", quantity=10, escrowBalancePaise=500, sellerCostFloorPaise=300000,
    )
    step1 = negotiator.executeTurn(turnNumber=1, buyerBidPaise=330000, sellerAskPaise=350000)
    assert step1.isConverged is False and len(negotiator.turnHistory) == 1 and negotiator.escrowBalancePaise == 450

    with pytest.raises(NonMonotonicConcessionViolation):
        negotiator.executeTurn(turnNumber=2, buyerBidPaise=325000, sellerAskPaise=345000)
    assert len(negotiator.turnHistory) == 1 and negotiator.escrowBalancePaise == 450

    with pytest.raises(NonMonotonicConcessionViolation):
        negotiator.executeTurn(turnNumber=2, buyerBidPaise=332000, sellerAskPaise=355000)
    assert len(negotiator.turnHistory) == 1 and negotiator.escrowBalancePaise == 450

    step2 = negotiator.executeTurn(turnNumber=2, buyerBidPaise=335000, sellerAskPaise=345000)
    assert step2.turnNumber == 2 and step2.spreadPaise == 10000 and len(negotiator.turnHistory) == 2


def testTc25MicroEscrowPoolDepletionMidTurn() -> None:
    """TC-25: Micro-escrow pool exhaustion mid-turn with zero overdraft and invariant balance preservation."""
    escrowManager = EscrowSessionManager()
    session = escrowManager.createSession(buyerAgentDid=testBuyerAgentDid, initialHoldPaise=150)

    session, rem1, _ = escrowManager.debitSession(session.sessionToken, feePaise=50)
    assert rem1 == 100 and session.debitedTotalPaise == 50
    session, rem2, _ = escrowManager.debitSession(session.sessionToken, feePaise=50)
    assert rem2 == 50 and session.debitedTotalPaise == 100
    session, rem3, _ = escrowManager.debitSession(session.sessionToken, feePaise=50)
    assert rem3 == 0 and session.debitedTotalPaise == 150

    with pytest.raises(InsufficientEscrowBalanceException):
        escrowManager.debitSession(session.sessionToken, feePaise=50)

    finalSession = escrowManager.getSession(session.sessionToken)
    assert finalSession.remainingBalancePaise == 0 and finalSession.debitedTotalPaise == 150 and finalSession.totalTurnsDebited == 3
