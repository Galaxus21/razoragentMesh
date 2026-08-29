"""Challenger 1: Mathematical, Nonce, and Cryptographic Invariants.

Tests:
1. Zero Floating Point Drift & Arithmetic Enclave Precision
2. Nonce Ledger Replay Prevention & NTP Drift Windowing
3. Ed25519 Cryptographic Integrity & Hash Chain Binding
"""

import asyncio
from decimal import Decimal
from fractions import Fraction
from typing import Any, Dict
import pytest

from razoragentMesh.packages.mandateEngine.verification.arithmeticEnclave import (
    computeCartSettlementTotal,
    computeGstBreakdown,
    computeLineItemTotal,
    computeTcsWithholding,
    validateIntegerPaise,
)
from razoragentMesh.tests.fixtures.taxFixtures import (
    getCanonicalOddPaiseScenarios,
)
from razoragentMesh.packages.mandateEngine.mandates.cartMandateSchema import (
    CartItemSchema,
    TaxBreakdownSchema,
)
from razoragentMesh.packages.mandateEngine.crypto.cryptoKeyUtils import (
    extractPublicKeyFromDid,
)
from razoragentMesh.packages.mandateEngine.crypto.ed25519Signer import Ed25519Signer
from razoragentMesh.packages.mandateEngine.crypto.ed25519Verifier import Ed25519Verifier
from razoragentMesh.packages.mandateEngine.crypto.jcsCanonicalizer import (
    canonicalizeAndHash,
    canonicalizeJson,
)
from razoragentMesh.packages.mandateEngine.mandates.mandateFactory import (
    createSignedCartMandate,
    createSignedExecutionMandate,
    createSignedIntentMandate,
    verifyMandateHashChain,
)
from razoragentMesh.packages.mandateEngine.nonce.nonceLedger import NonceLedger
from razoragentMesh.packages.mandateEngine.settlement.settlementExceptions import (
    ArithmeticDriftException,
    FutureTimestampException,
    MandateHashChainMismatchException,
    NonceReplayException,
    SignatureVerificationFailedException,
    TimestampExpiredException,
)


class TestZeroFloatingPointDrift:
    """Empirical stress tests for floating-point rejection and integer arithmetic."""

    @pytest.mark.parametrize(
        "maliciousInput",
        [
            0.0, -0.0, 1.5, 1976.501, -1976.501, 1e-5, 1e10,
            float("inf"), float("-inf"), float("nan"),
            True, False, "100", "1976.50",
            Decimal("100.5"), Decimal("100"), Fraction(10, 2),
            None, [], {}, [100], {"amount": 100},
        ],
    )
    def testValidateIntegerPaiseRejectsNonStrictInt(self, maliciousInput: Any) -> None:
        """Asserts that any type other than pure int is rejected with ArithmeticDriftException."""
        with pytest.raises(ArithmeticDriftException):
            validateIntegerPaise(maliciousInput, "testField")

    def testLineItemCalculationBoundaryAndFloats(self) -> None:
        """Asserts boundary and negative cases in computeLineItemTotal."""
        assert computeLineItemTotal(100, 5) == 500
        assert computeLineItemTotal(0, 5) == 0

        with pytest.raises(ArithmeticDriftException):
            computeLineItemTotal(-100, 5)
        with pytest.raises(ArithmeticDriftException):
            computeLineItemTotal(100, 0)
        with pytest.raises(ArithmeticDriftException):
            computeLineItemTotal(100, -1)
        with pytest.raises(ArithmeticDriftException):
            computeLineItemTotal(100.5, 2)  # type: ignore
        with pytest.raises(ArithmeticDriftException):
            computeLineItemTotal(100, 2.5)  # type: ignore

    def testGstPennyConservationFuzzing(self) -> None:
        """Fuzzes odd taxable amounts across all standard GST tax rates (0, 5, 12, 18, 28%)."""
        for scenario in getCanonicalOddPaiseScenarios():
            gst = computeGstBreakdown(scenario.taxablePaise, scenario.gstRatePercent, isIntraState=scenario.isIntraState)
            assert gst.cgstPaise == scenario.expectedCgstPaise
            assert gst.sgstPaise == scenario.expectedSgstPaise
            assert gst.igstPaise == scenario.expectedIgstPaise
            assert gst.totalTaxPaise == scenario.expectedTotalTaxPaise
            assert gst.cgstPaise + gst.sgstPaise + gst.igstPaise == gst.totalTaxPaise

        rates = [0, 5, 12, 18, 28]
        oddAmounts = [1, 2, 3, 7, 13, 99, 101, 103, 333, 999, 1976501, 10000000007]
        for amt in oddAmounts:
            for rate in rates:
                gstIntra = computeGstBreakdown(amt, rate, isIntraState=True)
                assert gstIntra.cgstPaise == gstIntra.sgstPaise
                assert gstIntra.cgstPaise + gstIntra.sgstPaise == gstIntra.totalTaxPaise
                assert gstIntra.totalTaxPaise == 2 * ((amt * rate) // 200)

                gstInter = computeGstBreakdown(amt, rate, isIntraState=False)
                assert gstInter.igstPaise == gstInter.totalTaxPaise
                assert gstInter.totalTaxPaise == (amt * rate) // 100

    def testTcsWithholdingIntraAndInterState(self) -> None:
        """Asserts TCS withholding computation exactness (0.5% + 0.5% intra, 1.0% inter)."""
        for scenario in getCanonicalOddPaiseScenarios():
            tcs = computeTcsWithholding(scenario.taxablePaise, isIntraState=scenario.isIntraState)
            assert tcs["totalTcsPaise"] == scenario.expectedTcsPaise
            if scenario.isIntraState:
                assert tcs["tcsCgstPaise"] == tcs["tcsSgstPaise"]
            else:
                assert tcs["tcsIgstPaise"] == scenario.expectedTcsPaise

    def testCartSettlementTotalWithNegativeDiscountBreach(self) -> None:
        """Asserts that discount exceeding gross amount raises ArithmeticDriftException."""
        with pytest.raises(ArithmeticDriftException):
            computeCartSettlementTotal(taxableSubtotalPaise=1000, totalTaxPaise=180, shippingPaise=50, discountPaise=2000)

    def testJcsCanonicalizerRecursivelyTrapsNestedFloats(self) -> None:
        """Asserts that deep nested floats in dicts, lists, sets are intercepted."""
        nestedPayload = {
            "level1": {
                "level2": [
                    {"valid": 100},
                    {"nestedList": [1, 2, 3.14159]},
                ]
            }
        }
        with pytest.raises(ArithmeticDriftException):
            canonicalizeJson(nestedPayload)

        setWithFloat = {"a": {1, 2, 3.5}}
        with pytest.raises(ArithmeticDriftException):
            canonicalizeJson(setWithFloat)


class TestNonceReplayAndNtpDrift:
    """Empirical stress tests for NonceLedger replay protection and NTP windowing."""

    @pytest.mark.asyncio
    async def testConcurrentNonceReplayDefense(self, mockRedisClient: Any) -> None:
        """Simulates 20 concurrent requests attempting to consume the EXACT SAME nonce."""
        ledger = NonceLedger(mockRedisClient)
        serverTime = 2000000000
        reusedNonce = "nonce_concurrent_race_attack"

        async def attemptConsume():
            try:
                await ledger.validateAndRecordNonce(reusedNonce, timestamp=serverTime, serverTime=serverTime)
                return "SUCCESS"
            except NonceReplayException:
                return "REPLAY_BLOCKED"

        results = await asyncio.gather(*[attemptConsume() for _ in range(20)])
        assert results.count("SUCCESS") == 1
        assert results.count("REPLAY_BLOCKED") == 19

    def testNtpTimestampExtremeBoundaries(self, mockRedisClient: Any) -> None:
        """Tests strict NTP window bounds: [T - 5, T + 60]."""
        ledger = NonceLedger(mockRedisClient)
        serverTime = 5000

        assert ledger.verifyTimestampWindow(4995, serverTime=serverTime) is True
        assert ledger.verifyTimestampWindow(5060, serverTime=serverTime) is True

        with pytest.raises(TimestampExpiredException):
            ledger.verifyTimestampWindow(4994, serverTime=serverTime)
        with pytest.raises(FutureTimestampException):
            ledger.verifyTimestampWindow(5061, serverTime=serverTime)
        with pytest.raises(TimestampExpiredException):
            ledger.verifyTimestampWindow(-100, serverTime=serverTime)
        with pytest.raises(FutureTimestampException):
            ledger.verifyTimestampWindow(2147483647, serverTime=serverTime)


class TestCryptographicMandateIntegrity:
    """Empirical stress tests for Ed25519 signing, verification, and hash-chain binding."""

    def testSignatureFailsOnAnyBitFlip(self, agentKeyFixtures: Dict[str, Any]) -> None:
        """Asserts that altering any single bit/byte in payload or signature fails verification."""
        userKey = agentKeyFixtures["userCfo"]
        signer = Ed25519Signer(userKey["privateKeyHex"])
        publicKeyHex = signer.getPublicKeyHex()

        payload = {"amount": 100000, "currency": "INR", "mandateId": "mandate_1"}
        canonicalBytes, _ = canonicalizeAndHash(payload)
        sigHex = signer.signCanonicalBytes(canonicalBytes)

        assert Ed25519Verifier.verifySignature(publicKeyHex, canonicalBytes, sigHex) is True

        corruptSig = ("0" if sigHex[0] != "0" else "1") + sigHex[1:]
        assert Ed25519Verifier.verifySignature(publicKeyHex, canonicalBytes, corruptSig) is False

        with pytest.raises(SignatureVerificationFailedException):
            Ed25519Verifier.verifySignature(publicKeyHex, canonicalBytes, corruptSig, raiseOnFailure=True)

        assert Ed25519Verifier.verifySignature(publicKeyHex, canonicalBytes, sigHex[:-2]) is False
        with pytest.raises(SignatureVerificationFailedException):
            Ed25519Verifier.verifySignature(publicKeyHex, canonicalBytes, sigHex[:-2], raiseOnFailure=True)

        otherKey = agentKeyFixtures["merchantNode"]
        otherPub = extractPublicKeyFromDid(otherKey["did"])
        assert Ed25519Verifier.verifySignature(otherPub, canonicalBytes, sigHex) is False

    def testMandateHashChainTamperingInterception(self, agentKeyFixtures: Dict[str, Any]) -> None:
        """Tests that altering IntentMandate or CartMandate breaks ExecutionMandate hash chain."""
        userSigner = Ed25519Signer(agentKeyFixtures["userCfo"]["privateKeyHex"])
        buyerSigner = Ed25519Signer(agentKeyFixtures["buyerAgent"]["privateKeyHex"])
        merchantSigner = Ed25519Signer(agentKeyFixtures["merchantNode"]["privateKeyHex"])
        currentTime = 1755936000

        intentMandate = createSignedIntentMandate(
            mandateId="intent_chain_test", userSigner=userSigner,
            delegatedAgentDid=buyerSigner.getAgentDid(), maxBudgetPaise=1000000,
            upiCircleDelegationToken="upi_tok", singleTransactionLimitPaise=500000, timestamp=currentTime,
        )
        cartItem = CartItemSchema(
            skuId="SKU-001", quantity=1, unitPricePaise=300000, hsnCode="8471",
            gstRatePercent=18, lineTotalPaise=300000,
        )
        cartMandate = createSignedCartMandate(
            cartId="cart_chain_test", merchantSigner=merchantSigner,
            merchantGstin="29AABCU9603R1ZJ", merchantStateCode="29",
            buyerDeliveryPincode="560001", buyerDeliveryStateCode="29",
            items=[cartItem], taxableSubtotalPaise=300000,
            taxBreakdown=TaxBreakdownSchema(cgstPaise=27000, sgstPaise=27000, igstPaise=0, totalTaxPaise=54000),
            shippingPaise=0, discountPaise=0, totalPaise=354000,
            inventoryLockToken="lock_tok", inventoryLockExpiresAt=currentTime + 60, timestamp=currentTime,
        )
        execMandate = createSignedExecutionMandate(
            executionId="exec_chain_test", buyerAgentSigner=buyerSigner,
            intentMandate=intentMandate, cartMandate=cartMandate,
            settlementAmountPaise=354000, upiCircleToken="upi_tok", timestamp=currentTime,
        )

        assert verifyMandateHashChain(intentMandate, cartMandate, execMandate) is True

        tamperedIntent = intentMandate.model_copy(update={"maxBudgetPaise": 2000000})
        with pytest.raises(MandateHashChainMismatchException):
            verifyMandateHashChain(tamperedIntent, cartMandate, execMandate)

        tamperedCart = cartMandate.model_copy(update={"totalPaise": 999999})
        with pytest.raises(MandateHashChainMismatchException):
            verifyMandateHashChain(intentMandate, tamperedCart, execMandate)
