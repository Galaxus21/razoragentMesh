"""Adversarial Benchmark: Webhooks, Bullion Pricing, Cross-Tenant Isolation, and Signature Invariance."""

from decimal import Decimal
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
from razoragentMesh.tests.mockInfraHelpers import MockRedisAsync

sampleWebhookSecret: str = "whsec_test_secret_key_12345"
forgedSignatureHeader: str = "0000000000000000000000000000000000000000000000000000000000000000"
testPrivateKeyHex: str = "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60"


def testTc17WebhookBitFlipAndHeaderForgery() -> None:
    """TC-17: Constant-time HMAC-SHA256 rejection on 1-byte payload mutation and header forgery."""
    payloadBytes = b'{"event":"payment.captured","payload":{"payment":{"entity":{"id":"pay_test_001","amount":500000}}}}'
    validSignature = computeWebhookSignature(payloadBytes, sampleWebhookSecret)

    assert verifyRazorpayWebhookSignature(payloadBytes, validSignature, sampleWebhookSecret) is True

    tamperedBytes = bytearray(payloadBytes)
    tamperedBytes[10] = tamperedBytes[10] ^ 0x01
    tamperedPayload = bytes(tamperedBytes)

    assert verifyRazorpayWebhookSignature(tamperedPayload, validSignature, sampleWebhookSecret) is False
    with pytest.raises(WebhookSignatureVerificationException):
        verifyRazorpayWebhookSignature(tamperedPayload, validSignature, sampleWebhookSecret, raiseOnFailure=True)

    assert verifyRazorpayWebhookSignature(payloadBytes, forgedSignatureHeader, sampleWebhookSecret) is False
    with pytest.raises(WebhookSignatureVerificationException):
        verifyRazorpayWebhookSignature(payloadBytes, forgedSignatureHeader, sampleWebhookSecret, raiseOnFailure=True)


@pytest.mark.asyncio
async def testTc18SubSecondBullionFlashCrashAndStaleQuoteDefense() -> None:
    """TC-18: Sub-second bullion spot price quote expiration defense and audit trail."""
    oracle = createInMemorySpotRateOracle()
    t0 = 1700000000
    rule = DynamicPricingRule(
        pricingType="FORMULA_SPOT_LINKED", oracleFeedSymbol="MCX_GOLD_24K_INR_PER_GRAM",
        netWeightGrams=Decimal("10.0"), purityMultiplier=Decimal("1.0"),
        makingChargesType="PERCENTAGE_OF_GOLD", makingChargesPaise=300,
        stoneChargesPaise=0, maxQuoteTtlSeconds=60,
    )
    quote = await computeSpotLinkedQuote(rule=rule, oracle=oracle, gstRatePercent=3, currentTimestamp=t0)
    assert quote.expiresAtTimestamp == t0 + 60

    verifyQuoteNotExpired(quote.expiresAtTimestamp, currentTimestamp=t0 + 59)
    with pytest.raises(StalePriceQuoteException) as excInfo:
        verifyQuoteNotExpired(quote.expiresAtTimestamp, currentTimestamp=t0 + 61)
    assert excInfo.value.deltaMs == 1000


def _buildMerchantAndListing(name: str, gstin: str, acc: str, email: str, pin: str, sku: str, title: str, cat: str, hsn: str, gst: int, price: int, stock: int):
    req = MerchantRegistrationRequest(
        businessName=name, gstin=gstin, razorpayAccountId=acc, contactEmail=email, originPincode=pin,
    )
    record = generateMerchantKeypair(req)
    listing = UniversalProductListing(
        skuId=sku, merchantDid=record.merchantDid, title=title, category=cat,
        description=title, hsnCode=hsn, gstRatePercent=gst, baseUnitPricePaise=price,
        availableStock=stock, originPincode=pin,
    )
    return record, listing


@pytest.mark.asyncio
async def testTc19CrossTenantDidIsolation() -> None:
    """TC-19: Cross-tenant DID isolation preventing unauthorized policy queries and catalog bleed."""
    redisClient = MockRedisAsync()
    recA, listA = _buildMerchantAndListing("Alpha Bullion", "29ABCDE1234F1ZW", "acc_alpha_01", "a@bullion.in", "560001", "SKU-GOLD-ALPHA-01", "24K Gold Bar 10g", "bullion", "7108", 3, 6795000, 20)
    recB, listB = _buildMerchantAndListing("Beta Electronics", "27ABCDE1234F1Z0", "acc_beta_02", "b@elec.in", "400001", "SKU-PHONE-BETA-02", "Smartphone Model X", "electronics", "8517", 18, 4500000, 50)

    policyA = NegotiationPolicy(
        merchantDid=recA.merchantDid, marginFloorBps=800, minimumOrderQuantity=1,
        autoAcceptSpreadPaise=5000, maxNegotiationTurns=5, createdAtTimestamp=1700000000, updatedAtTimestamp=1700000000,
    )
    await redisClient.set(f"{redisMerchantPolicyKeyPrefix}{recA.merchantDid}", policyA.model_dump_json())
    assert await redisClient.get(f"{redisMerchantPolicyKeyPrefix}{recB.merchantDid}") is None

    catalog = CatalogManager(redisClient=redisClient)
    await catalog.upsertSku(listA)
    await catalog.upsertSku(listB)

    skusA = await catalog.listMerchantSkus(recA.merchantDid)
    skusB = await catalog.listMerchantSkus(recB.merchantDid)
    assert skusA == ["SKU-GOLD-ALPHA-01"] and skusB == ["SKU-PHONE-BETA-02"]
    assert "SKU-PHONE-BETA-02" not in skusA and "SKU-GOLD-ALPHA-01" not in skusB


def testTc24Ed25519SignatureMalleabilityAndJcsKeyReordering() -> None:
    """TC-24: RFC 8785 JCS canonicalization invariance across key re-orderings in Ed25519 signatures."""
    signer = Ed25519Signer(privateKeyHex=testPrivateKeyHex)
    publicKeyHex = signer.getPublicKeyHex()

    payloadA = {"amountPaise": 500000, "buyerDid": "did:agent:buyer-01", "mandateId": "man_order_101", "nonce": "non_test_nonce_999", "sellerDid": "did:agent:merchant-nexus-01"}
    payloadB = {"sellerDid": "did:agent:merchant-nexus-01", "nonce": "non_test_nonce_999", "mandateId": "man_order_101", "buyerDid": "did:agent:buyer-01", "amountPaise": 500000}

    bytesA = canonicalizeJson(payloadA)
    bytesB = canonicalizeJson(payloadB)
    assert bytesA == bytesB

    sigHex = signer.signPayload(payloadA)
    assert Ed25519Verifier.verifyPayloadSignature(publicKeyHex, payloadA, sigHex) is True
    assert Ed25519Verifier.verifyPayloadSignature(publicKeyHex, payloadB, sigHex) is True
    assert Ed25519Verifier.verifySignature(publicKeyHex, bytesB, sigHex) is True
