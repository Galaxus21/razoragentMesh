"""Adversarial Benchmark Module 2 — Concurrent Settlement Race & Boundary Invariant.

Covers:
- TC-13: 5 concurrent 2PC settlement sagas (asyncio.gather), secondary transfer crash
         triggering atomic LIFO compensating reversals, and nonce invalidation.
- TC-14: Split manifest boundary & negative value injection testing rejecting negative prices,
         negative transfers, sum divergence, and float math.
"""

import asyncio
from typing import Any, Tuple
import fakeredis.aioredis
from pydantic import ValidationError
import pytest

from razoragentMesh.packages.mandateEngine.crypto.cryptoKeyUtils import generateKeyPair
from razoragentMesh.packages.mandateEngine.crypto.ed25519Signer import Ed25519Signer
from razoragentMesh.packages.mandateEngine.crypto.jcsCanonicalizer import (
    canonicalizeJson,
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
    NonceReplayException,
    SettlementCompensationTriggeredException,
)
from razoragentMesh.packages.mandateEngine.settlement.settlementOrchestrator import (
    SettlementOrchestrator,
    SettlementResult,
)
from razoragentMesh.packages.mandateEngine.settlement.splitManifestBuilder import (
    SplitTransferManifest,
    buildSplitManifest,
)
from razoragentMesh.packages.mandateEngine.verification.arithmeticEnclave import (
    computeCartSettlementTotal,
    computeGstBreakdown,
    computeLineItemTotal,
    computeTcsWithholding,
    validateIntegerPaise,
)

fixedServerTimeTc13: int = 1700000000
taxableSubtotalTc13: int = 100000
taxPaiseTc13: int = 18000
shippingPaiseTc13: int = 2000
grossSettlementPaiseTc13: int = 120000
failingLogisticsAccountTc13: str = "acc_logistics_fail_tc13"
standardLogisticsAccountTc13: str = "acc_logistics_ok"
protocolFeeAccountTc13: str = "acc_protocol_fees"
protocolFeePaiseTc13: int = 50


def _buildRaceMandateTriplet(
    index: int,
    userSigner: Ed25519Signer,
    merchantSigner: Ed25519Signer,
    agentSigner: Ed25519Signer,
) -> Tuple[IntentMandate, CartMandate, ExecutionMandate]:
    """Builds unique signed mandate chain for a race test participant."""
    intentM = createSignedIntentMandate(
        mandateId=f"M-I-RACE-{index}",
        userSigner=userSigner,
        delegatedAgentDid=agentSigner.getAgentDid(),
        maxBudgetPaise=500000,
        upiCircleDelegationToken=f"upi_tok_race_{index}",
        singleTransactionLimitPaise=500000,
        validUntilTimestamp=2000000000,
    )

    item = CartItemSchema(
        skuId=f"SKU-RACE-{index}",
        quantity=1,
        unitPricePaise=taxableSubtotalTc13,
        hsnCode="84713010",
        gstRatePercent=18,
        lineTotalPaise=taxableSubtotalTc13,
    )
    taxBreakdown = TaxBreakdownSchema(
        cgstPaise=9000,
        sgstPaise=9000,
        igstPaise=0,
        totalTaxPaise=taxPaiseTc13,
    )
    cartM = createSignedCartMandate(
        cartId=f"M-C-RACE-{index}",
        merchantSigner=merchantSigner,
        merchantGstin="29AAAAA0000A1Z5",
        merchantStateCode="29",
        buyerDeliveryPincode="560001",
        buyerDeliveryStateCode="29",
        items=[item],
        taxableSubtotalPaise=taxableSubtotalTc13,
        taxBreakdown=taxBreakdown,
        shippingPaise=shippingPaiseTc13,
        discountPaise=0,
        totalPaise=grossSettlementPaiseTc13,
        inventoryLockToken=f"lock_race_{index}",
        inventoryLockExpiresAt=2000000000,
    )

    execM = createSignedExecutionMandate(
        executionId=f"M-E-RACE-{index}",
        buyerAgentSigner=agentSigner,
        intentMandate=intentM,
        cartMandate=cartM,
        settlementAmountPaise=grossSettlementPaiseTc13,
        upiCircleToken=f"upi_tok_race_{index}",
        timestamp=fixedServerTimeTc13,
        nonce=f"nonce_tc13_race_{index}",
    )
    return intentM, cartM, execM


@pytest.mark.asyncio
async def testTc13ConcurrentTwoPhaseCommitSettlementRaceAndRollback() -> None:
    """TC-13: 5 concurrent 2PC sagas with 1 simulated transfer failure triggering LIFO rollback."""
    fakeRedis = fakeredis.aioredis.FakeRedis()
    nonceLedger = NonceLedger(fakeRedis)
    routeClient = RazorpayRouteClient(isMockMode=True)
    routeClient.simulatedFailureAccount = failingLogisticsAccountTc13

    uPriv, _ = generateKeyPair()
    mPriv, _ = generateKeyPair()
    aPriv, _ = generateKeyPair()
    uSigner = Ed25519Signer(uPriv)
    mSigner = Ed25519Signer(mPriv)
    aSigner = Ed25519Signer(aPriv)

    failingIndex = 2

    async def executeSingleSaga(idx: int) -> SettlementResult:
        logisticsAcc = failingLogisticsAccountTc13 if idx == failingIndex else standardLogisticsAccountTc13
        orchestrator = SettlementOrchestrator(
            routeClient=routeClient,
            nonceLedger=nonceLedger,
            protocolFeeAccount=protocolFeeAccountTc13,
            protocolFeePaise=protocolFeePaiseTc13,
            logisticsAccount=logisticsAcc,
        )
        intentM, cartM, execM = _buildRaceMandateTriplet(idx, uSigner, mSigner, aSigner)
        return await orchestrator.executeSettlementSaga(
            intentMandate=intentM,
            cartMandate=cartM,
            executionMandate=execM,
            merchantAccount=f"acc_merchant_{idx}",
            paymentId=f"pay_race_{idx}",
            serverTime=fixedServerTimeTc13,
        )

    results = await asyncio.gather(*[executeSingleSaga(i) for i in range(5)], return_exceptions=True)

    for idx, res in enumerate(results):
        if idx == failingIndex:
            assert isinstance(res, SettlementCompensationTriggeredException)
        else:
            assert isinstance(res, SettlementResult)
            assert res.status == "captured"

    # LIFO Reversal assertion: 2 successful transfers in failing saga were reversed
    assert len(routeClient._reversals) == 2

    # Nonce invalidation assertion: Phase 1 consumed the nonce, replay must be blocked
    failedNonce = f"nonce_tc13_race_{failingIndex}"
    with pytest.raises(NonceReplayException):
        await nonceLedger.validateAndRecordNonce(failedNonce, fixedServerTimeTc13, fixedServerTimeTc13)


def testTc14SplitManifestBoundaryAndNegativeValueInjection() -> None:
    """TC-14: Reject malformed split manifests, negative line totals, and negative transfers."""
    with pytest.raises(ArithmeticDriftException):
        computeLineItemTotal(-50000, 2)

    with pytest.raises(ArithmeticDriftException):
        computeLineItemTotal(50000, 0)

    with pytest.raises(ArithmeticDriftException):
        computeLineItemTotal(50000, -2)

    with pytest.raises(ArithmeticDriftException):
        computeCartSettlementTotal(10000, 1800, shippingPaise=0, discountPaise=20000)

    with pytest.raises(ArithmeticDriftException):
        computeGstBreakdown(-1000, 18, isIntraState=False)

    with pytest.raises(ArithmeticDriftException):
        computeGstBreakdown(1000, -5, isIntraState=False)

    with pytest.raises(ArithmeticDriftException):
        computeTcsWithholding(-500, isIntraState=False)

    with pytest.raises(ValidationError):
        RouteTransferRequest(account="acc_merch", amount=-100)

    with pytest.raises(ValidationError):
        RouteTransferRequest(account="acc_merch", amount=0)

    with pytest.raises(ValidationError):
        SplitTransferManifest(
            merchantAccount="acc_m",
            merchantAmountPaise=0,
            protocolFeeAccount="acc_p",
            protocolFeePaise=0,
            logisticsAccount="acc_l",
            logisticsAmountPaise=0,
            totalPaise=100,
        )


def testTc14FloatAndTypePoisoningRejection() -> None:
    """TC-14: Reject float values, string boolean poisoning, and non-integer types."""
    with pytest.raises(ArithmeticDriftException):
        validateIntegerPaise(42.50, "unitPricePaise")

    with pytest.raises(ArithmeticDriftException):
        validateIntegerPaise(True, "quantity")

    with pytest.raises(ArithmeticDriftException):
        validateIntegerPaise("5000", "unitPricePaise")

    with pytest.raises(ArithmeticDriftException):
        canonicalizeJson({"price": 42.50})

    validInt = validateIntegerPaise(100000, "unitPricePaise")
    assert validInt == 100000
