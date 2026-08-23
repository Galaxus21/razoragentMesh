"""Adversarial Benchmark Module 4: Bullion pricing, security invariants, and protocol boundaries."""

from decimal import Decimal
from typing import Any, Dict, List
import pytest

from razoragentMesh.packages.mandateEngine.crypto.ed25519Signer import Ed25519Signer
from razoragentMesh.packages.mandateEngine.crypto.ed25519Verifier import Ed25519Verifier
from razoragentMesh.packages.mandateEngine.crypto.jcsCanonicalizer import canonicalizeJson
from razoragentMesh.packages.mandateEngine.settlement.settlementExceptions import (
    WebhookSignatureVerificationException,
)
from razoragentMesh.packages.mandateEngine.settlement.webhookVerifier import (
    computeWebhookSignature,
    verifyRazorpayWebhookSignature,
)
from razoragentMesh.packages.merchantApi.src.catalog.catalogManager import CatalogManager
from razoragentMesh.packages.merchantApi.src.catalog.pricingFormulaEngine import (
    StalePriceQuoteException,
    computeSpotLinkedQuote,
    verifyQuoteNotExpired,
)
from razoragentMesh.packages.merchantApi.src.catalog.spotRateOracle import (
    createInMemorySpotRateOracle,
)
from razoragentMesh.packages.merchantApi.src.constants.merchantConstants import (
    redisMerchantPolicyKeyPrefix,
)
from razoragentMesh.packages.merchantApi.src.onboarding.merchantRegistrar import (
    generateMerchantKeypair,
)
from razoragentMesh.packages.merchantApi.src.schemas.dynamicPricingSchema import (
    DynamicPricingRule,
)
from razoragentMesh.packages.merchantApi.src.schemas.merchantSchema import (
    MerchantRegistrationRequest,
)
from razoragentMesh.packages.merchantApi.src.schemas.policySchema import (
    NegotiationPolicy,
)
from razoragentMesh.packages.merchantApi.src.schemas.universalProductSchema import (
    UniversalProductListing,
)
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
from razoragentMesh.tests.mockInfraHelpers import MockRedisAsync

# Benchmark Test Constants in camelCase
sampleWebhookSecret: str = "whsec_test_secret_key_12345"
forgedSignatureHeader: str = "0000000000000000000000000000000000000000000000000000000000000000"
testClientIpAddress: str = "192.168.1.100"
testPrivateKeyHex: str = "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60"
testBuyerAgentDid: str = "did:agent:buyer-procurement-01"


def testTc17WebhookBitFlipAndHeaderForgery() -> None:
    """TC-17: Constant-time HMAC-SHA256 rejection on 1-byte payload mutation and header forgery."""
    payloadBytes = b'{"event":"payment.captured","payload":{"payment":{"entity":{"id":"pay_test_001","amount":500000}}}}'
    validSignature = computeWebhookSignature(payloadBytes, sampleWebhookSecret)

    assert verifyRazorpayWebhookSignature(payloadBytes, validSignature, sampleWebhookSecret) is True

    # Mutate 1 byte (bit-flip) in the payload body
    tamperedBytes = bytearray(payloadBytes)
    tamperedBytes[10] = tamperedBytes[10] ^ 0x01
    tamperedPayload = bytes(tamperedBytes)

    assert verifyRazorpayWebhookSignature(tamperedPayload, validSignature, sampleWebhookSecret) is False
    with pytest.raises(WebhookSignatureVerificationException):
        verifyRazorpayWebhookSignature(
            tamperedPayload,
            validSignature,
            sampleWebhookSecret,
            raiseOnFailure=True,
        )

    # Test forged signature header against pristine payload
    assert verifyRazorpayWebhookSignature(payloadBytes, forgedSignatureHeader, sampleWebhookSecret) is False
    with pytest.raises(WebhookSignatureVerificationException):
        verifyRazorpayWebhookSignature(
            payloadBytes,
            forgedSignatureHeader,
            sampleWebhookSecret,
            raiseOnFailure=True,
        )


@pytest.mark.asyncio
async def testTc18SubSecondBullionFlashCrashAndStaleQuoteDefense() -> None:
    """TC-18: Sub-second bullion spot price quote expiration defense and audit trail."""
    oracle = createInMemorySpotRateOracle()
    t0 = 1700000000
    rule = DynamicPricingRule(
        pricingType="FORMULA_SPOT_LINKED",
        oracleFeedSymbol="MCX_GOLD_24K_INR_PER_GRAM",
        netWeightGrams=Decimal("10.0"),
        purityMultiplier=Decimal("1.0"),
        makingChargesType="PERCENTAGE_OF_GOLD",
        makingChargesPaise=300,
        stoneChargesPaise=0,
        maxQuoteTtlSeconds=60,
    )

    quote = await computeSpotLinkedQuote(
        rule=rule,
        oracle=oracle,
        gstRatePercent=3,
        currentTimestamp=t0,
    )

    assert quote.expiresAtTimestamp == t0 + 60

    # 1 second before expiry: settlement validation must succeed
    verifyQuoteNotExpired(quote.expiresAtTimestamp, currentTimestamp=t0 + 59)

    # Exactly 1 second past expiry (t0 + 61): must raise StalePriceQuoteException with 1000ms delta
    with pytest.raises(StalePriceQuoteException) as excInfo:
        verifyQuoteNotExpired(quote.expiresAtTimestamp, currentTimestamp=t0 + 61)

    assert excInfo.value.deltaMs == 1000


@pytest.mark.asyncio
async def testTc19CrossTenantDidIsolation() -> None:
    """TC-19: Cross-tenant DID isolation preventing unauthorized policy queries and catalog bleed."""
    redisClient = MockRedisAsync()
    reqA = MerchantRegistrationRequest(
        businessName="Merchant Alpha Bullion",
        gstin="29ABCDE1234F1Z5",
        razorpayAccountId="acc_alpha_01",
        contactEmail="alpha@bullion.in",
        originPincode="560001",
    )
    reqB = MerchantRegistrationRequest(
        businessName="Merchant Beta Electronics",
        gstin="27ABCDE1234F1Z7",
        razorpayAccountId="acc_beta_02",
        contactEmail="beta@electronics.in",
        originPincode="400001",
    )

    recordA = generateMerchantKeypair(reqA)
    recordB = generateMerchantKeypair(reqB)

    # Store policy for Merchant A
    policyA = NegotiationPolicy(
        merchantDid=recordA.merchantDid,
        marginFloorBps=800,
        minimumOrderQuantity=1,
        autoAcceptSpreadPaise=5000,
        maxNegotiationTurns=5,
        createdAtTimestamp=1700000000,
        updatedAtTimestamp=1700000000,
    )
    policyKeyA = f"{redisMerchantPolicyKeyPrefix}{recordA.merchantDid}"
    await redisClient.set(policyKeyA, policyA.model_dump_json())

    # Tenant B queries its own policy -> None (not configured)
    policyKeyB = f"{redisMerchantPolicyKeyPrefix}{recordB.merchantDid}"
    retrievedPolicyB = await redisClient.get(policyKeyB)
    assert retrievedPolicyB is None

    # Upsert catalog listings for both merchants
    catalogManager = CatalogManager(redisClient=redisClient)
    listingA = UniversalProductListing(
        skuId="SKU-GOLD-ALPHA-01",
        merchantDid=recordA.merchantDid,
        title="24K Gold Bar 10g",
        category="bullion",
        description="MCX benchmark gold bar",
        hsnCode="7108",
        gstRatePercent=3,
        baseUnitPricePaise=6795000,
        availableStock=20,
        originPincode="560001",
    )
    listingB = UniversalProductListing(
        skuId="SKU-PHONE-BETA-02",
        merchantDid=recordB.merchantDid,
        title="Smartphone Model X",
        category="electronics",
        description="5G smartphone",
        hsnCode="8517",
        gstRatePercent=18,
        baseUnitPricePaise=4500000,
        availableStock=50,
        originPincode="400001",
    )

    await catalogManager.upsertSku(listingA)
    await catalogManager.upsertSku(listingB)

    # Verify merchant catalog query returns only tenant-owned SKUs
    skusA = await catalogManager.listMerchantSkus(recordA.merchantDid)
    skusB = await catalogManager.listMerchantSkus(recordB.merchantDid)

    assert skusA == ["SKU-GOLD-ALPHA-01"]
    assert skusB == ["SKU-PHONE-BETA-02"]
    assert "SKU-PHONE-BETA-02" not in skusA
    assert "SKU-GOLD-ALPHA-01" not in skusB


def testTc21DynamicPowDifficultyEscalation() -> None:
    """TC-21: Dynamic PoW difficulty escalation from 4 to 5 leading zeros under rapid ingress load."""
    shield = IngressAntiSpamShield()

    # Initial request from client -> baseline difficulty 4 leading zeros
    baselineChallenge = shield.generateChallenge(clientIp=testClientIpAddress)
    assert baselineChallenge.powDifficultyZeros == 4

    # High load simulation (100+ requests) -> difficulty escalates to 5 leading zeros
    escalatedChallenge = shield.generateChallenge(
        clientIp=testClientIpAddress,
        requestCount=100,
    )
    assert escalatedChallenge.powDifficultyZeros == 5

    # Solve the 5-zero challenge
    validNonce = solvePoWChallenge(
        escalatedChallenge.challengeToken,
        difficultyZeros=5,
    )
    result = shield.validatePoWSubmission(
        escalatedChallenge.challengeToken,
        validNonce,
    )
    assert result.isValid is True
    assert result.computedDigest.startswith("00000")

    # A nonce satisfying only 4 zeros fails the 5-zero challenge
    challengeToken = shield.generateChallenge(clientIp=testClientIpAddress, requestCount=101).challengeToken
    insufficientNonce = solvePoWChallenge(challengeToken, difficultyZeros=4)
    if not shield.verifyPoWSolution(challengeToken, insufficientNonce, difficultyZeros=5):
        with pytest.raises(InvalidProofOfWorkException):
            shield.validatePoWSubmission(challengeToken, insufficientNonce, requiredDifficulty=5)


def testTc22CombinatorialAstConstraintSatisfaction() -> None:
    """TC-22: 5-dimension combinatorial AST constraint satisfaction over 10 SKU candidates."""
    manifest = NegativeConstraintManifest(
        excludedAllergens=["peanut", "gluten"],
        excludedActiveSalts=["paracetamol"],
        requireOtcOnly=True,
        requireVeg=True,
        maxWeightGrams=500,
    )
    filterEngine = NegativeConstraintFilter(manifest)

    candidateSkus: List[Dict[str, Any]] = [
        {"skuId": "SKU-01", "brand": "BrandA", "attributes": {"allergens": ["peanut"], "weightGrams": 200, "isVeg": True}},
        {"skuId": "SKU-02", "brand": "BrandB", "attributes": {"allergens": ["gluten"], "weightGrams": 300, "isVeg": True}},
        {"skuId": "SKU-03", "brand": "PharmaA", "pharmaFacet": {"activeSalt": "paracetamol"}, "attributes": {"weightGrams": 100, "isVeg": True}},
        {"skuId": "SKU-04", "brand": "PharmaB", "pharmaFacet": {"prescriptionRequired": True}, "attributes": {"weightGrams": 150, "isVeg": True}},
        {"skuId": "SKU-05", "brand": "FoodA", "fmcgFacet": {"isVeg": False}, "attributes": {"weightGrams": 250}},
        {"skuId": "SKU-06", "brand": "FoodB", "fmcgFacet": {}, "attributes": {"weightGrams": 200}},  # Missing isVeg -> fail-closed False
        {"skuId": "SKU-07", "brand": "ItemA", "attributes": {"allergens": [], "weightGrams": 650, "isVeg": True}},
        {"skuId": "SKU-08", "brand": "ItemB", "attributes": {"allergens": ["peanut"], "weightGrams": 750, "isVeg": False}},
        {"skuId": "SKU-09", "brand": "SafeFoodA", "attributes": {"allergens": [], "weightGrams": 250, "isVeg": True}},
        {"skuId": "SKU-10", "brand": "SafeFoodB", "attributes": {"allergens": [], "weightGrams": 450, "isVeg": True}},
    ]

    results = [filterEngine.evaluateCandidate(sku) for sku in candidateSkus]
    allowedCandidates = [res for res in results if res.isAllowed]
    rejectedCandidates = [res for res in results if not res.isAllowed]

    assert len(allowedCandidates) == 2
    assert len(rejectedCandidates) == 8
    assert {c.skuId for c in allowedCandidates} == {"SKU-09", "SKU-10"}

    # Assert specific failure reasons
    rejections = {res.skuId: res.rejectionReason for res in rejectedCandidates}
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
        skuId="SKU-CHAIR-001",
        quantity=10,
        escrowBalancePaise=500,
        sellerCostFloorPaise=300000,
    )

    # Turn 1: Valid initial offers
    step1 = negotiator.executeTurn(turnNumber=1, buyerBidPaise=330000, sellerAskPaise=350000)
    assert step1.isConverged is False
    assert len(negotiator.turnHistory) == 1
    assert negotiator.escrowBalancePaise == 450

    # Turn 2: Buyer bid regression (325000 < 330000) -> violation
    with pytest.raises(NonMonotonicConcessionViolation):
        negotiator.executeTurn(turnNumber=2, buyerBidPaise=325000, sellerAskPaise=345000)

    # Verify state is uncorrupted (turn history and escrow preserved)
    assert len(negotiator.turnHistory) == 1
    assert negotiator.escrowBalancePaise == 450

    # Turn 2: Seller ask escalation (355000 > 350000) -> violation
    with pytest.raises(NonMonotonicConcessionViolation):
        negotiator.executeTurn(turnNumber=2, buyerBidPaise=332000, sellerAskPaise=355000)

    assert len(negotiator.turnHistory) == 1
    assert negotiator.escrowBalancePaise == 450

    # Turn 2: Valid concessions (buyer 335000 >= 330000, seller 345000 <= 350000) -> success
    step2 = negotiator.executeTurn(turnNumber=2, buyerBidPaise=335000, sellerAskPaise=345000)
    assert step2.turnNumber == 2
    assert step2.spreadPaise == 10000
    assert len(negotiator.turnHistory) == 2
    assert negotiator.escrowBalancePaise == 400


def testTc24Ed25519SignatureMalleabilityAndJcsKeyReordering() -> None:
    """TC-24: RFC 8785 JCS canonicalization invariance across key re-orderings in Ed25519 signatures."""
    signer = Ed25519Signer(privateKeyHex=testPrivateKeyHex)
    publicKeyHex = signer.getPublicKeyHex()

    # Dictionary with key ordering A
    payloadA = {
        "amountPaise": 500000,
        "buyerDid": "did:agent:buyer-01",
        "mandateId": "man_order_101",
        "nonce": "non_test_nonce_999",
        "sellerDid": "did:agent:merchant-nexus-01",
    }

    # Dictionary with completely reversed key ordering B
    payloadB = {
        "sellerDid": "did:agent:merchant-nexus-01",
        "nonce": "non_test_nonce_999",
        "mandateId": "man_order_101",
        "buyerDid": "did:agent:buyer-01",
        "amountPaise": 500000,
    }

    # RFC 8785 canonical bytes must be byte-for-byte identical
    bytesA = canonicalizeJson(payloadA)
    bytesB = canonicalizeJson(payloadB)
    assert bytesA == bytesB

    # Sign payload A
    sigHex = signer.signPayload(payloadA)

    # Detached signature must verify against both payload representations
    assert Ed25519Verifier.verifyPayloadSignature(publicKeyHex, payloadA, sigHex) is True
    assert Ed25519Verifier.verifyPayloadSignature(publicKeyHex, payloadB, sigHex) is True
    assert Ed25519Verifier.verifySignature(publicKeyHex, bytesB, sigHex) is True


def testTc25MicroEscrowPoolDepletionMidTurn() -> None:
    """TC-25: Micro-escrow pool exhaustion mid-turn with zero overdraft and invariant balance preservation."""
    escrowManager = EscrowSessionManager()
    session = escrowManager.createSession(
        buyerAgentDid=testBuyerAgentDid,
        initialHoldPaise=150,  # Exactly 3 turns × 50 paise
    )

    # Turns 1, 2, 3: Successful debits
    session, rem1, _ = escrowManager.debitSession(session.sessionToken, feePaise=50)
    assert rem1 == 100
    assert session.debitedTotalPaise == 50

    session, rem2, _ = escrowManager.debitSession(session.sessionToken, feePaise=50)
    assert rem2 == 50
    assert session.debitedTotalPaise == 100

    session, rem3, _ = escrowManager.debitSession(session.sessionToken, feePaise=50)
    assert rem3 == 0
    assert session.debitedTotalPaise == 150

    # Turn 4: Balance is 0 -> InsufficientEscrowBalanceException
    with pytest.raises(InsufficientEscrowBalanceException):
        escrowManager.debitSession(session.sessionToken, feePaise=50)

    # Verify zero negative balance and overdraft prevention
    finalSession = escrowManager.getSession(session.sessionToken)
    assert finalSession.remainingBalancePaise == 0
    assert finalSession.debitedTotalPaise == 150
    assert finalSession.totalTurnsDebited == 3
