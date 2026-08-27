"""Integration tests for fault recovery, AP2 budget breaches, tampering, and saga rollbacks."""

import time
from typing import Any, Dict
import pytest

from razoragentMesh.packages.mandateEngine.mandates.mandateFactory import (
    createSignedIntentMandate,
)
from razoragentMesh.packages.mandateEngine.settlement.settlementExceptions import (
    BudgetExceededViolation,
    MandateHashChainMismatchException,
    NonceReplayException,
    SettlementCompensationTriggeredException,
)
from razoragentMesh.packages.mandateEngine.settlement.splitManifestBuilder import (
    defaultProtocolFeeAccount,
)
from razoragentMesh.packages.mandateEngine.verification.budgetGate import validateBudgetGate
from razoragentMesh.packages.mandateEngine.verification.signatureChainVerifier import (
    verifyMandateChain,
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

depletedSkuStock: int = 3
excessiveRequestedQuantity: int = 10
strictBudgetPaise: int = 2000000
tamperAmountDeltaPaise: int = 50000


@pytest.mark.asyncio
async def testInventoryLockDepletionFaultRecovery(
    agentKeyFixtures: Dict[str, Any],
    mockRedisClient: Any,
) -> None:
    """Verifies that inventory depletion returns -1 and prevents cart mandate creation."""
    depletedSkuId = "SKU-DEPLETED-001"
    stockKey = f"sku:{depletedSkuId}:stock"
    fencingKey = f"sku:{depletedSkuId}:fence"
    mockRedisClient.store[stockKey] = depletedSkuStock

    lockStatus, availableStock = await mockRedisClient.eval(
        "", 2, stockKey, fencingKey, excessiveRequestedQuantity, defaultLockToken, 60
    )

    assert lockStatus == -1
    assert availableStock == depletedSkuStock
    assert mockRedisClient.store[stockKey] == depletedSkuStock


@pytest.mark.asyncio
async def testBudgetGateBreachFaultRecovery(
    agentKeyFixtures: Dict[str, Any],
    mockRedisClient: Any,
) -> None:
    """Verifies that AP2 budget gate aborts execution when cart total exceeds maxBudget."""
    signers = setupIntegrationSigners(agentKeyFixtures)
    currentTime = int(time.time())

    intentMandate = createSignedIntentMandate(
        mandateId="intent_breach_001", userSigner=signers.userSigner,
        delegatedAgentDid=signers.buyerSigner.getAgentDid(), maxBudgetPaise=strictBudgetPaise,
        upiCircleDelegationToken=defaultUpiToken, singleTransactionLimitPaise=strictBudgetPaise,
        authorizedCategories=[defaultCategory], timestamp=currentTime,
    )
    cartMandate, totalGrossPaise = buildStandardCartMandate(signers, defaultLockToken, currentTime)
    executionMandate = buildStandardExecutionMandate(
        signers.buyerSigner, intentMandate, cartMandate, totalGrossPaise, currentTime,
    )

    with pytest.raises(BudgetExceededViolation) as excInfo:
        validateBudgetGate(intentMandate, cartMandate, executionMandate, currentTime)
    assert "exceeds delegated budget" in str(excInfo.value)


@pytest.mark.asyncio
async def testMandateHashChainTamperingFaultRecovery(
    agentKeyFixtures: Dict[str, Any],
    mockRedisClient: Any,
) -> None:
    """Verifies that tampering with cart mandate fields causes hash chain rejection."""
    signers = setupIntegrationSigners(agentKeyFixtures)
    currentTime = int(time.time())

    intentMandate = createSignedIntentMandate(
        mandateId="intent_tamper_001", userSigner=signers.userSigner,
        delegatedAgentDid=signers.buyerSigner.getAgentDid(), maxBudgetPaise=5000000,
        upiCircleDelegationToken=defaultUpiToken, singleTransactionLimitPaise=5000000,
        authorizedCategories=[defaultCategory], timestamp=currentTime,
    )
    cartMandate, totalGrossPaise = buildStandardCartMandate(signers, defaultLockToken, currentTime)
    executionMandate = buildStandardExecutionMandate(
        signers.buyerSigner, intentMandate, cartMandate, totalGrossPaise, currentTime,
    )

    tamperedCart = cartMandate.model_copy(update={"totalPaise": totalGrossPaise + tamperAmountDeltaPaise})
    with pytest.raises(MandateHashChainMismatchException) as excInfo:
        verifyMandateChain(intentMandate, tamperedCart, executionMandate)
    assert "Cart mandate hash mismatch" in str(excInfo.value)


@pytest.mark.asyncio
async def testSettlementSagaRollbackFaultRecovery(
    agentKeyFixtures: Dict[str, Any],
    mockRedisClient: Any,
) -> None:
    """Verifies 2PC rollback compensation when a secondary split transfer fails."""
    signers = setupIntegrationSigners(agentKeyFixtures)
    currentTime = int(time.time())

    intentMandate = createSignedIntentMandate(
        mandateId="intent_rollback_001", userSigner=signers.userSigner,
        delegatedAgentDid=signers.buyerSigner.getAgentDid(), maxBudgetPaise=5000000,
        upiCircleDelegationToken=defaultUpiToken, singleTransactionLimitPaise=5000000,
        authorizedCategories=[defaultCategory], timestamp=currentTime,
    )
    cartMandate, totalGrossPaise = buildStandardCartMandate(signers, defaultLockToken, currentTime)
    executionMandate = buildStandardExecutionMandate(
        signers.buyerSigner, intentMandate, cartMandate, totalGrossPaise, currentTime,
    )

    orchestrator = setupIntegrationOrchestrator(
        mockRedisClient=mockRedisClient, simulatedFailureAccount=defaultProtocolFeeAccount,
    )

    with pytest.raises(SettlementCompensationTriggeredException) as excInfo:
        await orchestrator.executeSettlementSaga(
            intentMandate=intentMandate, cartMandate=cartMandate,
            executionMandate=executionMandate, merchantAccount=defaultMerchantAccount,
            paymentId="pay_rollback_001", serverTime=currentTime,
        )
    assert "2PC Transfer failed: triggered rollback" in str(excInfo.value)


@pytest.mark.asyncio
async def testNonceReplaySettlementFaultRecovery(
    agentKeyFixtures: Dict[str, Any],
    mockRedisClient: Any,
) -> None:
    """Verifies that reusing an already committed execution mandate nonce raises 409 NonceReplayException."""
    signers = setupIntegrationSigners(agentKeyFixtures)
    currentTime = int(time.time())

    intentMandate = createSignedIntentMandate(
        mandateId="intent_replay_001", userSigner=signers.userSigner,
        delegatedAgentDid=signers.buyerSigner.getAgentDid(), maxBudgetPaise=5000000,
        upiCircleDelegationToken=defaultUpiToken, singleTransactionLimitPaise=5000000,
        authorizedCategories=[defaultCategory], timestamp=currentTime,
    )
    cartMandate, totalGrossPaise = buildStandardCartMandate(signers, defaultLockToken, currentTime)
    executionMandate = buildStandardExecutionMandate(
        signers.buyerSigner, intentMandate, cartMandate, totalGrossPaise, currentTime,
    )

    orchestrator = setupIntegrationOrchestrator(mockRedisClient)
    result = await orchestrator.executeSettlementSaga(
        intentMandate=intentMandate, cartMandate=cartMandate,
        executionMandate=executionMandate, merchantAccount=defaultMerchantAccount,
        paymentId="pay_replay_first_001", serverTime=currentTime,
    )
    assert result.status == "captured"

    with pytest.raises(NonceReplayException) as excInfo:
        await orchestrator.executeSettlementSaga(
            intentMandate=intentMandate, cartMandate=cartMandate,
            executionMandate=executionMandate, merchantAccount=defaultMerchantAccount,
            paymentId="pay_replay_second_001", serverTime=currentTime,
        )
    assert "Replay attack detected" in str(excInfo.value)
