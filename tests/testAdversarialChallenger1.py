"""Adversarial Stress Test Suite — Challenger 1 (Cryptographic and Financial Invariants).

Empirically tests and challenges:
1. Zero Floating Point Drift & Arithmetic Enclave Precision
2. Budget Gate Invariants & Breach Interception
3. Nonce Ledger Replay Prevention & NTP Drift Windowing
4. Ed25519 Cryptographic Integrity & Hash Chain Binding
5. Two-Phase Commit (2PC) Settlement Saga Compensation
"""

import asyncio
from decimal import Decimal
from fractions import Fraction
import time
from typing import Any, Dict, List
import pytest

from razoragentMesh.packages.mandateEngine.arithmeticEnclave import (
    computeCartSettlementTotal,
    computeGstBreakdown,
    computeLineItemTotal,
    computeTcsWithholding,
    validateIntegerPaise,
)
from razoragentMesh.packages.mandateEngine.budgetGate import validateBudgetGate
from razoragentMesh.packages.mandateEngine.cartMandateSchema import (
    CartItemSchema,
    CartMandate,
    TaxBreakdownSchema,
)
from razoragentMesh.packages.mandateEngine.cryptoKeyUtils import (
    extractPublicKeyFromDid,
    formatDid,
    generateKeyPair,
)
from razoragentMesh.packages.mandateEngine.ed25519Signer import Ed25519Signer
from razoragentMesh.packages.mandateEngine.ed25519Verifier import Ed25519Verifier
from razoragentMesh.packages.mandateEngine.executionMandateSchema import ExecutionMandate
from razoragentMesh.packages.mandateEngine.gstrInvoiceEngine import (
    generateGstrInvoice,
    isPlaceOfSupplyIntraState,
)
from razoragentMesh.packages.mandateEngine.intentMandateSchema import IntentMandate
from razoragentMesh.packages.mandateEngine.jcsCanonicalizer import (
    canonicalizeAndHash,
    canonicalizeJson,
    computeSha256Digest,
)
from razoragentMesh.packages.mandateEngine.mandateFactory import (
    computeMandateHash,
    createSignedCartMandate,
    createSignedExecutionMandate,
    createSignedIntentMandate,
    verifyMandateHashChain,
)
from razoragentMesh.packages.mandateEngine.nonceGenerator import generateNonce
from razoragentMesh.packages.mandateEngine.nonceLedger import NonceLedger
from razoragentMesh.packages.mandateEngine.razorpayRouteClient import (
    RazorpayRouteClient,
    RouteTransferRequest,
)
from razoragentMesh.packages.mandateEngine.settlementExceptions import (
    ArithmeticDriftException,
    ArithmeticEnclaveMismatchException,
    BudgetExceededViolation,
    CategoryNotAuthorizedException,
    FutureTimestampException,
    MandateExpiredException,
    MandateHashChainMismatchException,
    NonceReplayException,
    SignatureVerificationFailedException,
    SingleTransactionLimitExceededException,
    SettlementCompensationTriggeredException,
    TimestampExpiredException,
)
from razoragentMesh.packages.mandateEngine.settlementOrchestrator import (
    SettlementOrchestrator,
)


class TestZeroFloatingPointDrift:
    """Empirical stress tests for floating-point rejection and integer arithmetic."""

    @pytest.mark.parametrize(
        "maliciousInput",
        [
            0.0,
            -0.0,
            1.5,
            1976.501,
            -1976.501,
            1e-5,
            1e10,
            float("inf"),
            float("-inf"),
            float("nan"),
            True,
            False,
            "100",
            "1976.50",
            Decimal("100.5"),
            Decimal("100"),
            Fraction(10, 2),
            None,
            [],
            {},
            [100],
            {"amount": 100},
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
        rates = [0, 5, 12, 18, 28]
        oddAmounts = [1, 2, 3, 7, 13, 99, 101, 103, 333, 999, 1976501, 10000000007]

        for amt in oddAmounts:
            for rate in rates:
                gstIntra = computeGstBreakdown(amt, rate, isIntraState=True)
                assert gstIntra["cgstPaise"] + gstIntra["sgstPaise"] == gstIntra["totalTaxPaise"]
                assert gstIntra["igstPaise"] == 0
                assert gstIntra["totalTaxPaise"] == (amt * rate) // 100
                assert gstIntra["cgstPaise"] == (amt * (rate // 2)) // 100
                assert gstIntra["sgstPaise"] == gstIntra["totalTaxPaise"] - gstIntra["cgstPaise"]

                gstInter = computeGstBreakdown(amt, rate, isIntraState=False)
                assert gstInter["cgstPaise"] == 0
                assert gstInter["sgstPaise"] == 0
                assert gstInter["igstPaise"] == gstInter["totalTaxPaise"]
                assert gstInter["totalTaxPaise"] == (amt * rate) // 100

    def testTcsWithholdingIntraAndInterState(self) -> None:
        """Asserts TCS withholding computation exactness (0.5% + 0.5% intra, 1.0% inter)."""
        tcsIntra = computeTcsWithholding(100000, isIntraState=True)
        assert tcsIntra["tcsCgstPaise"] == 500
        assert tcsIntra["tcsSgstPaise"] == 500
        assert tcsIntra["tcsIgstPaise"] == 0
        assert tcsIntra["totalTcsPaise"] == 1000

        tcsInter = computeTcsWithholding(100000, isIntraState=False)
        assert tcsInter["tcsCgstPaise"] == 0
        assert tcsInter["tcsSgstPaise"] == 0
        assert tcsInter["tcsIgstPaise"] == 1000
        assert tcsInter["totalTcsPaise"] == 1000

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


class TestBudgetGateBreachDefense:
    """Empirical stress tests for AP2 BudgetGate constraints."""

    @pytest.fixture
    def setupMandates(self, agentKeyFixtures: Dict[str, Any]):
        userKey = agentKeyFixtures["userCfo"]
        buyerKey = agentKeyFixtures["buyerAgent"]
        merchantKey = agentKeyFixtures["merchantNode"]

        userSigner = Ed25519Signer(userKey["privateKeyHex"])
        buyerSigner = Ed25519Signer(buyerKey["privateKeyHex"])
        merchantSigner = Ed25519Signer(merchantKey["privateKeyHex"])

        currentTime = 1755936000

        intentMandate = createSignedIntentMandate(
            mandateId="intent_gate_test",
            userSigner=userSigner,
            delegatedAgentDid=buyerSigner.getAgentDid(),
            maxBudgetPaise=1000000,
            upiCircleDelegationToken="upi_token_gate",
            singleTransactionLimitPaise=500000,
            authorizedCategories=["electronics", "office_supplies"],
            validUntilTimestamp=currentTime + 3600,
            timestamp=currentTime,
        )

        return {
            "userSigner": userSigner,
            "buyerSigner": buyerSigner,
            "merchantSigner": merchantSigner,
            "intentMandate": intentMandate,
            "currentTime": currentTime,
        }

    def _createCartAndExecution(
        self,
        merchantSigner: Ed25519Signer,
        buyerSigner: Ed25519Signer,
        intentMandate: IntentMandate,
        itemUnitPrice: int,
        itemQuantity: int,
        taxPercent: int,
        shipping: int,
        discount: int,
        claimedCartTotal: int,
        claimedSettlementAmt: int,
        currentTime: int,
    ) -> tuple[CartMandate, ExecutionMandate]:
        taxableSubtotal = itemUnitPrice * itemQuantity
        taxBreakdown = computeGstBreakdown(taxableSubtotal, taxPercent, isIntraState=True)

        cartItem = CartItemSchema(
            skuId="SKU-STRESS-01",
            quantity=itemQuantity,
            unitPricePaise=itemUnitPrice,
            hsnCode="8471",
            gstRatePercent=taxPercent,
            lineTotalPaise=taxableSubtotal,
        )
        tbSchema = TaxBreakdownSchema(
            cgstPaise=taxBreakdown["cgstPaise"],
            sgstPaise=taxBreakdown["sgstPaise"],
            igstPaise=taxBreakdown["igstPaise"],
            totalTaxPaise=taxBreakdown["totalTaxPaise"],
        )

        cartMandate = createSignedCartMandate(
            cartId="cart_gate_stress",
            merchantSigner=merchantSigner,
            merchantGstin="29AABCU9603R1ZM",
            merchantStateCode="29",
            buyerDeliveryPincode="560001",
            buyerDeliveryStateCode="29",
            items=[cartItem],
            taxableSubtotalPaise=taxableSubtotal,
            taxBreakdown=tbSchema,
            shippingPaise=shipping,
            discountPaise=discount,
            totalPaise=claimedCartTotal,
            inventoryLockToken="lock_gate_token",
            inventoryLockExpiresAt=currentTime + 60,
            timestamp=currentTime,
        )

        execMandate = createSignedExecutionMandate(
            executionId="exec_gate_stress",
            buyerAgentSigner=buyerSigner,
            intentMandate=intentMandate,
            cartMandate=cartMandate,
            settlementAmountPaise=claimedSettlementAmt,
            upiCircleToken="upi_token_gate",
            timestamp=currentTime,
        )
        return cartMandate, execMandate

    def testBudgetCapExactBoundaries(self, setupMandates: Dict[str, Any]) -> None:
        """Tests exact boundary conditions for max budget cap and single transaction limit."""
        ctx = setupMandates
        cart, execM = self._createCartAndExecution(
            merchantSigner=ctx["merchantSigner"],
            buyerSigner=ctx["buyerSigner"],
            intentMandate=ctx["intentMandate"],
            itemUnitPrice=500000,
            itemQuantity=1,
            taxPercent=0,
            shipping=0,
            discount=0,
            claimedCartTotal=500000,
            claimedSettlementAmt=500000,
            currentTime=ctx["currentTime"],
        )
        assert validateBudgetGate(ctx["intentMandate"], cart, execM, ctx["currentTime"]) is True

        cartOverSingle, execOverSingle = self._createCartAndExecution(
            merchantSigner=ctx["merchantSigner"],
            buyerSigner=ctx["buyerSigner"],
            intentMandate=ctx["intentMandate"],
            itemUnitPrice=500001,
            itemQuantity=1,
            taxPercent=0,
            shipping=0,
            discount=0,
            claimedCartTotal=500001,
            claimedSettlementAmt=500001,
            currentTime=ctx["currentTime"],
        )
        with pytest.raises(SingleTransactionLimitExceededException):
            validateBudgetGate(ctx["intentMandate"], cartOverSingle, execOverSingle, ctx["currentTime"])

    def testArithmeticDriftMismatchedCartAndExecutionTotals(self, setupMandates: Dict[str, Any]) -> None:
        """Tests detection of arithmetic tampering in cart or execution amounts."""
        ctx = setupMandates
        cartTampered, execTampered = self._createCartAndExecution(
            merchantSigner=ctx["merchantSigner"],
            buyerSigner=ctx["buyerSigner"],
            intentMandate=ctx["intentMandate"],
            itemUnitPrice=100000,
            itemQuantity=1,
            taxPercent=0,
            shipping=0,
            discount=0,
            claimedCartTotal=90000,
            claimedSettlementAmt=90000,
            currentTime=ctx["currentTime"],
        )
        with pytest.raises(ArithmeticEnclaveMismatchException):
            validateBudgetGate(ctx["intentMandate"], cartTampered, execTampered, ctx["currentTime"])

    def testMandateExpirationBoundary(self, setupMandates: Dict[str, Any]) -> None:
        """Tests exact expiration boundary."""
        ctx = setupMandates
        validUntil = ctx["intentMandate"].validUntilTimestamp
        cart, execM = self._createCartAndExecution(
            merchantSigner=ctx["merchantSigner"],
            buyerSigner=ctx["buyerSigner"],
            intentMandate=ctx["intentMandate"],
            itemUnitPrice=100000,
            itemQuantity=1,
            taxPercent=0,
            shipping=0,
            discount=0,
            claimedCartTotal=100000,
            claimedSettlementAmt=100000,
            currentTime=validUntil,
        )
        assert validateBudgetGate(ctx["intentMandate"], cart, execM, currentTimestamp=validUntil) is True
        with pytest.raises(MandateExpiredException):
            validateBudgetGate(ctx["intentMandate"], cart, execM, currentTimestamp=validUntil + 1)

    def testUnauthorizedCategoryRejection(self, setupMandates: Dict[str, Any]) -> None:
        """Tests rejection when unauthorized categories are present."""
        ctx = setupMandates
        cart, execM = self._createCartAndExecution(
            merchantSigner=ctx["merchantSigner"],
            buyerSigner=ctx["buyerSigner"],
            intentMandate=ctx["intentMandate"],
            itemUnitPrice=100000,
            itemQuantity=1,
            taxPercent=0,
            shipping=0,
            discount=0,
            claimedCartTotal=100000,
            claimedSettlementAmt=100000,
            currentTime=ctx["currentTime"],
        )
        with pytest.raises(CategoryNotAuthorizedException):
            validateBudgetGate(
                ctx["intentMandate"],
                cart,
                execM,
                ctx["currentTime"],
                skuCategories=["electronics", "luxury_jewelry"],
            )

    @pytest.mark.asyncio
    async def testSettlementSagaAbortsOnBudgetBreachWithZeroDebited(
        self,
        setupMandates: Dict[str, Any],
        mockRedisClient: Any,
    ) -> None:
        """Asserts that settlement saga blocks on budget breach, resulting in 0 captures and 0 transfers."""
        ctx = setupMandates
        cartOverBudget, execOverBudget = self._createCartAndExecution(
            merchantSigner=ctx["merchantSigner"],
            buyerSigner=ctx["buyerSigner"],
            intentMandate=ctx["intentMandate"],
            itemUnitPrice=1500000,
            itemQuantity=1,
            taxPercent=0,
            shipping=0,
            discount=0,
            claimedCartTotal=1500000,
            claimedSettlementAmt=1500000,
            currentTime=ctx["currentTime"],
        )

        routeClient = RazorpayRouteClient()
        nonceLedger = NonceLedger(mockRedisClient)
        orchestrator = SettlementOrchestrator(
            routeClient=routeClient,
            nonceLedger=nonceLedger,
        )

        with pytest.raises(BudgetExceededViolation):
            await orchestrator.executeSettlementSaga(
                intentMandate=ctx["intentMandate"],
                cartMandate=cartOverBudget,
                executionMandate=execOverBudget,
                merchantAccount="acc_merchant_nexus_01",
                paymentId="pay_budget_breach_intercept",
                serverTime=ctx["currentTime"],
            )

        assert len(routeClient._capturedPayments) == 0
        assert len(routeClient._transfers) == 0


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
            mandateId="intent_chain_test",
            userSigner=userSigner,
            delegatedAgentDid=buyerSigner.getAgentDid(),
            maxBudgetPaise=1000000,
            upiCircleDelegationToken="upi_tok",
            singleTransactionLimitPaise=500000,
            timestamp=currentTime,
        )

        cartItem = CartItemSchema(
            skuId="SKU-001",
            quantity=1,
            unitPricePaise=300000,
            hsnCode="8471",
            gstRatePercent=18,
            lineTotalPaise=300000,
        )
        tb = TaxBreakdownSchema(cgstPaise=27000, sgstPaise=27000, igstPaise=0, totalTaxPaise=54000)

        cartMandate = createSignedCartMandate(
            cartId="cart_chain_test",
            merchantSigner=merchantSigner,
            merchantGstin="29AABCU9603R1ZM",
            merchantStateCode="29",
            buyerDeliveryPincode="560001",
            buyerDeliveryStateCode="29",
            items=[cartItem],
            taxableSubtotalPaise=300000,
            taxBreakdown=tb,
            shippingPaise=0,
            discountPaise=0,
            totalPaise=354000,
            inventoryLockToken="lock_tok",
            inventoryLockExpiresAt=currentTime + 60,
            timestamp=currentTime,
        )

        execMandate = createSignedExecutionMandate(
            executionId="exec_chain_test",
            buyerAgentSigner=buyerSigner,
            intentMandate=intentMandate,
            cartMandate=cartMandate,
            settlementAmountPaise=354000,
            upiCircleToken="upi_tok",
            timestamp=currentTime,
        )

        assert verifyMandateHashChain(intentMandate, cartMandate, execMandate) is True

        tamperedIntent = intentMandate.model_copy(update={"maxBudgetPaise": 2000000})
        with pytest.raises(MandateHashChainMismatchException):
            verifyMandateHashChain(tamperedIntent, cartMandate, execMandate)

        tamperedCart = cartMandate.model_copy(update={"totalPaise": 999999})
        with pytest.raises(MandateHashChainMismatchException):
            verifyMandateHashChain(intentMandate, tamperedCart, execMandate)


class TestTwoPhaseCommitSettlementRollback:
    """Empirical stress tests for 2PC Settlement Saga compensation and rollback."""

    @pytest.mark.asyncio
    async def testRollbackOnMerchantTransferFailure(
        self,
        agentKeyFixtures: Dict[str, Any],
        mockRedisClient: Any,
    ) -> None:
        """Tests saga behavior when 1st transfer (merchant) fails."""
        userSigner = Ed25519Signer(agentKeyFixtures["userCfo"]["privateKeyHex"])
        buyerSigner = Ed25519Signer(agentKeyFixtures["buyerAgent"]["privateKeyHex"])
        merchantSigner = Ed25519Signer(agentKeyFixtures["merchantNode"]["privateKeyHex"])

        currentTime = 1755936000

        intentMandate = createSignedIntentMandate(
            mandateId="intent_2pc_merchant_fail",
            userSigner=userSigner,
            delegatedAgentDid=buyerSigner.getAgentDid(),
            maxBudgetPaise=1000000,
            upiCircleDelegationToken="upi_tok_2pc",
            singleTransactionLimitPaise=1000000,
            timestamp=currentTime,
        )

        cartItem = CartItemSchema(
            skuId="SKU-001",
            quantity=1,
            unitPricePaise=420000,
            hsnCode="8504",
            gstRatePercent=0,
            lineTotalPaise=420000,
        )
        tb = TaxBreakdownSchema(cgstPaise=0, sgstPaise=0, igstPaise=0, totalTaxPaise=0)

        cartMandate = createSignedCartMandate(
            cartId="cart_2pc_merchant_fail",
            merchantSigner=merchantSigner,
            merchantGstin="29AABCU9603R1ZM",
            merchantStateCode="29",
            buyerDeliveryPincode="560001",
            buyerDeliveryStateCode="29",
            items=[cartItem],
            taxableSubtotalPaise=420000,
            taxBreakdown=tb,
            shippingPaise=0,
            discountPaise=0,
            totalPaise=420000,
            inventoryLockToken="lock_2pc_m_fail",
            inventoryLockExpiresAt=currentTime + 60,
            timestamp=currentTime,
        )

        execMandate = createSignedExecutionMandate(
            executionId="exec_2pc_merchant_fail",
            buyerAgentSigner=buyerSigner,
            intentMandate=intentMandate,
            cartMandate=cartMandate,
            settlementAmountPaise=420000,
            upiCircleToken="upi_tok_2pc",
            timestamp=currentTime,
        )

        routeClient = RazorpayRouteClient()
        routeClient.simulatedFailureAccount = "acc_merchant_fail_01"
        nonceLedger = NonceLedger(mockRedisClient)

        orchestrator = SettlementOrchestrator(
            routeClient=routeClient,
            nonceLedger=nonceLedger,
        )

        with pytest.raises(SettlementCompensationTriggeredException) as excInfo:
            await orchestrator.executeSettlementSaga(
                intentMandate=intentMandate,
                cartMandate=cartMandate,
                executionMandate=execMandate,
                merchantAccount="acc_merchant_fail_01",
                paymentId="pay_2pc_merchant_fail",
                serverTime=currentTime,
            )

        assert "triggered rollback of 0 transfers" in str(excInfo.value)
        assert len(routeClient._transfers) == 0
        assert len(routeClient._reversals) == 0

    @pytest.mark.asyncio
    async def testRollbackOnProtocolFeeFailureCompensatesMerchantTransfer(
        self,
        agentKeyFixtures: Dict[str, Any],
        mockRedisClient: Any,
    ) -> None:
        """Tests saga behavior when 2nd transfer (protocol fee) fails, ensuring 1st transfer is reversed."""
        userSigner = Ed25519Signer(agentKeyFixtures["userCfo"]["privateKeyHex"])
        buyerSigner = Ed25519Signer(agentKeyFixtures["buyerAgent"]["privateKeyHex"])
        merchantSigner = Ed25519Signer(agentKeyFixtures["merchantNode"]["privateKeyHex"])

        currentTime = 1755936000

        intentMandate = createSignedIntentMandate(
            mandateId="intent_2pc_proto_fail",
            userSigner=userSigner,
            delegatedAgentDid=buyerSigner.getAgentDid(),
            maxBudgetPaise=1000000,
            upiCircleDelegationToken="upi_tok_2pc",
            singleTransactionLimitPaise=1000000,
            timestamp=currentTime,
        )

        cartItem = CartItemSchema(
            skuId="SKU-001",
            quantity=1,
            unitPricePaise=420000,
            hsnCode="8504",
            gstRatePercent=0,
            lineTotalPaise=420000,
        )
        tb = TaxBreakdownSchema(cgstPaise=0, sgstPaise=0, igstPaise=0, totalTaxPaise=0)

        cartMandate = createSignedCartMandate(
            cartId="cart_2pc_proto_fail",
            merchantSigner=merchantSigner,
            merchantGstin="29AABCU9603R1ZM",
            merchantStateCode="29",
            buyerDeliveryPincode="560001",
            buyerDeliveryStateCode="29",
            items=[cartItem],
            taxableSubtotalPaise=420000,
            taxBreakdown=tb,
            shippingPaise=0,
            discountPaise=0,
            totalPaise=420000,
            inventoryLockToken="lock_2pc_proto_fail",
            inventoryLockExpiresAt=currentTime + 60,
            timestamp=currentTime,
        )

        execMandate = createSignedExecutionMandate(
            executionId="exec_2pc_proto_fail",
            buyerAgentSigner=buyerSigner,
            intentMandate=intentMandate,
            cartMandate=cartMandate,
            settlementAmountPaise=420000,
            upiCircleToken="upi_tok_2pc",
            timestamp=currentTime,
        )

        routeClient = RazorpayRouteClient()
        routeClient.simulatedFailureAccount = "acc_protocol_fee"
        nonceLedger = NonceLedger(mockRedisClient)

        orchestrator = SettlementOrchestrator(
            routeClient=routeClient,
            nonceLedger=nonceLedger,
            protocolFeeAccount="acc_protocol_fee",
            protocolFeePaise=50,
        )

        with pytest.raises(SettlementCompensationTriggeredException) as excInfo:
            await orchestrator.executeSettlementSaga(
                intentMandate=intentMandate,
                cartMandate=cartMandate,
                executionMandate=execMandate,
                merchantAccount="acc_merchant_valid_01",
                paymentId="pay_2pc_proto_fail",
                serverTime=currentTime,
            )

        assert "triggered rollback of 1 transfers" in str(excInfo.value)
        assert len(routeClient._transfers) == 1
        assert len(routeClient._reversals) == 1
        reversal = list(routeClient._reversals.values())[0]
        assert reversal.amount == (420000 - 50)

    @pytest.mark.asyncio
    async def testRollbackOnLogisticsFailureCompensatesAllPriorTransfersInLifoOrder(
        self,
        agentKeyFixtures: Dict[str, Any],
        mockRedisClient: Any,
    ) -> None:
        """Tests saga behavior when 3rd transfer (logistics) fails, ensuring merchant and protocol fee transfers are reversed."""
        userSigner = Ed25519Signer(agentKeyFixtures["userCfo"]["privateKeyHex"])
        buyerSigner = Ed25519Signer(agentKeyFixtures["buyerAgent"]["privateKeyHex"])
        merchantSigner = Ed25519Signer(agentKeyFixtures["merchantNode"]["privateKeyHex"])

        currentTime = 1755936000

        intentMandate = createSignedIntentMandate(
            mandateId="intent_2pc_logistics_fail",
            userSigner=userSigner,
            delegatedAgentDid=buyerSigner.getAgentDid(),
            maxBudgetPaise=1000000,
            upiCircleDelegationToken="upi_tok_2pc",
            singleTransactionLimitPaise=1000000,
            timestamp=currentTime,
        )

        cartItem = CartItemSchema(
            skuId="SKU-001",
            quantity=1,
            unitPricePaise=380000,
            hsnCode="8504",
            gstRatePercent=0,
            lineTotalPaise=380000,
        )
        tb = TaxBreakdownSchema(cgstPaise=0, sgstPaise=0, igstPaise=0, totalTaxPaise=0)

        cartMandate = createSignedCartMandate(
            cartId="cart_2pc_logistics_fail",
            merchantSigner=merchantSigner,
            merchantGstin="29AABCU9603R1ZM",
            merchantStateCode="29",
            buyerDeliveryPincode="560001",
            buyerDeliveryStateCode="29",
            items=[cartItem],
            taxableSubtotalPaise=380000,
            taxBreakdown=tb,
            shippingPaise=38000,
            discountPaise=0,
            totalPaise=418000,
            inventoryLockToken="lock_2pc_logistics_fail",
            inventoryLockExpiresAt=currentTime + 60,
            timestamp=currentTime,
        )

        execMandate = createSignedExecutionMandate(
            executionId="exec_2pc_logistics_fail",
            buyerAgentSigner=buyerSigner,
            intentMandate=intentMandate,
            cartMandate=cartMandate,
            settlementAmountPaise=418000,
            upiCircleToken="upi_tok_2pc",
            timestamp=currentTime,
        )

        routeClient = RazorpayRouteClient()
        routeClient.simulatedFailureAccount = "acc_logistics_delhivery"
        nonceLedger = NonceLedger(mockRedisClient)

        orchestrator = SettlementOrchestrator(
            routeClient=routeClient,
            nonceLedger=nonceLedger,
            protocolFeeAccount="acc_protocol_fee",
            protocolFeePaise=2000,
            logisticsAccount="acc_logistics_delhivery",
        )

        with pytest.raises(SettlementCompensationTriggeredException) as excInfo:
            await orchestrator.executeSettlementSaga(
                intentMandate=intentMandate,
                cartMandate=cartMandate,
                executionMandate=execMandate,
                merchantAccount="acc_merchant_nexus_01",
                paymentId="pay_2pc_logistics_fail",
                serverTime=currentTime,
            )

        assert "triggered rollback of 2 transfers" in str(excInfo.value)
        assert len(routeClient._transfers) == 2
        assert len(routeClient._reversals) == 2
        reversedAmounts = [r.amount for r in routeClient._reversals.values()]
        assert 378000 in reversedAmounts
        assert 2000 in reversedAmounts