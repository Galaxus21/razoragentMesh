"""Cross-compatibility and Mesh protocol conformance test suite for Python Buyer SDK."""

import pytest
from razoragentMesh.packages.mandateEngine import (
    CartMandate as EngineCartMandate,
    Ed25519Signer,
    Ed25519Verifier,
    ExecutionMandate as EngineExecutionMandate,
    IntentMandate as EngineIntentMandate,
    canonicalizeJson as engineCanonicalizeJson,
    computeMandateHash as engineComputeMandateHash,
    computeSha256Digest as engineComputeSha256Digest,
    generateKeyPair as engineGenerateKeyPair,
    validateBudgetGate,
    verifyMandateChain as engineVerifyMandateChain,
)

from razoragent_buyer_sdk import (
    AgentKeyManager,
    AgentMandateBuilder,
    CartItemSchema,
    CartMandate,
    ExecutionMandate,
    IntentMandate,
    PowSolver,
    TaxBreakdownSchema,
    canonicalizeAndHash,
    canonicalizeJson,
    computeMandateHash,
    computeSha256Digest,
    createAmendmentMandate,
    createCartMandate,
    createExecutionMandate,
    createIntentMandate,
    solvePoWChallenge,
    verifyPoWSolution,
)


def testCrossJcsCanonicalizationParity() -> None:
    """Verifies 100% byte-for-byte identity between SDK and MandateEngine JCS."""
    payloads = [
        {"zeta": 10, "alpha": 20, "nested": {"b": 2, "a": 1}},
        {"items": [{"sku": "SKU-01", "pricePaise": 50000}, {"sku": "SKU-02", "pricePaise": 25000}]},
        {"currency": "INR", "amountPaise": 100000, "tags": ["bulk", "express"]},
        {"active": True, "blocked": False, "meta": None},
    ]

    for p in payloads:
        sdkBytes = canonicalizeJson(p)
        engineBytes = engineCanonicalizeJson(p)
        assert sdkBytes == engineBytes

        sdkHash = computeSha256Digest(sdkBytes)
        engineHash = engineComputeSha256Digest(engineBytes)
        assert sdkHash == engineHash


def testCrossEd25519SigningAndVerification() -> None:
    """Verifies bidirectional Ed25519 signature interoperability."""
    # SDK Signer -> Engine Verifier
    sdkKm = AgentKeyManager.generate()
    payloadA = {"paymentId": "pay_live_test_001", "amountPaise": 450000}
    sigA = sdkKm.signPayload(payloadA)

    sdkVerifyResult = AgentKeyManager.verifyPayloadSignature(sdkKm.getPublicKeyHex(), payloadA, sigA)
    assert sdkVerifyResult is True

    engineVerifyResult = Ed25519Verifier.verifyPayloadSignature(sdkKm.getPublicKeyHex(), payloadA, sigA)
    assert engineVerifyResult is True

    # Engine Signer -> SDK Verifier
    enginePriv, _ = engineGenerateKeyPair()
    engineSigner = Ed25519Signer(enginePriv)
    payloadB = {"cartId": "cart_999", "shippingPaise": 5000}
    engineSig = engineSigner.signPayload(payloadB)

    engineSelfVerify = Ed25519Verifier.verifyPayloadSignature(engineSigner.getPublicKeyHex(), payloadB, engineSig)
    assert engineSelfVerify is True

    sdkCrossVerify = AgentKeyManager.verifyPayloadSignature(engineSigner.getPublicKeyHex(), payloadB, engineSig)
    assert sdkCrossVerify is True


def _buildCrossTestMandates(userKm: AgentKeyManager, agentKm: AgentKeyManager, merchantKm: AgentKeyManager):
    sdkIntent = createIntentMandate(
        mandateId="M-I-CROSS-001", userKeyManager=userKm, delegatedAgentDid=agentKm.getAgentDid(),
        maxBudgetPaise=1000000, upiCircleDelegationToken="upi_tok_cross_001",
        singleTransactionLimitPaise=600000, authorizedCategories=["electronics"],
        validUntilTimestamp=2000000000, nonce="nonce_cross_intent_001", timestamp=1700000000,
    )
    items = [CartItemSchema(skuId="SKU-CROSS-001", quantity=1, unitPricePaise=400000, hsnCode="8504", gstRatePercent=18, lineTotalPaise=400000)]
    tax = TaxBreakdownSchema(cgstPaise=36000, sgstPaise=36000, igstPaise=0, totalTaxPaise=72000)
    sdkCart = createCartMandate(
        cartId="M-C-CROSS-001", merchantKeyManager=merchantKm, merchantGstin="29AABCU9603R1ZJ",
        merchantStateCode="29", buyerDeliveryPincode="560001", buyerDeliveryStateCode="29",
        items=items, taxableSubtotalPaise=400000, taxBreakdown=tax, shippingPaise=0, discountPaise=0,
        totalPaise=472000, inventoryLockToken="lock_cross_001", inventoryLockExpiresAt=2000000000,
        nonce="nonce_cross_cart_001", timestamp=1700000000,
    )
    sdkExec = createExecutionMandate(
        executionId="M-E-CROSS-001", buyerKeyManager=agentKm, intentMandate=sdkIntent,
        cartMandate=sdkCart, settlementAmountPaise=472000, upiCircleToken="upi_tok_cross_001",
        nonce="nonce_cross_exec_001", timestamp=1700000000,
    )
    return sdkIntent, sdkCart, sdkExec


def testCrossMandateCreationAndEngineVerification() -> None:
    """Creates AP2 mandates via Python SDK and verifies them via MandateEngine enclave & BudgetGate."""
    userKm, agentKm, merchantKm = AgentKeyManager.generate(), AgentKeyManager.generate(), AgentKeyManager.generate()
    sdkIntent, sdkCart, sdkExec = _buildCrossTestMandates(userKm, agentKm, merchantKm)

    engIntent = EngineIntentMandate.model_validate(sdkIntent.model_dump())
    engCart = EngineCartMandate.model_validate(sdkCart.model_dump())
    engExec = EngineExecutionMandate.model_validate(sdkExec.model_dump())

    assert computeMandateHash(sdkIntent) == engineComputeMandateHash(engIntent)
    assert computeMandateHash(sdkCart) == engineComputeMandateHash(engCart)
    assert computeMandateHash(sdkExec) == engineComputeMandateHash(engExec)

    assert engineVerifyMandateChain(engIntent, engCart, engExec) is True
    assert validateBudgetGate(engIntent, engCart, engExec, currentTimestamp=1700000000, skuCategories=["electronics"]) is True


def testCrossDualSignedAmendmentMandate() -> None:
    """Verifies AmendmentMandate dual signatures against MandateEngine verifier."""
    agentKm, merchantKm = AgentKeyManager.generate(), AgentKeyManager.generate()
    items = [CartItemSchema(skuId="SKU-A", quantity=1, unitPricePaise=10000, hsnCode="8504", gstRatePercent=18, lineTotalPaise=10000)]
    tax = TaxBreakdownSchema(cgstPaise=900, sgstPaise=900, igstPaise=0, totalTaxPaise=1800)
    mkCart = lambda cid, lock: createCartMandate(
        cartId=cid, merchantKeyManager=merchantKm, merchantGstin="29AABCU9603R1ZJ", merchantStateCode="29",
        buyerDeliveryPincode="560001", buyerDeliveryStateCode="29", items=items, taxableSubtotalPaise=10000,
        taxBreakdown=tax, shippingPaise=0, discountPaise=0, totalPaise=11800, inventoryLockToken=lock,
        inventoryLockExpiresAt=2000000000,
    )
    cart1, cart2 = mkCart("C-01", "l1"), mkCart("C-02", "l2")

    amendment = createAmendmentMandate(
        amendmentId="M-A-CROSS-001", buyerKeyManager=agentKm, merchantKeyManager=merchantKm,
        previousCartMandate=cart1, newCartMandate=cart2,
        substitutedSkuMapping={"SKU-A": "SKU-B"}, priceDeltaPaise=0, amendmentReason="Cross SDK substitution",
    )
    unsignedDict = {
        "amendmentId": amendment.amendmentId, "amendmentReason": amendment.amendmentReason,
        "newCartMandateHash": amendment.newCartMandateHash, "nonce": amendment.nonce,
        "previousCartMandateHash": amendment.previousCartMandateHash, "priceDeltaPaise": amendment.priceDeltaPaise,
        "substitutedSkuMapping": amendment.substitutedSkuMapping, "timestamp": amendment.timestamp,
    }
    assert Ed25519Verifier.verifyPayloadSignature(agentKm.getPublicKeyHex(), unsignedDict, amendment.agentSignature) is True
    assert Ed25519Verifier.verifyPayloadSignature(merchantKm.getPublicKeyHex(), unsignedDict, amendment.merchantSignature) is True

