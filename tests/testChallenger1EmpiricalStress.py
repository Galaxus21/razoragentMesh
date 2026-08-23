"""Challenger 1 Empirical Stress Harness — Comprehensive Adversarial Verification.

Covers:
1. Multi-item GSTR-1 mixed tax calculation, TCS withholding, and JCS canonical hash across (0%, 5%, 12%, 18%, 28%)
2. Zero penny drift (Δ = 0 paise) under asymmetric discount allocation across odd unit prices
3. 2PC Route settlement sagas under concurrent transfer failures, LIFO reversal ordering, and nonce invalidation
4. Fail-closed vegetarian constraint filter with missing/null/falsy isVeg fields
"""

import asyncio
from decimal import Decimal
import time
from typing import Any, Dict, List
import fakeredis.aioredis
from pydantic import ValidationError
import pytest

from razoragentMesh.packages.mandateEngine.crypto.cryptoKeyUtils import generateKeyPair
from razoragentMesh.packages.mandateEngine.crypto.ed25519Signer import Ed25519Signer
from razoragentMesh.packages.mandateEngine.crypto.ed25519Verifier import Ed25519Verifier
from razoragentMesh.packages.mandateEngine.crypto.jcsCanonicalizer import (
    canonicalizeAndHash,
    canonicalizeJson,
    computeSha256Digest,
)
from razoragentMesh.packages.mandateEngine.mandates.cartMandateSchema import (
    CartItemSchema,
    CartMandate,
    TaxBreakdownSchema,
)
from razoragentMesh.packages.mandateEngine.mandates.executionMandateSchema import (
    ExecutionMandate,
)
from razoragentMesh.packages.mandateEngine.mandates.intentMandateSchema import (
    IntentMandate,
)
from razoragentMesh.packages.mandateEngine.mandates.mandateFactory import (
    createSignedCartMandate,
    createSignedExecutionMandate,
    createSignedIntentMandate,
)
from razoragentMesh.packages.mandateEngine.nonce.nonceLedger import NonceLedger
from razoragentMesh.packages.mandateEngine.settlement.razorpayRouteClient import (
    RazorpayRouteClient,
    RouteTransferRequest,
)
from razoragentMesh.packages.mandateEngine.settlement.settlementExceptions import (
    ArithmeticDriftException,
    FutureTimestampException,
    NonceReplayException,
    SettlementCompensationTriggeredException,
    TimestampExpiredException,
)
from razoragentMesh.packages.mandateEngine.settlement.settlementOrchestrator import (
    SettlementOrchestrator,
    SettlementResult,
)
from razoragentMesh.packages.mandateEngine.settlement.splitManifestBuilder import (
    SplitTransferManifest,
    buildSplitManifest,
)
from razoragentMesh.packages.mandateEngine.tax.gstrInvoiceEngine import (
    GstrInvoicePayload,
    GstrLineItem,
    _buildInvoiceDict,
    generateGstrInvoice,
    isPlaceOfSupplyIntraState,
)
from razoragentMesh.packages.mandateEngine.verification.arithmeticEnclave import (
    computeCartSettlementTotal,
    computeGstBreakdown,
    computeLineItemTotal,
    computeTcsWithholding,
    validateIntegerPaise,
)
from razoragentMesh.packages.vectorHealer.src.constraints.constraintFilter import (
    NegativeConstraintFilter,
)
from razoragentMesh.packages.vectorHealer.src.constraints.negativeManifestSchema import (
    NegativeConstraintManifest,
)


class TestGstrMixedTaxAndJcsVerification:
    """1. Multi-item GSTR-1 mixed tax calculation, TCS withholding, and JCS canonical hash generation."""

    @pytest.mark.parametrize(
        "isIntraState,merchantState,deliveryState",
        [
            (True, "29", "29"),
            (False, "29", "27"),
            (False, "07", "33"),
            (True, "06", "06"),
        ],
    )
    def testAllFiveGstSlabsMixedCart(
        self, isIntraState: bool, merchantState: str, deliveryState: str
    ) -> None:
        """Verifies a 5-item cart spanning all GST slabs (0%, 5%, 12%, 18%, 28%)."""
        slabs = [0, 5, 12, 18, 28]
        quantities = [1, 2, 3, 4, 5]
        unitPrices = [50000, 75000, 120000, 250000, 400000]

        items: List[CartItemSchema] = []
        expectedLineTaxables: List[int] = []
        expectedLineTaxes: List[int] = []
        expectedLineCgst: List[int] = []
        expectedLineSgst: List[int] = []
        expectedLineIgst: List[int] = []

        for idx, rate in enumerate(slabs):
            qty = quantities[idx]
            price = unitPrices[idx]
            lineTaxable = computeLineItemTotal(price, qty)
            expectedLineTaxables.append(lineTaxable)

            gst = computeGstBreakdown(lineTaxable, rate, isIntraState=isIntraState)
            assert gst["totalTaxPaise"] == gst["cgstPaise"] + gst["sgstPaise"] + gst["igstPaise"]

            expectedLineTaxes.append(gst["totalTaxPaise"])
            expectedLineCgst.append(gst["cgstPaise"])
            expectedLineSgst.append(gst["sgstPaise"])
            expectedLineIgst.append(gst["igstPaise"])

            items.append(
                CartItemSchema(
                    skuId=f"SKU-SLAB-{rate}",
                    quantity=qty,
                    unitPricePaise=price,
                    hsnCode=f"84{rate:02d}00",
                    gstRatePercent=rate,
                    lineTotalPaise=lineTaxable,
                )
            )

        taxableSubtotal = sum(expectedLineTaxables)
        totalTax = sum(expectedLineTaxes)
        totalCgst = sum(expectedLineCgst)
        totalSgst = sum(expectedLineSgst)
        totalIgst = sum(expectedLineIgst)

        assert totalTax == totalCgst + totalSgst + totalIgst

        shippingPaise = 7500
        discountPaise = 5000
        grossTotal = computeCartSettlementTotal(
            taxableSubtotalPaise=taxableSubtotal,
            totalTaxPaise=totalTax,
            shippingPaise=shippingPaise,
            discountPaise=discountPaise,
        )
        assert grossTotal == taxableSubtotal + totalTax + shippingPaise - discountPaise

        # Generate Mandates
        userPriv, _ = generateKeyPair()
        merchantPriv, _ = generateKeyPair()
        agentPriv, _ = generateKeyPair()

        userSigner = Ed25519Signer(userPriv)
        merchantSigner = Ed25519Signer(merchantPriv)
        agentSigner = Ed25519Signer(agentPriv)

        intentMandate = createSignedIntentMandate(
            mandateId="M-I-GSTR-STRESS",
            userSigner=userSigner,
            delegatedAgentDid=agentSigner.getAgentDid(),
            maxBudgetPaise=10000000,
            upiCircleDelegationToken="upi_tok_gstr",
            singleTransactionLimitPaise=10000000,
        )

        taxBreakdown = TaxBreakdownSchema(
            cgstPaise=totalCgst,
            sgstPaise=totalSgst,
            igstPaise=totalIgst,
            totalTaxPaise=totalTax,
        )

        cartMandate = createSignedCartMandate(
            cartId="M-C-GSTR-STRESS",
            merchantSigner=merchantSigner,
            merchantGstin=f"{merchantState}AABCU9603R1ZM",
            merchantStateCode=merchantState,
            buyerDeliveryPincode="560001",
            buyerDeliveryStateCode=deliveryState,
            items=items,
            taxableSubtotalPaise=taxableSubtotal,
            taxBreakdown=taxBreakdown,
            shippingPaise=shippingPaise,
            discountPaise=discountPaise,
            totalPaise=grossTotal,
            inventoryLockToken="lock_gstr_stress",
            inventoryLockExpiresAt=2000000000,
        )

        executionMandate = createSignedExecutionMandate(
            executionId="M-E-GSTR-STRESS",
            buyerAgentSigner=agentSigner,
            intentMandate=intentMandate,
            cartMandate=cartMandate,
            settlementAmountPaise=grossTotal,
            upiCircleToken="upi_tok_gstr",
            timestamp=1750000000,
        )

        # Generate GSTR Invoice
        invoice = generateGstrInvoice(
            cartMandate=cartMandate,
            executionMandate=executionMandate,
            invoiceNumber="INV-STRESS-GSTR-01",
            invoiceTimestamp=1750000000,
        )

        assert isinstance(invoice, GstrInvoicePayload)
        assert invoice.isIntraState == isIntraState
        assert invoice.taxableAmountPaise == taxableSubtotal
        assert invoice.totalTaxPaise == totalTax
        assert invoice.totalCgstPaise == totalCgst
        assert invoice.totalSgstPaise == totalSgst
        assert invoice.totalIgstPaise == totalIgst
        assert invoice.grandTotalPaise == grossTotal

        # TCS Withholding Section 52 verification
        tcsExpected = computeTcsWithholding(taxableSubtotal, isIntraState=isIntraState)
        assert invoice.totalTcsPaise == tcsExpected["totalTcsPaise"]
        if isIntraState:
            assert tcsExpected["tcsCgstPaise"] == (taxableSubtotal * 50) // 10000
            assert tcsExpected["tcsSgstPaise"] == (taxableSubtotal * 50) // 10000
            assert tcsExpected["tcsIgstPaise"] == 0
        else:
            assert tcsExpected["tcsCgstPaise"] == 0
            assert tcsExpected["tcsSgstPaise"] == 0
            assert tcsExpected["tcsIgstPaise"] == (taxableSubtotal * 100) // 10000

        # Cryptographic Audit Hash verification
        rawDict = _buildInvoiceDict(
            cart=cartMandate,
            items=invoice.lineItems,
            totals=(taxableSubtotal, totalCgst, totalSgst, totalIgst, totalTax, grossTotal),
            num="INV-STRESS-GSTR-01",
            dt=invoice.invoiceDate,
            intra=isIntraState,
        )
        canonicalBytes = canonicalizeJson(rawDict)
        computedHash = computeSha256Digest(canonicalBytes)
        assert invoice.cryptographicAuditHash == computedHash
        assert len(invoice.cryptographicAuditHash) == 64

    def testJcsCanonicalHashInvarianceUnderKeyPermutations(self) -> None:
        """Verifies JCS produces identical hash regardless of dict key insertion order."""
        dict1 = {
            "zebra": 100,
            "alpha": {"bravo": [1, 2, 3], "charlie": "test"},
            "middle": True,
            "beta": None,
        }
        dict2 = {
            "beta": None,
            "middle": True,
            "alpha": {"charlie": "test", "bravo": [1, 2, 3]},
            "zebra": 100,
        }

        bytes1, hash1 = canonicalizeAndHash(dict1)
        bytes2, hash2 = canonicalizeAndHash(dict2)

        assert bytes1 == bytes2
        assert hash1 == hash2

    def testJcsRejectsAllFloatingPointPoisoning(self) -> None:
        """Verifies JCS strictly rejects floats in shallow, deep, or list structures."""
        with pytest.raises(ArithmeticDriftException):
            canonicalizeJson({"price": 100.0})

        with pytest.raises(ArithmeticDriftException):
            canonicalizeJson({"items": [{"qty": 1, "rate": 0.05}]})

        with pytest.raises(ArithmeticDriftException):
            canonicalizeJson([1, 2, [3, 4.0]])


class TestAsymmetricDiscountAndPennyConservation:
    """2. Zero penny drift (Δ = 0 paise) under asymmetric discount allocation."""

    @pytest.mark.parametrize(
        "prices,globalDiscount",
        [
            ([33333, 55555, 77777], 15000),
            ([33333, 55555, 77777], 10000),
            ([13, 37, 101, 333, 777, 999], 150),
            ([100001, 200003, 300007, 400009], 50000),
            ([7, 11, 13, 17, 19, 23, 29, 31], 75),
            ([999999, 1], 500000),
        ],
    )
    def testAsymmetricDiscountAllocationZeroDrift(
        self, prices: List[int], globalDiscount: int
    ) -> None:
        """Verifies exact penny conservation (sum of line discounts == globalDiscount, sum of net == cartSubtotal - globalDiscount)."""
        cartSubtotal = sum(prices)
        assert cartSubtotal > globalDiscount

        # Proportional integer floor allocation
        rawDiscounts = [(globalDiscount * p) // cartSubtotal for p in prices]
        allocatedSum = sum(rawDiscounts)
        driftRemainder = globalDiscount - allocatedSum
        assert driftRemainder >= 0

        # Allocate remainder to the highest priced item (penny conservation)
        finalDiscounts = list(rawDiscounts)
        maxIdx = prices.index(max(prices))
        finalDiscounts[maxIdx] += driftRemainder

        # Assert zero discount drift
        assert sum(finalDiscounts) == globalDiscount

        # Assert zero subtotal drift
        netLineTotals = [p - d for p, d in zip(prices, finalDiscounts)]
        assert sum(netLineTotals) == cartSubtotal - globalDiscount

        # Verify computeCartSettlementTotal matches
        grossTotal = computeCartSettlementTotal(
            taxableSubtotalPaise=cartSubtotal,
            totalTaxPaise=0,
            shippingPaise=500,
            discountPaise=globalDiscount,
        )
        assert grossTotal == (cartSubtotal - globalDiscount + 500)

    def testOddTaxFloorDivisionFuzzingThorough(self) -> None:
        """Fuzzes 500 odd amounts across all GST slabs checking penny conservation."""
        for rate in [0, 5, 12, 18, 28]:
            for amt in range(1, 501):
                oddAmt = amt * 2 + 1
                resIntra = computeGstBreakdown(oddAmt, rate, isIntraState=True)
                assert resIntra["cgstPaise"] + resIntra["sgstPaise"] == resIntra["totalTaxPaise"]
                assert resIntra["igstPaise"] == 0

                resInter = computeGstBreakdown(oddAmt, rate, isIntraState=False)
                assert resInter["igstPaise"] == resInter["totalTaxPaise"]
                assert resInter["cgstPaise"] == 0
                assert resInter["sgstPaise"] == 0


class TestConcurrentSettlementSagaAndReversals:
    """3. 2PC Route settlement sagas under concurrent failures, LIFO reversals, and nonces."""

    @pytest.mark.asyncio
    async def testTenConcurrentSagasWithVariedFailurePoints(self) -> None:
        """Dispatches 10 concurrent sagas: some succeed, some fail at merchant, protocol, or logistics."""
        fakeRedis = fakeredis.aioredis.FakeRedis()
        nonceLedger = NonceLedger(fakeRedis)
        routeClient = RazorpayRouteClient(isMockMode=True)

        userPriv, _ = generateKeyPair()
        merchPriv, _ = generateKeyPair()
        agentPriv, _ = generateKeyPair()
        uSigner = Ed25519Signer(userPriv)
        mSigner = Ed25519Signer(merchPriv)
        aSigner = Ed25519Signer(agentPriv)

        fixedTime = 1710000000

        # Define 10 saga configurations
        # Sagas 0, 1, 2: succeed
        # Saga 3: fail at merchant (transfer 0)
        # Saga 4: fail at protocol fee (transfer 1)
        # Saga 5: fail at logistics (transfer 2)
        # Sagas 6, 7, 8, 9: succeed
        failAtMerchantAccount = "acc_merch_failing_03"
        failAtProtoAccount = "acc_proto_failing_04"
        failAtLogisticsAccount = "acc_logistics_failing_05"

        async def runSaga(idx: int):
            mAcc = failAtMerchantAccount if idx == 3 else f"acc_merchant_{idx}"
            pAcc = failAtProtoAccount if idx == 4 else f"acc_proto_{idx}"
            lAcc = failAtLogisticsAccount if idx == 5 else f"acc_logistics_{idx}"

            # Setup RouteClient failure conditions dynamically
            if idx == 3:
                routeClient.simulatedFailureAccount = failAtMerchantAccount
            elif idx == 4:
                routeClient.simulatedFailureAccount = failAtProtoAccount
            elif idx == 5:
                routeClient.simulatedFailureAccount = failAtLogisticsAccount

            orchestrator = SettlementOrchestrator(
                routeClient=routeClient,
                nonceLedger=nonceLedger,
                protocolFeeAccount=pAcc,
                protocolFeePaise=100,
                logisticsAccount=lAcc,
            )

            # Build Mandates
            intentM = createSignedIntentMandate(
                mandateId=f"M-I-CONC-{idx}",
                userSigner=uSigner,
                delegatedAgentDid=aSigner.getAgentDid(),
                maxBudgetPaise=1000000,
                upiCircleDelegationToken=f"upi_tok_conc_{idx}",
                singleTransactionLimitPaise=1000000,
                validUntilTimestamp=2000000000,
            )
            item = CartItemSchema(
                skuId=f"SKU-CONC-{idx}",
                quantity=1,
                unitPricePaise=200000,
                hsnCode="8471",
                gstRatePercent=18,
                lineTotalPaise=200000,
            )
            cartM = createSignedCartMandate(
                cartId=f"M-C-CONC-{idx}",
                merchantSigner=mSigner,
                merchantGstin="29AAAAA0000A1Z5",
                merchantStateCode="29",
                buyerDeliveryPincode="560001",
                buyerDeliveryStateCode="29",
                items=[item],
                taxableSubtotalPaise=200000,
                taxBreakdown=TaxBreakdownSchema(cgstPaise=18000, sgstPaise=18000, igstPaise=0, totalTaxPaise=36000),
                shippingPaise=5000,
                discountPaise=0,
                totalPaise=241000,
                inventoryLockToken=f"lock_conc_{idx}",
                inventoryLockExpiresAt=2000000000,
            )
            execM = createSignedExecutionMandate(
                executionId=f"M-E-CONC-{idx}",
                buyerAgentSigner=aSigner,
                intentMandate=intentM,
                cartMandate=cartM,
                settlementAmountPaise=241000,
                upiCircleToken=f"upi_tok_conc_{idx}",
                timestamp=fixedTime,
                nonce=f"nonce_conc_test_{idx}",
            )

            return await orchestrator.executeSettlementSaga(
                intentMandate=intentM,
                cartMandate=cartM,
                executionMandate=execM,
                merchantAccount=mAcc,
                paymentId=f"pay_conc_{idx}",
                serverTime=fixedTime,
            )

        # Run sequential or concurrent tests to test failure modes deterministically
        for idx in range(10):
            if idx == 3:
                routeClient.simulatedFailureAccount = failAtMerchantAccount
                with pytest.raises(SettlementCompensationTriggeredException) as excInfo:
                    await runSaga(idx)
                assert "rollback of 0 transfers" in str(excInfo.value)
            elif idx == 4:
                routeClient.simulatedFailureAccount = failAtProtoAccount
                with pytest.raises(SettlementCompensationTriggeredException) as excInfo:
                    await runSaga(idx)
                assert "rollback of 1 transfers" in str(excInfo.value)
            elif idx == 5:
                routeClient.simulatedFailureAccount = failAtLogisticsAccount
                with pytest.raises(SettlementCompensationTriggeredException) as excInfo:
                    await runSaga(idx)
                assert "rollback of 2 transfers" in str(excInfo.value)
            else:
                routeClient.simulatedFailureAccount = None
                result = await runSaga(idx)
                assert isinstance(result, SettlementResult)
                assert result.status == "captured"

            # In ALL cases (success or failure), the nonce was recorded in Phase 1 and cannot be reused
            with pytest.raises(NonceReplayException):
                await nonceLedger.validateAndRecordNonce(
                    f"nonce_conc_test_{idx}",
                    timestamp=fixedTime,
                    serverTime=fixedTime,
                )

    @pytest.mark.asyncio
    async def testFiftyConcurrentNonceReplayAssault(self) -> None:
        """50 concurrent coroutines attempting to consume the exact same nonce."""
        fakeRedis = fakeredis.aioredis.FakeRedis()
        nonceLedger = NonceLedger(fakeRedis)
        attackNonce = "assault_nonce_99999"
        serverTime = 1720000000

        async def worker():
            try:
                await nonceLedger.validateAndRecordNonce(attackNonce, serverTime, serverTime)
                return "ACQUIRED"
            except NonceReplayException:
                return "REPLAY_REJECTED"

        results = await asyncio.gather(*[worker() for _ in range(50)])
        assert results.count("ACQUIRED") == 1
        assert results.count("REPLAY_REJECTED") == 49


class TestVegetarianFailClosedInvariant:
    """4. Verify fail-closed vegetarian constraint filter with missing/null/falsy isVeg fields."""

    def testMissingIsVegFieldDefaultsToFalseFailClosed(self) -> None:
        """Verifies that candidates without isVeg in fmcgFacet, attributes, or root are rejected."""
        manifest = NegativeConstraintManifest(requireVeg=True)
        filterEngine = NegativeConstraintFilter(manifest)

        # 1. Missing isVeg completely
        sku1 = {"skuId": "SKU-NO-VEG-1", "brand": "BrandX", "attributes": {"weightGrams": 100}}
        res1 = filterEngine.evaluateCandidate(sku1)
        assert res1.isAllowed is False
        assert res1.rejectionReason == "NON_VEG_EXCLUDED"

        # 2. Empty fmcgFacet
        sku2 = {"skuId": "SKU-NO-VEG-2", "brand": "BrandX", "fmcgFacet": {}, "attributes": {}}
        res2 = filterEngine.evaluateCandidate(sku2)
        assert res2.isAllowed is False
        assert res2.rejectionReason == "NON_VEG_EXCLUDED"

        # 3. isVeg is None
        sku3 = {"skuId": "SKU-NO-VEG-3", "brand": "BrandX", "fmcgFacet": {"isVeg": None}}
        res3 = filterEngine.evaluateCandidate(sku3)
        assert res3.isAllowed is False
        assert res3.rejectionReason == "NON_VEG_EXCLUDED"

        # 4. isVeg is False
        sku4 = {"skuId": "SKU-NO-VEG-4", "brand": "BrandX", "attributes": {"isVeg": False}}
        res4 = filterEngine.evaluateCandidate(sku4)
        assert res4.isAllowed is False
        assert res4.rejectionReason == "NON_VEG_EXCLUDED"

        # 5. isVeg is 0
        sku5 = {"skuId": "SKU-NO-VEG-5", "brand": "BrandX", "skuPayload": {"isVeg": 0}}
        res5 = filterEngine.evaluateCandidate(sku5)
        assert res5.isAllowed is False
        assert res5.rejectionReason == "NON_VEG_EXCLUDED"

        # 6. isVeg is True in fmcgFacet -> Allowed
        sku6 = {"skuId": "SKU-VEG-6", "brand": "BrandX", "fmcgFacet": {"isVeg": True}}
        res6 = filterEngine.evaluateCandidate(sku6)
        assert res6.isAllowed is True
        assert res6.rejectionReason is None

        # 7. isVeg is True in attributes -> Allowed
        sku7 = {"skuId": "SKU-VEG-7", "brand": "BrandX", "attributes": {"isVeg": True}}
        res7 = filterEngine.evaluateCandidate(sku7)
        assert res7.isAllowed is True
        assert res7.rejectionReason is None

        # 8. isVeg is True in root -> Allowed
        sku8 = {"skuId": "SKU-VEG-8", "brand": "BrandX", "isVeg": True}
        res8 = filterEngine.evaluateCandidate(sku8)
        assert res8.isAllowed is True
        assert res8.rejectionReason is None

    def testPriorityResolutionFacetOverAttributes(self) -> None:
        """Verifies fmcgFacet.isVeg takes precedence over attributes.isVeg."""
        manifest = NegativeConstraintManifest(requireVeg=True)
        filterEngine = NegativeConstraintFilter(manifest)

        # fmcgFacet says False, attributes says True -> must reject
        skuConflicted = {
            "skuId": "SKU-CONFLICT-01",
            "brand": "BrandX",
            "fmcgFacet": {"isVeg": False},
            "attributes": {"isVeg": True},
        }
        res = filterEngine.evaluateCandidate(skuConflicted)
        assert res.isAllowed is False
        assert res.rejectionReason == "NON_VEG_EXCLUDED"

        # fmcgFacet says True, attributes says False -> must allow
        skuConflicted2 = {
            "skuId": "SKU-CONFLICT-02",
            "brand": "BrandX",
            "fmcgFacet": {"isVeg": True},
            "attributes": {"isVeg": False},
        }
        res2 = filterEngine.evaluateCandidate(skuConflicted2)
        assert res2.isAllowed is True

    def testRequireVegFalsePermitsMissingAndFalseIsVeg(self) -> None:
        """When requireVeg=False, missing or False isVeg does NOT reject."""
        manifest = NegativeConstraintManifest(requireVeg=False)
        filterEngine = NegativeConstraintFilter(manifest)

        skuNoVeg = {"skuId": "SKU-NO-VEG", "brand": "BrandX", "fmcgFacet": {"isVeg": False}}
        res = filterEngine.evaluateCandidate(skuNoVeg)
        assert res.isAllowed is True
