"""Challenger 1 Empirical Stress: 2PC Saga Reversals and Negative Constraint Invariants.

Tests:
1. 2PC Route settlement sagas under concurrent failures, LIFO reversals, and nonces
2. Fail-closed vegetarian constraint filter with missing/null/falsy isVeg fields
"""

import asyncio
from typing import Any, Dict, List
import fakeredis.aioredis
import pytest

from razoragentMesh.packages.mandateEngine.crypto.cryptoKeyUtils import generateKeyPair
from razoragentMesh.packages.mandateEngine.crypto.ed25519Signer import Ed25519Signer
from razoragentMesh.packages.mandateEngine.mandates.cartMandateSchema import (
    CartItemSchema,
    TaxBreakdownSchema,
)
from razoragentMesh.packages.mandateEngine.mandates.mandateFactory import (
    createSignedCartMandate,
    createSignedExecutionMandate,
    createSignedIntentMandate,
)
from razoragentMesh.packages.mandateEngine.nonce.nonceLedger import NonceLedger
from razoragentMesh.packages.mandateEngine.settlement.razorpayRouteClient import (
    RazorpayRouteClient,
)
from razoragentMesh.packages.mandateEngine.settlement.settlementExceptions import (
    NonceReplayException,
    SettlementCompensationTriggeredException,
)
from razoragentMesh.packages.mandateEngine.settlement.settlementOrchestrator import (
    SettlementOrchestrator,
    SettlementResult,
)
from razoragentMesh.packages.vectorHealer.src.constraints.constraintFilter import (
    NegativeConstraintFilter,
)
from razoragentMesh.packages.vectorHealer.src.constraints.negativeManifestSchema import (
    NegativeConstraintManifest,
)


def _buildSagaMandates(idx: int, uSigner, mSigner, aSigner, fixedTime: int):
    intentM = createSignedIntentMandate(
        mandateId=f"M-I-CONC-{idx}", userSigner=uSigner,
        delegatedAgentDid=aSigner.getAgentDid(), maxBudgetPaise=1000000,
        upiCircleDelegationToken=f"upi_tok_conc_{idx}", singleTransactionLimitPaise=1000000,
        validUntilTimestamp=2000000000,
    )
    item = CartItemSchema(
        skuId=f"SKU-CONC-{idx}", quantity=1, unitPricePaise=200000,
        hsnCode="8471", gstRatePercent=18, lineTotalPaise=200000,
    )
    cartM = createSignedCartMandate(
        cartId=f"M-C-CONC-{idx}", merchantSigner=mSigner,
        merchantGstin="29AAAAA0000A1ZY", merchantStateCode="29",
        buyerDeliveryPincode="560001", buyerDeliveryStateCode="29",
        items=[item], taxableSubtotalPaise=200000,
        taxBreakdown=TaxBreakdownSchema(cgstPaise=18000, sgstPaise=18000, igstPaise=0, totalTaxPaise=36000),
        shippingPaise=5000, discountPaise=0, totalPaise=241000,
        inventoryLockToken=f"lock_conc_{idx}", inventoryLockExpiresAt=2000000000,
    )
    execM = createSignedExecutionMandate(
        executionId=f"M-E-CONC-{idx}", buyerAgentSigner=aSigner,
        intentMandate=intentM, cartMandate=cartM, settlementAmountPaise=241000,
        upiCircleToken=f"upi_tok_conc_{idx}", timestamp=fixedTime, nonce=f"nonce_conc_test_{idx}",
    )
    return intentM, cartM, execM


async def _runSingleSaga(idx: int, routeClient, nonceLedger, uSigner, mSigner, aSigner, fixedTime: int):
    mAcc = "acc_merch_failing_03" if idx == 3 else f"acc_merchant_{idx}"
    pAcc = "acc_proto_failing_04" if idx == 4 else f"acc_proto_{idx}"
    lAcc = "acc_logistics_failing_05" if idx == 5 else f"acc_logistics_{idx}"
    orchestrator = SettlementOrchestrator(
        routeClient=routeClient, nonceLedger=nonceLedger,
        protocolFeeAccount=pAcc, protocolFeePaise=100, logisticsAccount=lAcc,
    )
    intentM, cartM, execM = _buildSagaMandates(idx, uSigner, mSigner, aSigner, fixedTime)
    return await orchestrator.executeSettlementSaga(
        intentMandate=intentM, cartMandate=cartM, executionMandate=execM,
        merchantAccount=mAcc, paymentId=f"pay_conc_{idx}", serverTime=fixedTime,
    )


class TestConcurrentSettlementSagaAndReversals:
    """3. 2PC Route settlement sagas under concurrent failures, LIFO reversals, and nonces."""

    @pytest.mark.asyncio
    async def testTenConcurrentSagasWithVariedFailurePoints(self) -> None:
        """Dispatches 10 sagas: some succeed, some fail at merchant, protocol, or logistics."""
        fakeRedis = fakeredis.aioredis.FakeRedis()
        nonceLedger = NonceLedger(fakeRedis)
        routeClient = RazorpayRouteClient(isMockMode=True)
        uSigner = Ed25519Signer(generateKeyPair()[0])
        mSigner = Ed25519Signer(generateKeyPair()[0])
        aSigner = Ed25519Signer(generateKeyPair()[0])
        fixedTime = 1710000000

        for idx in range(10):
            if idx == 3:
                routeClient.simulatedFailureAccount = "acc_merch_failing_03"
                with pytest.raises(SettlementCompensationTriggeredException) as excInfo:
                    await _runSingleSaga(idx, routeClient, nonceLedger, uSigner, mSigner, aSigner, fixedTime)
                assert "rollback of 0 transfers" in str(excInfo.value)
            elif idx == 4:
                routeClient.simulatedFailureAccount = "acc_proto_failing_04"
                with pytest.raises(SettlementCompensationTriggeredException) as excInfo:
                    await _runSingleSaga(idx, routeClient, nonceLedger, uSigner, mSigner, aSigner, fixedTime)
                assert "rollback of 1 transfers" in str(excInfo.value)
            elif idx == 5:
                routeClient.simulatedFailureAccount = "acc_logistics_failing_05"
                with pytest.raises(SettlementCompensationTriggeredException) as excInfo:
                    await _runSingleSaga(idx, routeClient, nonceLedger, uSigner, mSigner, aSigner, fixedTime)
                assert "rollback of 2 transfers" in str(excInfo.value)
            else:
                routeClient.simulatedFailureAccount = None
                result = await _runSingleSaga(idx, routeClient, nonceLedger, uSigner, mSigner, aSigner, fixedTime)
                assert isinstance(result, SettlementResult) and result.status == "captured"

            with pytest.raises(NonceReplayException):
                await nonceLedger.validateAndRecordNonce(f"nonce_conc_test_{idx}", timestamp=fixedTime, serverTime=fixedTime)

    @pytest.mark.asyncio
    async def testFiftyConcurrentNonceReplayAssault(self) -> None:
        """50 concurrent coroutines attempting to consume the exact same nonce."""
        nonceLedger = NonceLedger(fakeredis.aioredis.FakeRedis())
        attackNonce, serverTime = "assault_nonce_99999", 1720000000

        async def worker():
            try:
                await nonceLedger.validateAndRecordNonce(attackNonce, serverTime, serverTime)
                return "ACQUIRED"
            except NonceReplayException:
                return "REPLAY_REJECTED"

        results = await asyncio.gather(*[worker() for _ in range(50)])
        assert results.count("ACQUIRED") == 1 and results.count("REPLAY_REJECTED") == 49


class TestVegetarianFailClosedInvariant:
    """4. Verify fail-closed vegetarian constraint filter with missing/null/falsy isVeg fields."""

    def testMissingOrFalsyIsVegRejections(self) -> None:
        filterEngine = NegativeConstraintFilter(NegativeConstraintManifest(requireVeg=True))
        sku1 = {"skuId": "SKU-NO-VEG-1", "brand": "BrandX", "attributes": {"weightGrams": 100}}
        assert filterEngine.evaluateCandidate(sku1).isAllowed is False
        sku2 = {"skuId": "SKU-NO-VEG-2", "brand": "BrandX", "fmcgFacet": {}, "attributes": {}}
        assert filterEngine.evaluateCandidate(sku2).isAllowed is False
        sku3 = {"skuId": "SKU-NO-VEG-3", "brand": "BrandX", "fmcgFacet": {"isVeg": None}}
        assert filterEngine.evaluateCandidate(sku3).isAllowed is False
        sku4 = {"skuId": "SKU-NO-VEG-4", "brand": "BrandX", "attributes": {"isVeg": False}}
        assert filterEngine.evaluateCandidate(sku4).isAllowed is False
        sku5 = {"skuId": "SKU-NO-VEG-5", "brand": "BrandX", "skuPayload": {"isVeg": 0}}
        assert filterEngine.evaluateCandidate(sku5).isAllowed is False

    def testTruthyIsVegAllowed(self) -> None:
        filterEngine = NegativeConstraintFilter(NegativeConstraintManifest(requireVeg=True))
        sku6 = {"skuId": "SKU-VEG-6", "brand": "BrandX", "fmcgFacet": {"isVeg": True}}
        assert filterEngine.evaluateCandidate(sku6).isAllowed is True
        sku7 = {"skuId": "SKU-VEG-7", "brand": "BrandX", "attributes": {"isVeg": True}}
        assert filterEngine.evaluateCandidate(sku7).isAllowed is True
        sku8 = {"skuId": "SKU-VEG-8", "brand": "BrandX", "isVeg": True}
        assert filterEngine.evaluateCandidate(sku8).isAllowed is True

    def testPriorityResolutionFacetOverAttributes(self) -> None:
        filterEngine = NegativeConstraintFilter(NegativeConstraintManifest(requireVeg=True))
        skuConflicted = {"skuId": "SKU-C1", "brand": "BrandX", "fmcgFacet": {"isVeg": False}, "attributes": {"isVeg": True}}
        assert filterEngine.evaluateCandidate(skuConflicted).isAllowed is False
        skuConflicted2 = {"skuId": "SKU-C2", "brand": "BrandX", "fmcgFacet": {"isVeg": True}, "attributes": {"isVeg": False}}
        assert filterEngine.evaluateCandidate(skuConflicted2).isAllowed is True

    def testRequireVegFalsePermitsMissingAndFalseIsVeg(self) -> None:
        filterEngine = NegativeConstraintFilter(NegativeConstraintManifest(requireVeg=False))
        skuNoVeg = {"skuId": "SKU-NO-VEG", "brand": "BrandX", "fmcgFacet": {"isVeg": False}}
        assert filterEngine.evaluateCandidate(skuNoVeg).isAllowed is True
