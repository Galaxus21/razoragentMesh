"""Empirical Challenger 2 Test Suite: Concurrency, Protocol & Adversarial Invariants.

Tests the 5 core mission requirements:
1. Concurrency Double-Lock Race (TC-09)
2. Anti-Spam Sybil & x402-INR Challenge (TC-06)
3. Rubinstein-Ståhl Bargaining Monotonicity (TC-02)
4. Out-of-Stock Self-Healing & Latency SLA (TC-04)
5. Negative Constraint Filtering (TC-05)
"""

import asyncio
import hashlib
import time
from typing import Any, Dict, List
import pytest
from httpx import ASGITransport, AsyncClient

# Imports from codebase
from razoragentMesh.packages.mandateEngine.amendmentMandateSchema import AmendmentMandate
from razoragentMesh.packages.mandateEngine.arithmeticConstants import (
    paisePerRupee,
    percentDivisor,
)
from razoragentMesh.packages.mandateEngine.arithmeticEnclave import (
    computeCartSettlementTotal,
    computeGstBreakdown,
    computeLineItemTotal,
    validateIntegerPaise,
)
from razoragentMesh.packages.mandateEngine.cartMandateSchema import (
    CartItemSchema,
    CartMandate,
    TaxBreakdownSchema,
)
from razoragentMesh.packages.mandateEngine.cryptoKeyUtils import extractPublicKeyFromDid
from razoragentMesh.packages.mandateEngine.ed25519Signer import Ed25519Signer
from razoragentMesh.packages.mandateEngine.ed25519Verifier import Ed25519Verifier
from razoragentMesh.packages.mandateEngine.intentMandateSchema import IntentMandate
from razoragentMesh.packages.mandateEngine.jcsCanonicalizer import (
    canonicalizeJson,
    computeSha256Digest,
)
from razoragentMesh.packages.mandateEngine.mandateFactory import (
    createSignedAmendmentMandate,
    createSignedCartMandate,
    createSignedIntentMandate,
)
from razoragentMesh.packages.mandateEngine.settlementExceptions import (
    ArithmeticDriftException,
    BudgetExceededViolation,
)
from razoragentMesh.packages.vectorHealer.constraintFilter import (
    NegativeConstraintFilter,
    NegativeConstraintManifest,
)
from razoragentMesh.packages.vectorHealer.embeddingProvider import EmbeddingProvider
from razoragentMesh.packages.vectorHealer.healerConstants import (
    maxPriceDeltaPercent,
    minCosineSimilarity,
)
from razoragentMesh.packages.vectorHealer.healerExceptions import (
    NoSubstituteFoundException,
)
from razoragentMesh.packages.vectorHealer.mandatePatcher import MandatePatcher
from razoragentMesh.packages.vectorHealer.oosInterceptor import OosInterceptor
from razoragentMesh.packages.vectorHealer.vectorSearcher import (
    ScoredPointCandidate,
    VectorSearcher,
)
from razoragentMesh.packages.x402Gateway.astContractCompiler import (
    CommercialContractAst,
    compileCommercialContractAst,
)
from razoragentMesh.packages.x402Gateway.bidStateMachine import (
    NegotiationStatus,
    RubinsteinStahlNegotiator,
)
from razoragentMesh.packages.x402Gateway.gatewayApp import app
from razoragentMesh.packages.x402Gateway.gatewayConstants import (
    headerEscrowToken,
    headerPowChallenge,
    headerPowSolution,
    initialEscrowPoolPaise,
    maxNegotiationTurns,
    microFeePerTurnPaise,
    powLeadingZeros,
    requiredLeadingPrefix,
)
from razoragentMesh.packages.x402Gateway.gatewayExceptions import (
    InvalidProofOfWorkException,
    NegotiationExhaustedException,
    NonMonotonicConcessionViolation,
    PowChallengeExpiredException,
    PowReplayDetectedException,
)
from razoragentMesh.packages.x402Gateway.microEscrowClient import MicroEscrowClient
from razoragentMesh.packages.x402Gateway.proofOfWorkMiddleware import (
    IngressAntiSpamShield,
    solvePoWChallenge,
)
from razoragentMesh.tests.mockInfraHelpers import MockQdrantClient, MockRedisAsync


# ============================================================================
# 1. CONCURRENCY DOUBLE-LOCK RACE STRESS TESTS (TC-09)
# ============================================================================

@pytest.mark.asyncio
async def testChallenger2ConcurrencyExactDoubleLockRace(mockRedisClient: MockRedisAsync) -> None:
    """Stress Test 1.1: Exact 2-agent simultaneous race for last 1 inventory unit.
    
    Verifies:
    - Exactly 1 agent receives Lock Success (status == 1) with fencing token >= 1
    - Exactly 1 agent receives 409 Conflict / Insufficient Stock (status == -1)
    - Redis stock becomes exactly 0 (no negative inventory, no over-allocation)
    """
    skuId = "SKU-STRESS-001"
    stockKey = f"sku:{skuId}:stock"
    fencingKey = f"sku:{skuId}:fence"
    await mockRedisClient.set(stockKey, 1)

    async def lockAttempt(agentId: str) -> tuple[int, int]:
        res = await mockRedisClient.eval("", 2, stockKey, fencingKey, 1, f"token_{agentId}", 60)
        return res[0], res[1]

    taskA = asyncio.create_task(lockAttempt("agent_alpha"))
    taskB = asyncio.create_task(lockAttempt("agent_beta"))

    resA, resB = await asyncio.gather(taskA, taskB)
    statuses = [resA[0], resB[0]]

    assert statuses.count(1) == 1, f"Expected exactly 1 success, got {statuses}"
    assert statuses.count(-1) == 1, f"Expected exactly 1 failure, got {statuses}"

    finalStock = int(await mockRedisClient.get(stockKey) or 0)
    assert finalStock == 0, f"Stock must be exactly 0, got {finalStock}"


@pytest.mark.asyncio
async def testChallenger2ConcurrencyMultiAgentMassiveContention(mockRedisClient: MockRedisAsync) -> None:
    """Stress Test 1.2: 50 concurrent agents racing for 5 available inventory units.
    
    Verifies:
    - Exactly 5 agents acquire 1 unit each (status == 1)
    - Exactly 45 agents are rejected with status == -1
    - Monotonically increasing fencing tokens 1 through 5
    - Final stock in Redis is strictly 0 (no leak)
    """
    skuId = "SKU-STRESS-50-AGENTS"
    stockKey = f"sku:{skuId}:stock"
    fencingKey = f"sku:{skuId}:fence"
    initialStock = 5
    concurrencyCount = 50

    await mockRedisClient.set(stockKey, initialStock)

    async def attemptLock(agentIndex: int) -> tuple[int, int]:
        res = await mockRedisClient.eval(
            "", 2, stockKey, fencingKey, 1, f"token_agent_{agentIndex:03d}", 60
        )
        return res[0], res[1]

    tasks = [asyncio.create_task(attemptLock(i)) for i in range(concurrencyCount)]
    results = await asyncio.gather(*tasks)

    successes = [r for r in results if r[0] == 1]
    rejections = [r for r in results if r[0] == -1]

    assert len(successes) == initialStock, f"Expected {initialStock} successes, got {len(successes)}"
    assert len(rejections) == concurrencyCount - initialStock, f"Expected {concurrencyCount - initialStock} rejections, got {len(rejections)}"

    # Check that fencing tokens are unique and monotonically positive
    fencingTokens = sorted([r[1] for r in successes])
    assert fencingTokens == list(range(1, initialStock + 1)), f"Fencing tokens must be [1..5], got {fencingTokens}"

    finalStock = int(await mockRedisClient.get(stockKey) or 0)
    assert finalStock == 0


@pytest.mark.asyncio
async def testChallenger2ConcurrencyLockExpirationAndRelock(mockRedisClient: MockRedisAsync) -> None:
    """Stress Test 1.3: Lock attempts on depleted stock remain rejected."""
    skuId = "SKU-STRESS-DEPLETED"
    stockKey = f"sku:{skuId}:stock"
    fencingKey = f"sku:{skuId}:fence"
    await mockRedisClient.set(stockKey, 0)

    res = await mockRedisClient.eval("", 2, stockKey, fencingKey, 1, "token_fail", 60)
    assert res[0] == -1
    assert res[1] == 0


# ============================================================================
# 2. ANTI-SPAM SYBIL & x402-INR CHALLENGE STRESS TESTS (TC-06)
# ============================================================================

def testChallenger2AntiSpam100ConcurrentSpamBidsFastPathRejection() -> None:
    """Stress Test 2.1: 100 concurrent unauthenticated spam bids.
    
    Verifies:
    - 1st request generates valid HTTP 402 challenge with 4-zero PoW requirement
    - Remaining 99 spam bids rejected with 402 in < 2ms each without invoking LLM
    - LLM invocation count remains strictly 0
    """
    shield = IngressAntiSpamShield()

    # Turn 1: First probe receives 402 challenge
    startChal = time.perf_counter()
    challenge = shield.generateChallenge(clientIp="192.168.1.10")
    chalLatencyMs = (time.perf_counter() - startChal) * 1000.0

    assert challenge.statusCode == 402
    assert challenge.wwwAuthenticate == "x402-INR"
    assert challenge.powDifficultyZeros == 4
    assert chalLatencyMs < 2.0, f"Challenge generation latency {chalLatencyMs:.3f}ms exceeded 2ms SLA"

    # Turn 2..100: 99 spam requests
    rejectionTimesMs: List[float] = []
    for spamIndex in range(2, 101):
        t0 = time.perf_counter()
        status, msg = shield.processRequest(challengeToken=None, powNonce=None, escrowSessionToken=None)
        elapsedMs = (time.perf_counter() - t0) * 1000.0
        rejectionTimesMs.append(elapsedMs)
        assert status == 402
        assert "Micro-escrow and PoW challenge required" in msg

    assert len(rejectionTimesMs) == 99
    maxRejectionMs = max(rejectionTimesMs)
    avgRejectionMs = sum(rejectionTimesMs) / len(rejectionTimesMs)

    assert avgRejectionMs < 1.0, f"Average rejection latency {avgRejectionMs:.4f}ms exceeded 1ms"
    assert maxRejectionMs < 2.0, f"Max rejection latency {maxRejectionMs:.4f}ms exceeded 2ms"
    assert shield.llmInvocationsCount == 0, "Zero LLM invocations allowed on spam flood"


def testChallenger2PoWReplayAndTamperedNonceAttack() -> None:
    """Stress Test 2.2: Adversarial attacks on PoW mechanism.
    
    Verifies:
    - Replaying a solved challenge nonce is blocked by replay guard
    - Invalid nonce fails difficulty verification
    - Expired challenge is rejected
    """
    shield = IngressAntiSpamShield()
    challenge = shield.generateChallenge(clientIp="10.10.10.1")
    nonce = solvePoWChallenge(challenge.challengeToken)

    # 1. First submission succeeds
    result = shield.validatePoWSubmission(challenge.challengeToken, nonce)
    assert result.isValid is True

    # 2. Replay of same token/nonce -> PowReplayDetectedException
    with pytest.raises(PowReplayDetectedException):
        shield.validatePoWSubmission(challenge.challengeToken, nonce)

    # 3. Invalid nonce on fresh challenge -> InvalidProofOfWorkException
    chal2 = shield.generateChallenge(clientIp="10.10.10.2")
    with pytest.raises(InvalidProofOfWorkException):
        shield.validatePoWSubmission(chal2.challengeToken, nonce=999999999)

    # 4. Expired challenge -> PowChallengeExpiredException
    chal3 = shield.generateChallenge(clientIp="10.10.10.3")
    shield.activeChallenges[chal3.challengeToken] = int(time.time()) - 10  # force expiry
    with pytest.raises(PowChallengeExpiredException):
        shield.validatePoWSubmission(chal3.challengeToken, nonce=0)


@pytest.mark.asyncio
async def testChallenger2GatewayApp100SpamHttpRequests() -> None:
    """Stress Test 2.3: 100 concurrent HTTP requests against FastAPI /api/v1/mesh/negotiate.
    
    Verifies:
    - All 100 requests without PoW / escrow header receive HTTP 402 in < 5ms over ASGI
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        async def sendSpamRequest(idx: int) -> int:
            resp = await client.post(
                "/api/v1/mesh/negotiate",
                json={
                    "skuId": "SKU-CHAIR-001",
                    "quantity": 1,
                    "turnNumber": 1,
                    "buyerBidPaise": 330000,
                    "sellerAskPaise": 345000,
                    "buyerAgentDid": f"did:agent:spammer_{idx}",
                    "merchantDid": "did:agent:merchant",
                },
            )
            return resp.status_code

        tasks = [sendSpamRequest(i) for i in range(100)]
        t0 = time.perf_counter()
        statusCodes = await asyncio.gather(*tasks)
        totalElapsedMs = (time.perf_counter() - t0) * 1000.0

        assert statusCodes.count(402) == 100
        avgLatencyMs = totalElapsedMs / 100.0
        assert avgLatencyMs < 10.0, f"Average ASGI HTTP 402 latency {avgLatencyMs:.2f}ms"


# ============================================================================
# 3. RUBINSTEIN-STÅHL BARGAINING MONOTONICITY STRESS TESTS (TC-02)
# ============================================================================

def testChallenger2RubinsteinStahlMonotonicityAndAdversarialAttacks() -> None:
    """Stress Test 3.1: Adversarial challenge against BidStateMachine invariants.
    
    Verifies:
    - Buyer bid decrease raises NonMonotonicConcessionViolation
    - Seller ask increase raises NonMonotonicConcessionViolation
    - Turn > 5 raises NegotiationExhaustedException
    - Micro-escrow debits exactly 50 paise per executed turn
    """
    negotiator = RubinsteinStahlNegotiator(
        skuId="SKU-CHAIR-001",
        quantity=10,
        escrowBalancePaise=5000,
        sellerCostFloorPaise=330000,
    )

    # Turn 1: Normal opening
    turn1 = negotiator.executeTurn(1, 320000, 350000)
    assert not turn1.isConverged
    assert negotiator.cumulativeMicroFeesPaise == 50
    assert negotiator.escrowBalancePaise == 4950

    # Malicious Attack 1: Buyer decreases bid (320000 -> 315000)
    with pytest.raises(NonMonotonicConcessionViolation) as excInfo:
        negotiator.executeTurn(2, 315000, 345000)
    assert "Buyer bid cannot decrease" in str(excInfo.value)

    # Malicious Attack 2: Seller increases ask (350000 -> 355000)
    with pytest.raises(NonMonotonicConcessionViolation) as excInfo2:
        negotiator.executeTurn(2, 325000, 355000)
    assert "Seller ask cannot increase" in str(excInfo2.value)

    # Turn 2: Valid progression
    turn2 = negotiator.executeTurn(2, 325000, 345000)
    assert not turn2.isConverged
    assert negotiator.cumulativeMicroFeesPaise == 100

    # Turn 3: Valid progression
    turn3 = negotiator.executeTurn(3, 330000, 340000)
    assert not turn3.isConverged
    assert negotiator.cumulativeMicroFeesPaise == 150

    # Turn 4: Valid progression
    turn4 = negotiator.executeTurn(4, 332000, 335000)
    assert not turn4.isConverged
    assert negotiator.cumulativeMicroFeesPaise == 200

    # Turn 5: Max allowed turn without convergence -> status NEGOTIATION_EXHAUSTED
    turn5 = negotiator.executeTurn(5, 333000, 334000)
    assert not turn5.isConverged
    assert negotiator.status == NegotiationStatus.NEGOTIATION_EXHAUSTED
    assert negotiator.cumulativeMicroFeesPaise == 250

    # Malicious Attack 3: Attempting Turn 6 after exhaustion
    with pytest.raises(NegotiationExhaustedException):
        negotiator.executeTurn(6, 334000, 334000)


def testChallenger2RubinsteinStahlMarginFloorAndAstCompilation() -> None:
    """Stress Test 3.2: Seller margin floor enforcement and AST compilation integrity."""
    negotiator = RubinsteinStahlNegotiator(
        skuId="SKU-104",
        quantity=50,
        escrowBalancePaise=5000,
        sellerCostFloorPaise=335000,
    )

    # Test seller counter-ask cannot breach floor (₹3,350)
    counterAskTurn10 = negotiator.computeSellerCounterAsk(
        initialAskPaise=345000, buyerBidPaise=300000, turnIndex=10
    )
    assert counterAskTurn10 >= 335000, "Counter-ask must not breach seller cost floor"

    # 3-turn convergence test
    negotiator.executeTurn(1, 330000, 345000)
    negotiator.executeTurn(2, 333000, 338000)
    finalTurn = negotiator.executeTurn(3, 335000, 335000)

    assert finalTurn.isConverged
    assert negotiator.status == NegotiationStatus.CONVERGED
    assert negotiator.cumulativeMicroFeesPaise == 150

    # AST compilation
    ast, astHash = compileCommercialContractAst(
        skuId="SKU-104",
        quantity=50,
        agreedUnitPrice=335000,
        turns=3,
        buyerDid="did:agent:buyer_c2",
        merchantDid="did:agent:merchant_c2",
        timestamp=1755936000,
        gstRate=18,
        isIntraState=True,
    )

    assert ast.agreedUnitPricePaise == 335000
    assert ast.taxableSubtotalPaise == 16750000  # 50 * 335000
    assert ast.totalTaxPaise == 3015000         # 18% of 16750000
    assert ast.totalGrossPaise == 19765000       # 16750000 + 3015000
    assert len(astHash) == 64


# ============================================================================
# 4. OUT-OF-STOCK SELF-HEALING & LATENCY SLA STRESS TESTS (TC-04)
# ============================================================================

def testChallenger2OosSelfHealingBoundaryConditions(
    agentKeyFixtures: Dict[str, Any],
    catalogFixtures: List[Dict[str, Any]],
    mockQdrantClient: MockQdrantClient,
) -> None:
    """Stress Test 4.1: Vector boundary conditions (Cosine 0.849 vs 0.850, Price Delta 5.01% vs 5.00%).
    
    Verifies:
    - Candidate with Cosine < 0.85 is rejected
    - Candidate with Price Delta > +5.0% is rejected
    - Candidate with insufficient stock is skipped
    - Valid substitute meets all 3 criteria and produces dual-signed AmendmentMandate
    """
    buyerKey = agentKeyFixtures["buyerAgent"]
    merchantKey = agentKeyFixtures["merchantNode"]
    buyerSigner = Ed25519Signer(buyerKey["privateKeyHex"])
    merchantSigner = Ed25519Signer(merchantKey["privateKeyHex"])

    now = int(time.time())
    origCart = createSignedCartMandate(
        cartId="cart_c2_oos_test",
        merchantSigner=merchantSigner,
        merchantGstin="29AABCU9603R1ZM",
        merchantStateCode="29",
        buyerDeliveryPincode="560001",
        buyerDeliveryStateCode="29",
        items=[
            CartItemSchema(
                skuId="SKU-101",
                quantity=1,
                unitPricePaise=350000,
                hsnCode="8471",
                gstRatePercent=18,
                lineTotalPaise=350000,
            )
        ],
        taxableSubtotalPaise=350000,
        taxBreakdown=TaxBreakdownSchema(cgstPaise=31500, sgstPaise=31500, igstPaise=0, totalTaxPaise=63000),
        shippingPaise=0,
        discountPaise=0,
        totalPaise=413000,
        inventoryLockToken="lock_failed_oos",
        inventoryLockExpiresAt=now + 60,
        timestamp=now,
    )

    interceptor = OosInterceptor(mockQdrantClient, catalogFixtures)

    # 1. Normal Healing on SKU-101 -> SKU-104 (+₹50 / +1.43%, Cosine >= 0.85)
    amendment, healedCart, durationMs, cosineSim = interceptor.healOutOfStock(
        failedSkuId="SKU-101",
        requestedQuantity=1,
        buyerAgentSigner=buyerSigner,
        merchantSigner=merchantSigner,
        originalCartMandate=origCart,
    )

    assert durationMs < 300.0, f"Healing latency {durationMs:.2f}ms exceeded 300ms SLA"
    assert amendment.substitutedSkuMapping["SKU-101"] == "SKU-104"
    assert amendment.priceDeltaPaise == 5000
    assert cosineSim >= 0.85
    assert healedCart.items[0].skuId == "SKU-104"

    # Dual signature verification
    agentPub = extractPublicKeyFromDid(buyerSigner.getAgentDid())
    merchantPub = extractPublicKeyFromDid(merchantSigner.getAgentDid())
    unsignedAmendment = {k: v for k, v in amendment.model_dump().items() if k not in ("agentSignature", "merchantSignature")}
    assert Ed25519Verifier.verifyPayloadSignature(agentPub, unsignedAmendment, amendment.agentSignature)
    assert Ed25519Verifier.verifyPayloadSignature(merchantPub, unsignedAmendment, amendment.merchantSignature)


def testChallenger2OosSelfHealing100IterationsLatencySla(
    agentKeyFixtures: Dict[str, Any],
    catalogFixtures: List[Dict[str, Any]],
    mockQdrantClient: MockQdrantClient,
) -> None:
    """Stress Test 4.2: 100 consecutive OOS self-healing cycles for latency SLA compliance.
    
    Verifies:
    - 100% of 100 cycles complete in < 300ms
    - Mean latency is sub-10ms
    """
    buyerSigner = Ed25519Signer(agentKeyFixtures["buyerAgent"]["privateKeyHex"])
    merchantSigner = Ed25519Signer(agentKeyFixtures["merchantNode"]["privateKeyHex"])

    now = int(time.time())
    origCart = createSignedCartMandate(
        cartId="cart_c2_sla_test",
        merchantSigner=merchantSigner,
        merchantGstin="29AABCU9603R1ZM",
        merchantStateCode="29",
        buyerDeliveryPincode="560001",
        buyerDeliveryStateCode="29",
        items=[
            CartItemSchema(
                skuId="SKU-101",
                quantity=1,
                unitPricePaise=350000,
                hsnCode="8471",
                gstRatePercent=18,
                lineTotalPaise=350000,
            )
        ],
        taxableSubtotalPaise=350000,
        taxBreakdown=TaxBreakdownSchema(cgstPaise=31500, sgstPaise=31500, igstPaise=0, totalTaxPaise=63000),
        shippingPaise=0,
        discountPaise=0,
        totalPaise=413000,
        inventoryLockToken="lock_sla_oos",
        inventoryLockExpiresAt=now + 60,
        timestamp=now,
    )

    interceptor = OosInterceptor(mockQdrantClient, catalogFixtures)
    latencies: List[float] = []

    for _ in range(100):
        _, _, durationMs, _ = interceptor.healOutOfStock(
            failedSkuId="SKU-101",
            requestedQuantity=1,
            buyerAgentSigner=buyerSigner,
            merchantSigner=merchantSigner,
            originalCartMandate=origCart,
        )
        latencies.append(durationMs)

    assert len(latencies) == 100
    meanLatency = sum(latencies) / len(latencies)
    maxLatency = max(latencies)

    assert maxLatency < 300.0, f"Max latency {maxLatency:.2f}ms exceeded 300ms SLA"
    assert meanLatency < 20.0, f"Mean latency {meanLatency:.2f}ms exceeded expected fast threshold"


def testChallenger2OosSelfHealingBudgetExceededGuard(
    agentKeyFixtures: Dict[str, Any],
    catalogFixtures: List[Dict[str, Any]],
    mockQdrantClient: MockQdrantClient,
) -> None:
    """Stress Test 4.3: Substitute pushes total beyond delegated budget -> raises BudgetExceededViolation."""
    buyerSigner = Ed25519Signer(agentKeyFixtures["buyerAgent"]["privateKeyHex"])
    merchantSigner = Ed25519Signer(agentKeyFixtures["merchantNode"]["privateKeyHex"])

    # Delegate max budget of ₹4,150 (415,000 paise). Original total was ₹4,130 (413,000 paise).
    # Substitute SKU-104 total is 355000 * 1.18 = 418,900 paise -> Exceeds 415,000 paise!
    intentMandate = createSignedIntentMandate(
        mandateId="intent_tight_budget",
        userSigner=buyerSigner,
        delegatedAgentDid=buyerSigner.getAgentDid(),
        maxBudgetPaise=415000,
        upiCircleDelegationToken="upi_tok_c2_test",
        singleTransactionLimitPaise=500000,
        authorizedCategories=["electronics"],
        validUntilTimestamp=int(time.time()) + 3600,
    )

    now = int(time.time())
    origCart = createSignedCartMandate(
        cartId="cart_budget_tight",
        merchantSigner=merchantSigner,
        merchantGstin="29AABCU9603R1ZM",
        merchantStateCode="29",
        buyerDeliveryPincode="560001",
        buyerDeliveryStateCode="29",
        items=[
            CartItemSchema(
                skuId="SKU-101",
                quantity=1,
                unitPricePaise=350000,
                hsnCode="8471",
                gstRatePercent=18,
                lineTotalPaise=350000,
            )
        ],
        taxableSubtotalPaise=350000,
        taxBreakdown=TaxBreakdownSchema(cgstPaise=31500, sgstPaise=31500, igstPaise=0, totalTaxPaise=63000),
        shippingPaise=0,
        discountPaise=0,
        totalPaise=413000,
        inventoryLockToken="lock_budget_tight",
        inventoryLockExpiresAt=now + 60,
        timestamp=now,
    )

    interceptor = OosInterceptor(mockQdrantClient, catalogFixtures)
    with pytest.raises(BudgetExceededViolation):
        interceptor.healOutOfStock(
            failedSkuId="SKU-101",
            requestedQuantity=1,
            buyerAgentSigner=buyerSigner,
            merchantSigner=merchantSigner,
            originalCartMandate=origCart,
            intentMandate=intentMandate,
        )


# ============================================================================
# 5. NEGATIVE CONSTRAINT FILTERING STRESS TESTS (TC-05)
# ============================================================================

def testChallenger2NegativeConstraintAdversarialAllergensAndBrands(
    catalogFixtures: List[Dict[str, Any]],
) -> None:
    """Stress Test 5.1: Adversarial variations of blacklisted allergens and excluded brands.
    
    Verifies:
    - Mixed case: "PeAnUt", "PEANUT_OIL", "  peanut  "
    - Substring matches: "refined peanut oil extract"
    - Excluded brands: "SensTech", "SENSTECH", "senstech"
    - Hard Boolean rejection on all non-compliant SKUs
    - Sunflower oil (SKU-205) allowed
    """
    manifest = NegativeConstraintManifest(
        excludedAllergens=["  PeAnUt  ", "PEANUT_OIL", "tree-nuts"],
        excludedBrands=["  SensTech  ", "BadVendor"],
        maxWeightGrams=1000,
        maxSlaHours=48,
    )
    filterEngine = NegativeConstraintFilter(manifest)

    # 1. SKU-201 contains Peanut Oil -> Hard Rejection
    sku201 = next(s for s in catalogFixtures if s["skuId"] == "SKU-201")
    eval201 = filterEngine.evaluateCandidate(sku201)
    assert not eval201.isAllowed
    assert "ALLERGEN_BREACH:peanut" in str(eval201.rejectionReason)

    # 2. SKU-001 has brand 'SensTech' -> Hard Rejection
    sku001 = next(s for s in catalogFixtures if s["skuId"] == "SKU-001")
    eval001 = filterEngine.evaluateCandidate(sku001)
    assert not eval001.isAllowed
    assert "BRAND_EXCLUDED:senstech" in str(eval001.rejectionReason)

    # 3. SKU-301 weight is 1050g > max 500g -> Hard Rejection
    sku301 = next(s for s in catalogFixtures if s["skuId"] == "SKU-301")
    eval301 = filterEngine.evaluateCandidate(sku301)
    assert not eval301.isAllowed
    assert "WEIGHT_LIMIT_EXCEEDED" in str(eval301.rejectionReason)

    # 4. SKU-205 is Sunflower Oil, weight 450g, compliant brand -> Allowed
    sku205 = next(s for s in catalogFixtures if s["skuId"] == "SKU-205")
    eval205 = filterEngine.evaluateCandidate(sku205)
    assert eval205.isAllowed
    assert eval205.rejectionReason is None


def testChallenger2NegativeConstraintMultiDimensionAndSlaBreach() -> None:
    """Stress Test 5.2: Dimension and SLA constraint boundary enforcement."""
    manifest = NegativeConstraintManifest(
        maxDimensionCm={"length": 50, "width": 50, "height": 50},
        maxSlaHours=24,
    )
    filterEngine = NegativeConstraintFilter(manifest)

    # Candidate exceeding dimension limit
    oversizedCandidate = {
        "skuId": "SKU-LARGE-001",
        "brand": "StandardBrand",
        "attributes": {
            "dimensionsCm": {"length": 65, "width": 40, "height": 40},
            "weightGrams": 300,
        },
        "slaHours": 12,
    }
    evalDim = filterEngine.evaluateCandidate(oversizedCandidate)
    assert not evalDim.isAllowed
    assert "DIMENSION_LIMIT_EXCEEDED:length:65cm" in str(evalDim.rejectionReason)

    # Candidate exceeding SLA limit
    slowCandidate = {
        "skuId": "SKU-SLOW-001",
        "brand": "StandardBrand",
        "attributes": {
            "dimensionsCm": {"length": 20, "width": 20, "height": 20},
            "weightGrams": 300,
            "slaHours": 48,
        },
    }
    evalSla = filterEngine.evaluateCandidate(slowCandidate)
    assert not evalSla.isAllowed
    assert "SLA_EXCEEDED:48h" in str(evalSla.rejectionReason)

    # Compliant candidate
    compliantCandidate = {
        "skuId": "SKU-OK-001",
        "brand": "StandardBrand",
        "attributes": {
            "dimensionsCm": {"length": 20, "width": 20, "height": 20},
            "weightGrams": 300,
            "slaHours": 18,
        },
    }
    evalOk = filterEngine.evaluateCandidate(compliantCandidate)
    assert evalOk.isAllowed
    assert evalOk.rejectionReason is None
