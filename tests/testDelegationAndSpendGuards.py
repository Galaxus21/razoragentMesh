"""Negative tests for the AP2 delegation and cumulative-spend guards.

Each test here targets a specific authorization gap that was live in the codebase and that the
existing 1,212-test suite did not detect, because no test exercised the adversarial path:

* the agent a user delegated to was recorded in the IntentMandate and never compared against the
  agent that actually signed the ExecutionMandate;
* `maxBudgetPaise` was documented as a cumulative cap but enforced per-transaction;
* the nonce ledger stopped an identical ExecutionMandate being replayed, but not a fresh one
  minted against the same signed cart;
* `inventoryLockExpiresAt` was carried on the cart and never checked;
* the nonce was consumed before signatures were verified, so an unauthenticated caller could
  burn it and fail the legitimate settlement.

Assertions encode the intended AP2 delegation semantics, not the current implementation's output.
"""

import time
from typing import Optional

import fakeredis.aioredis
import pytest

from razoragentMesh.packages.mandateEngine.crypto.cryptoKeyUtils import generateKeyPair
from razoragentMesh.packages.mandateEngine.crypto.ed25519Signer import Ed25519Signer
from razoragentMesh.packages.mandateEngine.mandates.cartMandateSchema import (
    CartItemSchema,
    CartMandate,
    TaxBreakdownSchema,
)
from razoragentMesh.packages.mandateEngine.mandates.intentMandateSchema import IntentMandate
from razoragentMesh.packages.mandateEngine.mandates.mandateFactory import (
    createSignedCartMandate,
    createSignedExecutionMandate,
    createSignedIntentMandate,
)
from razoragentMesh.packages.mandateEngine.nonce.nonceLedger import NonceLedger, nonceRedisKeyPrefix
from razoragentMesh.packages.mandateEngine.settlement.razorpayRouteClient import RazorpayRouteClient
from razoragentMesh.packages.mandateEngine.settlement.settlementExceptions import (
    CartAlreadySettledException,
    CumulativeBudgetExceededException,
    InventoryLockExpiredException,
    SignatureVerificationFailedException,
    UnauthorizedAgentException,
)
from razoragentMesh.packages.mandateEngine.settlement.twoPhaseCommitSaga import TwoPhaseCommitSaga
from razoragentMesh.packages.mandateEngine.verification.arithmeticEnclave import (
    computeCartSettlementTotal,
    computeGstBreakdown,
    computeLineItemTotal,
)
from razoragentMesh.packages.mandateEngine.verification.budgetGate import validateBudgetGate
from razoragentMesh.packages.mandateEngine.verification.settlementLedger import SettlementLedger

unitPricePaise: int = 100000
gstRatePercent: int = 18
sharedStateCode: str = "29"
maxBudgetPaise: int = 500000


def _buildCart(merchantSigner: Ed25519Signer, lockExpiresAt: Optional[int] = None) -> CartMandate:
    """Builds a merchant-signed single-line cart whose totals satisfy the enclave recomputation."""
    lineTotal = computeLineItemTotal(unitPricePaise, 1)
    gst = computeGstBreakdown(lineTotal, gstRatePercent, True)
    total = computeCartSettlementTotal(lineTotal, gst.totalTaxPaise, 0, 0)
    return createSignedCartMandate(
        cartId="cart_guard_001", merchantSigner=merchantSigner,
        merchantGstin="29AAAAA0000A1ZY", merchantStateCode=sharedStateCode,
        buyerDeliveryPincode="560001", buyerDeliveryStateCode=sharedStateCode,
        items=[CartItemSchema(
            skuId="SKU-GUARD-001", quantity=1, unitPricePaise=unitPricePaise,
            hsnCode="94018010", gstRatePercent=gstRatePercent, lineTotalPaise=lineTotal,
        )],
        taxableSubtotalPaise=lineTotal,
        taxBreakdown=TaxBreakdownSchema(
            cgstPaise=gst.cgstPaise, sgstPaise=gst.sgstPaise,
            igstPaise=gst.igstPaise, totalTaxPaise=gst.totalTaxPaise,
        ),
        shippingPaise=0, discountPaise=0, totalPaise=total,
        inventoryLockToken="lock_guard_001",
        inventoryLockExpiresAt=lockExpiresAt if lockExpiresAt is not None else int(time.time()) + 600,
    )


def _buildIntent(userSigner: Ed25519Signer, delegatedAgentDid: str) -> IntentMandate:
    return createSignedIntentMandate(
        mandateId="M-GUARD-001", userSigner=userSigner, delegatedAgentDid=delegatedAgentDid,
        maxBudgetPaise=maxBudgetPaise, upiCircleDelegationToken="upi_tok_guard",
        singleTransactionLimitPaise=maxBudgetPaise,
    )


def _signers() -> tuple[Ed25519Signer, Ed25519Signer, Ed25519Signer]:
    """Returns (user, merchant, buyerAgent) signers with independent keypairs."""
    return tuple(Ed25519Signer(generateKeyPair()[0]) for _ in range(3))  # type: ignore[return-value]


# --- P0-1: delegated agent binding -------------------------------------------------------------

def testUnauthorizedAgentCannotSpendAnotherAgentsMandate() -> None:
    """An agent that is not the delegate named in the IntentMandate MUST be rejected.

    The verifying key is derived from the DID inside each mandate, so an attacker's own signature
    is internally valid; only the delegation comparison stops them spending the user's budget.
    """
    userSigner, merchantSigner, delegatedAgent = _signers()
    attackerAgent = Ed25519Signer(generateKeyPair()[0])

    intent = _buildIntent(userSigner, delegatedAgent.getAgentDid())
    cart = _buildCart(merchantSigner)
    attackerExecution = createSignedExecutionMandate(
        executionId="M-E-ATTACK", buyerAgentSigner=attackerAgent, intentMandate=intent,
        cartMandate=cart, settlementAmountPaise=cart.totalPaise, upiCircleToken="upi_tok_guard",
    )

    with pytest.raises(UnauthorizedAgentException):
        validateBudgetGate(intent, cart, attackerExecution)


def testDelegatedAgentIsAccepted() -> None:
    """Control: the agent the user actually delegated to passes the same gate."""
    userSigner, merchantSigner, delegatedAgent = _signers()
    intent = _buildIntent(userSigner, delegatedAgent.getAgentDid())
    cart = _buildCart(merchantSigner)
    execution = createSignedExecutionMandate(
        executionId="M-E-OK", buyerAgentSigner=delegatedAgent, intentMandate=intent,
        cartMandate=cart, settlementAmountPaise=cart.totalPaise, upiCircleToken="upi_tok_guard",
    )

    assert validateBudgetGate(intent, cart, execution) is True


# --- P0-2: cumulative budget --------------------------------------------------------------------

@pytest.mark.asyncio
async def testCumulativeSpendIsBoundedAcrossSeparateSettlements() -> None:
    """maxBudgetPaise is a cumulative ceiling: repeated settlements must exhaust it, not reset it."""
    ledger = SettlementLedger(redisClient=fakeredis.aioredis.FakeRedis(decode_responses=True))

    assert await ledger.recordCumulativeSpend("M-CUM", 300000, maxBudgetPaise) == 300000
    assert await ledger.recordCumulativeSpend("M-CUM", 150000, maxBudgetPaise) == 450000

    with pytest.raises(CumulativeBudgetExceededException):
        await ledger.recordCumulativeSpend("M-CUM", 100000, maxBudgetPaise)


@pytest.mark.asyncio
async def testBreachedSpendAttemptDoesNotConsumeBudget() -> None:
    """A rejected settlement must not leave its amount booked against the mandate."""
    ledger = SettlementLedger(redisClient=fakeredis.aioredis.FakeRedis(decode_responses=True))
    await ledger.recordCumulativeSpend("M-ROLLBACK", 450000, maxBudgetPaise)

    with pytest.raises(CumulativeBudgetExceededException):
        await ledger.recordCumulativeSpend("M-ROLLBACK", 100000, maxBudgetPaise)

    assert await ledger.getCumulativeSpend("M-ROLLBACK") == 450000


@pytest.mark.asyncio
async def testSpendLedgerFailsOpenWithoutRedis() -> None:
    """With no Redis the cap cannot be enforced; settlement proceeds rather than hard-failing."""
    ledger = SettlementLedger(redisClient=None)
    assert await ledger.recordCumulativeSpend("M-NOREDIS", 10**9, maxBudgetPaise) == 10**9


# --- P0-3: cart replay and inventory lock -------------------------------------------------------

@pytest.mark.asyncio
async def testSameCartCannotBeSettledTwice() -> None:
    """A fresh nonce must not permit re-settling an already-settled cart."""
    ledger = SettlementLedger(redisClient=fakeredis.aioredis.FakeRedis(decode_responses=True))
    await ledger.claimCartSettlement("cart_hash_abc")

    with pytest.raises(CartAlreadySettledException):
        await ledger.claimCartSettlement("cart_hash_abc")


@pytest.mark.asyncio
async def testExpiredInventoryLockIsRejected() -> None:
    """Settling against a lapsed reservation must fail: the stock may already be resold."""
    userSigner, merchantSigner, agent = _signers()
    expiredCart = _buildCart(merchantSigner, lockExpiresAt=int(time.time()) - 1)
    intent = _buildIntent(userSigner, agent.getAgentDid())
    execution = createSignedExecutionMandate(
        executionId="M-E-EXPIRED", buyerAgentSigner=agent, intentMandate=intent,
        cartMandate=expiredCart, settlementAmountPaise=expiredCart.totalPaise,
        upiCircleToken="upi_tok_guard",
    )
    saga = TwoPhaseCommitSaga(
        routeClient=RazorpayRouteClient(isMockMode=True),
        nonceLedger=NonceLedger(fakeredis.aioredis.FakeRedis(decode_responses=True)),
    )

    with pytest.raises(InventoryLockExpiredException):
        await saga.verifyAndCapturePhase(intent, expiredCart, execution, paymentId="pay_expired")


# --- P1-4: authenticate before consuming single-use state ---------------------------------------

@pytest.mark.asyncio
async def testNonceSurvivesAnUnauthenticatedSettlementAttempt() -> None:
    """A forged mandate must not burn the legitimate agent's nonce.

    Consuming the nonce before signature verification would let anyone who learns a nonce grief
    the real settlement into a 409.
    """
    userSigner, merchantSigner, agent = _signers()
    intent = _buildIntent(userSigner, agent.getAgentDid())
    cart = _buildCart(merchantSigner)
    execution = createSignedExecutionMandate(
        executionId="M-E-FORGED", buyerAgentSigner=agent, intentMandate=intent,
        cartMandate=cart, settlementAmountPaise=cart.totalPaise, upiCircleToken="upi_tok_guard",
    )
    tampered = execution.model_copy(update={"agentSignature": "0" * 128})

    redisClient = fakeredis.aioredis.FakeRedis(decode_responses=True)
    saga = TwoPhaseCommitSaga(
        routeClient=RazorpayRouteClient(isMockMode=True),
        nonceLedger=NonceLedger(redisClient),
    )

    with pytest.raises(SignatureVerificationFailedException):
        await saga.verifyAndCapturePhase(intent, cart, tampered, paymentId="pay_forged")

    assert await redisClient.get(f"{nonceRedisKeyPrefix}{execution.nonce}") is None
