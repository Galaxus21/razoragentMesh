"""Empirical Challenger 2 Test Suite: Gateway HMAC Webhook Security and Bit-Flip Verification."""

import hashlib
import hmac
import json
import pytest

from razoragentMesh.packages.mandateEngine.settlement.webhookVerifier import (
    verifyRazorpayWebhookSignature,
)
from razoragentMesh.packages.x402Gateway.src.alerts.priceDropAlertManager import (
    PriceDropWebhookPayload,
    eventPriceDropTriggered,
)

testSkuIdChair: str = "SKU-CHAIR-001"
testTargetPricePaise: int = 350000
testActivePricePaise: int = 340000
testBuyerAgentId: str = "did:mesh:buyer_challenger2"
testCallbackUrl: str = "https://buyer-agent.mesh/api/v1/webhook"
testWebhookSecret: str = "whsec_adversarial_test_secret_2026"


def testHmacWebhookExhaustiveBitFlip() -> None:
    """Challenge 2A: Verifies constant-time HMAC rejection across exhaustive bit mutations."""
    now = 1724480000
    payload = PriceDropWebhookPayload(
        event=eventPriceDropTriggered, alertId="alert_test12345678",
        skuId=testSkuIdChair, buyerAgentId=testBuyerAgentId,
        targetPricePaise=testTargetPricePaise, activePricePaise=testActivePricePaise,
        savingsPaise=10000, triggeredAtUnix=now, callbackUrl=testCallbackUrl,
    )
    payloadBytes = json.dumps(payload.model_dump(), separators=(",", ":"), sort_keys=True).encode("utf-8")
    validSig = hmac.new(testWebhookSecret.encode("utf-8"), payloadBytes, hashlib.sha256).hexdigest()
    assert verifyRazorpayWebhookSignature(payloadBytes, validSig, testWebhookSecret) is True

    step = max(1, len(payloadBytes) // 50)
    for byteIdx in range(0, len(payloadBytes), step):
        originalByte = payloadBytes[byteIdx]
        for bitIdx in range(8):
            corruptedBytes = bytearray(payloadBytes)
            corruptedBytes[byteIdx] = originalByte ^ (1 << bitIdx)
            assert verifyRazorpayWebhookSignature(bytes(corruptedBytes), validSig, testWebhookSecret) is False


def testHmacWebhookPayloadFieldTampering() -> None:
    """Challenge 2B: Verifies signature verification failure upon individual field tampering."""
    now = 1724480000
    basePayloadDict = {
        "event": eventPriceDropTriggered, "alertId": "alert_test12345678",
        "skuId": testSkuIdChair, "buyerAgentId": testBuyerAgentId,
        "targetPricePaise": testTargetPricePaise, "activePricePaise": testActivePricePaise,
        "savingsPaise": 10000, "triggeredAtUnix": now, "callbackUrl": testCallbackUrl,
    }
    payloadBytes = json.dumps(basePayloadDict, separators=(",", ":"), sort_keys=True).encode("utf-8")
    validSig = hmac.new(testWebhookSecret.encode("utf-8"), payloadBytes, hashlib.sha256).hexdigest()

    tamperingCases = [
        ("targetPricePaise", 400000), ("activePricePaise", 350000), ("savingsPaise", 0),
        ("skuId", "SKU-TABLE-999"), ("buyerAgentId", "did:mesh:attacker"), ("triggeredAtUnix", now + 100),
    ]
    for key, tamperedVal in tamperingCases:
        tamperedDict = dict(basePayloadDict)
        tamperedDict[key] = tamperedVal
        tamperedBytes = json.dumps(tamperedDict, separators=(",", ":"), sort_keys=True).encode("utf-8")
        assert verifyRazorpayWebhookSignature(tamperedBytes, validSig, testWebhookSecret) is False


def testHmacWebhookHeaderForgeryAndSecretMismatch() -> None:
    """Challenge 2C: Verifies rejection on secret mismatch or corrupted signature strings."""
    payloadBytes = b'{"event":"test"}'
    validSig = hmac.new(testWebhookSecret.encode("utf-8"), payloadBytes, hashlib.sha256).hexdigest()

    assert verifyRazorpayWebhookSignature(payloadBytes, validSig, "wrong_secret_123") is False
    forgedSig = ("0" if validSig[0] != "0" else "1") + validSig[1:]
    assert verifyRazorpayWebhookSignature(payloadBytes, forgedSig, testWebhookSecret) is False
    assert verifyRazorpayWebhookSignature(payloadBytes, validSig[:10], testWebhookSecret) is False
    assert verifyRazorpayWebhookSignature(payloadBytes, "", testWebhookSecret) is False
