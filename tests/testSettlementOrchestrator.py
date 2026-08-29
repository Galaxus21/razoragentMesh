"""Unit tests for 2PC Settlement Orchestrator and Saga Rollback Compensation."""

import pytest
import fakeredis.aioredis
from razoragentMesh.packages.mandateEngine.mandates.cartMandateSchema import (
    CartItemSchema,
    CartMandate,
    TaxBreakdownSchema,
)
from razoragentMesh.packages.mandateEngine.crypto.cryptoKeyUtils import generateKeyPair
from razoragentMesh.packages.mandateEngine.crypto.ed25519Signer import Ed25519Signer
from razoragentMesh.packages.mandateEngine.mandates.mandateFactory import (
    createSignedCartMandate,
    createSignedExecutionMandate,
    createSignedIntentMandate,
)
from razoragentMesh.packages.mandateEngine.nonce.nonceLedger import NonceLedger
from razoragentMesh.packages.mandateEngine.settlement.razorpayRouteClient import RazorpayRouteClient
from razoragentMesh.packages.mandateEngine.settlement.settlementExceptions import (
    SettlementCompensationTriggeredException,
)
from razoragentMesh.packages.mandateEngine.settlement.settlementOrchestrator import (
    SettlementOrchestrator,
    SettlementResult,
)


def _setupSagaMandates(amountPaise: int = 118000) -> tuple:
    """Sets up signed M_I, M_C, and M_E mandates."""
    uSigner = Ed25519Signer(generateKeyPair()[0])
    mSigner = Ed25519Signer(generateKeyPair()[0])
    aSigner = Ed25519Signer(generateKeyPair()[0])

    intentM = createSignedIntentMandate(
        mandateId="M-I-SAGA-01", userSigner=uSigner, delegatedAgentDid=aSigner.getAgentDid(),
        maxBudgetPaise=200000, upiCircleDelegationToken="upi_tok_saga",
        singleTransactionLimitPaise=200000, validUntilTimestamp=2000000000,
    )
    item = CartItemSchema(skuId="SKU-SAGA-01", quantity=1, unitPricePaise=100000, hsnCode="84713010", gstRatePercent=18, lineTotalPaise=100000)
    taxBreakdown = TaxBreakdownSchema(cgstPaise=9000, sgstPaise=9000, igstPaise=0, totalTaxPaise=18000)
    cartM = createSignedCartMandate(
        cartId="M-C-SAGA-01", merchantSigner=mSigner, merchantGstin="29AAAAA0000A1ZY",
        merchantStateCode="29", buyerDeliveryPincode="560001", buyerDeliveryStateCode="29",
        items=[item], taxableSubtotalPaise=100000, taxBreakdown=taxBreakdown,
        shippingPaise=0, discountPaise=0, totalPaise=amountPaise,
        inventoryLockToken="lock_saga", inventoryLockExpiresAt=2000000000,
    )
    execM = createSignedExecutionMandate(
        executionId="M-E-SAGA-01", buyerAgentSigner=aSigner, intentMandate=intentM,
        cartMandate=cartM, settlementAmountPaise=amountPaise, upiCircleToken="upi_tok_saga",
        timestamp=1700000000,
    )
    return intentM, cartM, execM



@pytest.mark.asyncio
async def testSettlementSagaHappyPath() -> None:
    """Verifies complete 2PC settlement lifecycle: capture, split transfers, and invoice."""
    fakeRedis = fakeredis.aioredis.FakeRedis()
    nonceLedger = NonceLedger(fakeRedis)
    routeClient = RazorpayRouteClient(isMockMode=True)
    orchestrator = SettlementOrchestrator(
        routeClient=routeClient,
        nonceLedger=nonceLedger,
        protocolFeeAccount="acc_protocol_fees",
        protocolFeePaise=50,
    )

    intentM, cartM, execM = _setupSagaMandates(amountPaise=118000)

    result = await orchestrator.executeSettlementSaga(
        intentMandate=intentM,
        cartMandate=cartM,
        executionMandate=execM,
        merchantAccount="acc_merchant_123",
        paymentId="pay_happy_path_001",
        serverTime=1700000000,
    )

    assert isinstance(result, SettlementResult)
    assert result.status == "captured"
    assert result.amountPaise == 118000
    assert len(result.transfers) == 3  # Merchant net + Protocol fee + Section 52 TCS withholding
    assert sum(t.amount for t in result.transfers) == result.amountPaise
    assert result.invoice.grandTotalPaise == 118000


@pytest.mark.asyncio
async def testSettlementSagaRollbackCompensation() -> None:
    """Verifies that failure in split transfer triggers reverse_transfer rollback."""
    fakeRedis = fakeredis.aioredis.FakeRedis()
    nonceLedger = NonceLedger(fakeRedis)
    routeClient = RazorpayRouteClient(isMockMode=True)

    # Configure protocol fee transfer to fail
    routeClient.simulatedFailureAccount = "acc_protocol_fees"

    orchestrator = SettlementOrchestrator(
        routeClient=routeClient,
        nonceLedger=nonceLedger,
        protocolFeeAccount="acc_protocol_fees",
        protocolFeePaise=50,
    )

    intentM, cartM, execM = _setupSagaMandates(amountPaise=118000)

    with pytest.raises(SettlementCompensationTriggeredException):
        await orchestrator.executeSettlementSaga(
            intentMandate=intentM,
            cartMandate=cartM,
            executionMandate=execM,
            merchantAccount="acc_merchant_123",
            paymentId="pay_fail_001",
            serverTime=1700000000,
        )

    # Verify that the initial merchant transfer was rolled back via reversal
    assert len(routeClient._reversals) == 1
