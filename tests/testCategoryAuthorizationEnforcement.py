"""Pins that `authorizedCategories` is a control and not a label.

The audit's finding was narrow and total: `validateBudgetGate` accepted a `skuCategories`
argument, `_verifyCategoryAuthorization` was written to check it, and no production caller ever
passed one -- `twoPhaseCommitSaga` called the gate positionally with four arguments, the fourth
of which is `currentTimestamp`. So the branch could not execute outside a test that invoked the
gate directly, and the MCP server's `establish_agent_delegation` correctly disclosed
`category_enforcement: "advertised_only"`.

Two properties have to hold for that to stay fixed, and each needs its own test:

1. The categories must REACH the gate from the settlement path, not merely from a direct call.
   `testUnauthorizedCategoryRejection` in testAdversarialChallenger1BudgetSaga.py already passed
   while the control was dead, because it called `validateBudgetGate` itself -- which is exactly
   why a saga-level test is the one that matters here.
2. They must come from the MERCHANT-SIGNED cart. A category the buyer's agent could choose is
   not a constraint on the buyer's agent.
"""

import time
from typing import Any, Dict

import pytest

from razoragentMesh.packages.mandateEngine.crypto.jcsCanonicalizer import canonicalizeJson
from razoragentMesh.packages.mandateEngine.mandates.cartMandateSchema import (
    uncategorizedCartItemCategory,
)
from razoragentMesh.packages.mandateEngine.mandates.mandateFactory import (
    createSignedIntentMandate,
)
from razoragentMesh.packages.mandateEngine.settlement.settlementExceptions import (
    CategoryNotAuthorizedException,
)
from razoragentMesh.packages.mandateEngine.settlement.twoPhaseCommitSaga import (
    _signedCartCategories,
)
from razoragentMesh.tests.integration.testEndToEndFixtures import (
    buildStandardCartMandate,
    buildStandardExecutionMandate,
    defaultCategory,
    defaultLockToken,
    defaultMerchantAccount,
    defaultUpiToken,
    setupIntegrationOrchestrator,
    setupIntegrationSigners,
)

unauthorizedCategory: str = "luxury_jewelry"
settlementBudgetPaise: int = 5000000


def _buildMandates(
    agentKeyFixtures: Dict[str, Any], authorizedCategories: list, currentTime: int
) -> tuple:
    """Builds a signed mandate chain whose cart is classified as `defaultCategory`."""
    signers = setupIntegrationSigners(agentKeyFixtures)
    intentMandate = createSignedIntentMandate(
        mandateId="intent_category_001", userSigner=signers.userSigner,
        delegatedAgentDid=signers.buyerSigner.getAgentDid(),
        maxBudgetPaise=settlementBudgetPaise, upiCircleDelegationToken=defaultUpiToken,
        singleTransactionLimitPaise=settlementBudgetPaise,
        authorizedCategories=authorizedCategories, timestamp=currentTime,
    )
    cartMandate, totalGrossPaise = buildStandardCartMandate(
        signers, defaultLockToken, currentTime
    )
    executionMandate = buildStandardExecutionMandate(
        signers.buyerSigner, intentMandate, cartMandate, totalGrossPaise, currentTime,
    )
    return signers, intentMandate, cartMandate, executionMandate


@pytest.mark.asyncio
async def testSettlementRefusesACartOutsideTheDelegatedCategories(
    agentKeyFixtures: Dict[str, Any],
    mockRedisClient: Any,
) -> None:
    """The saga -- not a direct gate call -- rejects a cart the delegation does not cover.

    This is the assertion that failed to exist for the whole life of the project: a delegation
    scoped to jewellery settled a cart of industrial electronics without complaint.
    """
    currentTime = int(time.time())
    _, intentMandate, cartMandate, executionMandate = _buildMandates(
        agentKeyFixtures, [unauthorizedCategory], currentTime
    )
    orchestrator = setupIntegrationOrchestrator(mockRedisClient=mockRedisClient)

    with pytest.raises(CategoryNotAuthorizedException) as excInfo:
        await orchestrator.executeSettlementSaga(
            intentMandate=intentMandate, cartMandate=cartMandate,
            executionMandate=executionMandate, merchantAccount=defaultMerchantAccount,
            paymentId="pay_category_reject_001", serverTime=currentTime,
        )
    assert defaultCategory in str(excInfo.value)
    assert unauthorizedCategory in str(excInfo.value)


@pytest.mark.asyncio
async def testSettlementAllowsACartInsideTheDelegatedCategories(
    agentKeyFixtures: Dict[str, Any],
    mockRedisClient: Any,
) -> None:
    """The same chain settles when the delegation does cover the cart's category.

    Without this, a gate that rejected everything would look identical to a gate that works.
    """
    currentTime = int(time.time())
    _, intentMandate, cartMandate, executionMandate = _buildMandates(
        agentKeyFixtures, [defaultCategory], currentTime
    )
    orchestrator = setupIntegrationOrchestrator(mockRedisClient=mockRedisClient)

    result = await orchestrator.executeSettlementSaga(
        intentMandate=intentMandate, cartMandate=cartMandate,
        executionMandate=executionMandate, merchantAccount=defaultMerchantAccount,
        paymentId="pay_category_allow_001", serverTime=currentTime,
    )
    assert result is not None


@pytest.mark.asyncio
async def testAnUnrestrictedDelegationStillSettles(
    agentKeyFixtures: Dict[str, Any],
    mockRedisClient: Any,
) -> None:
    """An empty whitelist is 'no category restriction', not 'no category permitted'.

    Reading it the other way would break every delegation that omits the field -- which is the
    default in both SDKs -- and would be a far louder failure than the one being fixed.
    """
    currentTime = int(time.time())
    _, intentMandate, cartMandate, executionMandate = _buildMandates(
        agentKeyFixtures, [], currentTime
    )
    orchestrator = setupIntegrationOrchestrator(mockRedisClient=mockRedisClient)

    result = await orchestrator.executeSettlementSaga(
        intentMandate=intentMandate, cartMandate=cartMandate,
        executionMandate=executionMandate, merchantAccount=defaultMerchantAccount,
        paymentId="pay_category_open_001", serverTime=currentTime,
    )
    assert result is not None


def testCategoriesAreReadFromTheSignedCartNotTheCaller(
    agentKeyFixtures: Dict[str, Any],
) -> None:
    """The list handed to the gate is derived from the cart the merchant signed.

    A buyer-supplied category list would be a constraint written by the constrained party.
    """
    currentTime = int(time.time())
    _, _, cartMandate, _ = _buildMandates(agentKeyFixtures, [defaultCategory], currentTime)
    assert _signedCartCategories(cartMandate) == [item.category for item in cartMandate.items]
    assert _signedCartCategories(cartMandate) == [defaultCategory]


@pytest.mark.asyncio
async def testAnUnclassifiedCartCannotSatisfyARestrictedDelegation(
    agentKeyFixtures: Dict[str, Any],
    mockRedisClient: Any,
) -> None:
    """The schema sentinel is unproven, not permitted.

    `category` carries a default so the JCS payload always holds the key and the two SDKs
    canonicalize identically. A default that also silently satisfied the whitelist would have
    reintroduced the original hole through the back door.
    """
    currentTime = int(time.time())
    signers, intentMandate, cartMandate, _ = _buildMandates(
        agentKeyFixtures, [defaultCategory], currentTime
    )
    unclassifiedItems = [
        item.model_copy(update={"category": uncategorizedCartItemCategory})
        for item in cartMandate.items
    ]
    unclassifiedCart = cartMandate.model_copy(update={"items": unclassifiedItems})

    # Re-signed by the merchant, so this fails on the category rather than on a signature the
    # edit invalidated -- otherwise the test would pass for the wrong reason.
    unsignedPayload = {
        key: value
        for key, value in unclassifiedCart.model_dump().items()
        if key != "merchantSignature"
    }
    resignedCart = unclassifiedCart.model_copy(
        update={
            "merchantSignature": signers.merchantSigner.signCanonicalBytes(
                canonicalizeJson(unsignedPayload)
            )
        }
    )
    executionMandate = buildStandardExecutionMandate(
        signers.buyerSigner, intentMandate, resignedCart, resignedCart.totalPaise, currentTime,
    )
    orchestrator = setupIntegrationOrchestrator(mockRedisClient=mockRedisClient)

    with pytest.raises(CategoryNotAuthorizedException) as excInfo:
        await orchestrator.executeSettlementSaga(
            intentMandate=intentMandate, cartMandate=resignedCart,
            executionMandate=executionMandate, merchantAccount=defaultMerchantAccount,
            paymentId="pay_category_unclassified_001", serverTime=currentTime,
        )
    assert uncategorizedCartItemCategory in str(excInfo.value)
