"""Comprehensive E2E automated test suite for 3-Step Smart Wait & Temporal Deferred Execution."""

import json
import time
from typing import List, Optional
from unittest.mock import AsyncMock, patch
from httpx import Response
from pydantic import BaseModel, ConfigDict, Field
import pytest

from razoragentMesh.packages.mandateEngine.settlement.webhookVerifier import (
    verifyRazorpayWebhookSignature,
)
from razoragentMesh.packages.mandateEngine.verification.arithmeticEnclave import (
    validateIntegerPaise,
)
from razoragentMesh.packages.merchantApi.src.schemas.universalProductSchema import (
    ScheduledPromotionSchema,
    UniversalProductListing,
)
from razoragentMesh.packages.x402Gateway.src.alerts.priceDropAlertManager import (
    PriceDropAlertManager,
)
from razoragentMesh.tests.mockInfraHelpers import MockRedisAsync

# Domain Constants in strict camelCase
defaultBasisPointsDivisor: int = 10000
defaultMinSavingsThresholdPaise: int = 50000
testChairSkuId: str = "SKU-CHAIR-001"
testChairBasePricePaise: int = 420000
testTargetPricePaise: int = 350000
testBuyerAgentDid: str = "did:mesh:buyer_alpha"
testWebhookCallbackUrl: str = "https://buyer-agent.mesh/api/v1/webhook"
testWebhookSecret: str = "whsec_test_secret_alpha_99"
secondsPerHour: int = 3600
secondsPerDay: int = 86400
zeroPaise: int = 0


class AgentUrgencyDecision(BaseModel):
    """Decision outcome of the autonomous buyer agent urgency vs savings matrix."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    shouldDefer: bool
    waitSeconds: int = Field(ge=0)
    projectedPricePaise: int = Field(ge=0)
    projectedSavingsPaise: int = Field(ge=0)
    reason: str


class EvaluatedPromotion(BaseModel):
    """Normalized scheduled promotion evaluation result."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    campaignId: str
    name: str
    startsAtUnix: int
    endsAtUnix: int
    expectedUnitPricePaise: int = Field(ge=0)
    expectedSavingsPaise: int = Field(ge=0)
    limitedStockAllocated: Optional[int] = Field(default=None, ge=0)


class TemporalQuoteEvaluation(BaseModel):
    """Container for active and upcoming promotion partitions with offered unit price."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    offeredUnitPricePaise: int = Field(ge=0)
    activePromotions: List[EvaluatedPromotion]
    upcomingPromotions: List[EvaluatedPromotion]


def calculatePromotionPrice(baseUnitPricePaise: int, promo: ScheduledPromotionSchema) -> int:
    """Calculates deterministic promotion unit price in integer paise with zero float drift."""
    validateIntegerPaise(baseUnitPricePaise, "baseUnitPricePaise")
    if promo.fixedPricePaise is not None:
        return promo.fixedPricePaise
    if promo.discountBps is not None:
        discountPaise = (baseUnitPricePaise * promo.discountBps) // defaultBasisPointsDivisor
        return baseUnitPricePaise - discountPaise
    if promo.discountPaise is not None:
        return max(zeroPaise, baseUnitPricePaise - promo.discountPaise)
    return baseUnitPricePaise


def evaluateTemporalPromotions(
    baseUnitPricePaise: int, promotions: List[ScheduledPromotionSchema], currentTimeUnix: int,
) -> TemporalQuoteEvaluation:
    """Partitions promotions into active vs upcoming and derives dynamic offered price."""
    validateIntegerPaise(baseUnitPricePaise, "baseUnitPricePaise")
    validateIntegerPaise(currentTimeUnix, "currentTimeUnix")
    activeList: List[EvaluatedPromotion] = []
    upcomingList: List[EvaluatedPromotion] = []

    for promo in promotions:
        expectedUnit = calculatePromotionPrice(baseUnitPricePaise, promo)
        expectedSavings = baseUnitPricePaise - expectedUnit
        if expectedSavings < zeroPaise:
            raise ValueError(f"Negative savings for campaign {promo.campaignId}")
        evaluated = EvaluatedPromotion(
            campaignId=promo.campaignId, name=promo.name, startsAtUnix=promo.startsAtUnix,
            endsAtUnix=promo.endsAtUnix, expectedUnitPricePaise=expectedUnit,
            expectedSavingsPaise=expectedSavings, limitedStockAllocated=promo.limitedStockAllocated,
        )
        if promo.startsAtUnix <= currentTimeUnix < promo.endsAtUnix:
            activeList.append(evaluated)
        elif promo.startsAtUnix > currentTimeUnix:
            upcomingList.append(evaluated)

    bestOffered = min([p.expectedUnitPricePaise for p in activeList]) if activeList else baseUnitPricePaise
    return TemporalQuoteEvaluation(
        offeredUnitPricePaise=bestOffered, activePromotions=activeList, upcomingPromotions=upcomingList,
    )


def evaluateAgentUrgencyDecision(
    currentPricePaise: int, upcomingPromotions: List[ScheduledPromotionSchema],
    currentTimeUnix: int, deliveryDeadlineUnix: int, deliveryDurationSeconds: int,
    minSavingsThresholdPaise: int = defaultMinSavingsThresholdPaise,
) -> AgentUrgencyDecision:
    """Evaluates agent urgency constraints vs projected savings to determine purchase deferral."""
    validateIntegerPaise(currentPricePaise, "currentPricePaise")
    if not upcomingPromotions:
        return AgentUrgencyDecision(
            shouldDefer=False, waitSeconds=0, projectedPricePaise=currentPricePaise,
            projectedSavingsPaise=0, reason="NO_UPCOMING_PROMOTIONS",
        )
    bestPromo = max(upcomingPromotions, key=lambda p: currentPricePaise - calculatePromotionPrice(currentPricePaise, p))
    bestSavings = currentPricePaise - calculatePromotionPrice(currentPricePaise, bestPromo)
    if bestSavings <= 0:
        return AgentUrgencyDecision(
            shouldDefer=False, waitSeconds=0, projectedPricePaise=currentPricePaise,
            projectedSavingsPaise=0, reason="ZERO_SAVINGS",
        )
    if bestPromo.startsAtUnix + deliveryDurationSeconds > deliveryDeadlineUnix:
        return AgentUrgencyDecision(
            shouldDefer=False, waitSeconds=0, projectedPricePaise=currentPricePaise,
            projectedSavingsPaise=0, reason="DELIVERY_DEADLINE_BREACH",
        )
    if bestSavings < minSavingsThresholdPaise:
        return AgentUrgencyDecision(
            shouldDefer=False, waitSeconds=0, projectedPricePaise=currentPricePaise,
            projectedSavingsPaise=bestSavings, reason="SAVINGS_BELOW_THRESHOLD",
        )
    return AgentUrgencyDecision(
        shouldDefer=True, waitSeconds=max(0, bestPromo.startsAtUnix - currentTimeUnix),
        projectedPricePaise=currentPricePaise - bestSavings, projectedSavingsPaise=bestSavings,
        reason="DEFERRED_FOR_SAVINGS",
    )


def testUpcomingPromotionsSignaledInQuote() -> None:
    """1. Evaluates upcoming promotion signaling with exact integer paise savings and invariants."""
    now = int(time.time())
    promo30Pct = ScheduledPromotionSchema(
        campaignId="CAMP-DIWALI-30", name="Diwali Mega Flash Sale",
        startsAtUnix=now + (3 * secondsPerHour), endsAtUnix=now + (27 * secondsPerHour),
        discountBps=3000, limitedStockAllocated=50,
    )
    promoFixed = ScheduledPromotionSchema(
        campaignId="CAMP-FIXED-3500", name="Fixed ₹3,500 Deal",
        startsAtUnix=now + (3 * secondsPerHour), endsAtUnix=now + (27 * secondsPerHour),
        fixedPricePaise=350000,
    )
    listing = UniversalProductListing(
        skuId=testChairSkuId, merchantDid="did:mesh:merchant_nexus_01",
        title="Ergonomic Executive Mesh Chair", description="High durability task chair",
        category="office_furniture", hsnCode="9401", gstRatePercent=18,
        baseUnitPricePaise=testChairBasePricePaise, availableStock=100,
        originPincode="560001", promotions=[promo30Pct, promoFixed],
    )
    evaluated = evaluateTemporalPromotions(listing.baseUnitPricePaise, listing.promotions, currentTimeUnix=now)
    assert len(evaluated.activePromotions) == 0 and len(evaluated.upcomingPromotions) == 2
    assert evaluated.offeredUnitPricePaise == testChairBasePricePaise

    eval30 = next(p for p in evaluated.upcomingPromotions if p.campaignId == "CAMP-DIWALI-30")
    assert eval30.expectedUnitPricePaise == 294000 and eval30.expectedSavingsPaise == 126000
    assert eval30.expectedSavingsPaise == listing.baseUnitPricePaise - eval30.expectedUnitPricePaise >= zeroPaise

    evalFixed = next(p for p in evaluated.upcomingPromotions if p.campaignId == "CAMP-FIXED-3500")
    assert evalFixed.expectedUnitPricePaise == 350000 and evalFixed.expectedSavingsPaise == 70000
    assert evalFixed.expectedSavingsPaise == listing.baseUnitPricePaise - evalFixed.expectedUnitPricePaise >= zeroPaise


def testAgentUrgencyDecisionMatrixUrgent() -> None:
    """2. Verifies urgent SLA constraint forces instant purchase without deferral."""
    now = 1724480000
    userDeadlineUnix = now + (4 * secondsPerHour)
    promoStartsAtUnix = now + (3 * secondsPerHour)
    deliveryDurationSeconds = 4 * secondsPerHour
    promo = ScheduledPromotionSchema(
        campaignId="CAMP-FLASH-30", name="Flash 30% Off",
        startsAtUnix=promoStartsAtUnix, endsAtUnix=promoStartsAtUnix + (24 * secondsPerHour),
        discountBps=3000,
    )
    decision = evaluateAgentUrgencyDecision(
        currentPricePaise=testChairBasePricePaise, upcomingPromotions=[promo],
        currentTimeUnix=now, deliveryDeadlineUnix=userDeadlineUnix,
        deliveryDurationSeconds=deliveryDurationSeconds,
    )
    assert decision.shouldDefer is False and decision.waitSeconds == 0
    assert decision.projectedPricePaise == testChairBasePricePaise and decision.projectedSavingsPaise == 0
    assert decision.reason == "DELIVERY_DEADLINE_BREACH"


def testAgentUrgencyDecisionMatrixFlexible() -> None:
    """3. Verifies flexible SLA allows deferral to capture promotional savings."""
    now = 1724480000
    userDeadlineUnix = now + (48 * secondsPerHour)
    promoStartsAtUnix = now + (3 * secondsPerHour)
    deliveryDurationSeconds = 4 * secondsPerHour
    promoBps = ScheduledPromotionSchema(
        campaignId="CAMP-FLASH-30", name="Flash 30% Off",
        startsAtUnix=promoStartsAtUnix, endsAtUnix=promoStartsAtUnix + (24 * secondsPerHour),
        discountBps=3000,
    )
    decision = evaluateAgentUrgencyDecision(
        currentPricePaise=testChairBasePricePaise, upcomingPromotions=[promoBps],
        currentTimeUnix=now, deliveryDeadlineUnix=userDeadlineUnix,
        deliveryDurationSeconds=deliveryDurationSeconds,
    )
    assert decision.shouldDefer is True and decision.waitSeconds == 10800
    assert decision.projectedPricePaise == 294000 and decision.projectedSavingsPaise == 126000
    assert decision.reason == "DEFERRED_FOR_SAVINGS"

    promoFixed = ScheduledPromotionSchema(
        campaignId="CAMP-FIXED-3500", name="Fixed ₹3,500 Deal",
        startsAtUnix=promoStartsAtUnix, endsAtUnix=promoStartsAtUnix + (24 * secondsPerHour),
        fixedPricePaise=350000,
    )
    decisionFixed = evaluateAgentUrgencyDecision(
        currentPricePaise=testChairBasePricePaise, upcomingPromotions=[promoFixed],
        currentTimeUnix=now, deliveryDeadlineUnix=userDeadlineUnix,
        deliveryDurationSeconds=deliveryDurationSeconds,
    )
    assert decisionFixed.shouldDefer is True and decisionFixed.waitSeconds == 10800
    assert decisionFixed.projectedPricePaise == 350000 and decisionFixed.projectedSavingsPaise == 70000


@pytest.mark.asyncio
async def testPriceDropWebhookRegistrationAndDispatch() -> None:
    """4. Verifies alert registration in Redis, TTL, HMAC-SHA256 signature dispatch, and cancellation."""
    mockRedis = MockRedisAsync()
    manager = PriceDropAlertManager(redisClient=mockRedis, webhookSecret=testWebhookSecret)
    now = int(time.time())
    expiryTimestamp = now + secondsPerDay
    alert = await manager.registerPriceDropAlert(
        skuId=testChairSkuId, targetPricePaise=testTargetPricePaise,
        callbackUrl=testWebhookCallbackUrl, buyerAgentId=testBuyerAgentDid,
        expiresAtUnix=expiryTimestamp,
    )
    assert alert.skuId == testChairSkuId and alert.targetPricePaise == 350000
    registeredAlerts = await manager.getAlertsForSku(testChairSkuId)
    assert len(registeredAlerts) == 1 and registeredAlerts[0].alertId == alert.alertId

    mockResponse = Response(status_code=200, content=b'{"status":"received"}')
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mockPost:
        mockPost.return_value = mockResponse
        results = await manager.dispatchPriceDropAlerts(skuId=testChairSkuId, activePricePaise=testTargetPricePaise)
        assert len(results) == 1 and results[0].status == "dispatched" and results[0].statusCode == 200

        mockPost.assert_called_once()
        callKwargs = mockPost.call_args.kwargs
        dispatchedContent, dispatchedHeaders = callKwargs["content"], callKwargs["headers"]
        meshSig, rzpSig = dispatchedHeaders["X-Mesh-Signature"], dispatchedHeaders["X-Razorpay-Signature"]
        assert meshSig == rzpSig
        assert verifyRazorpayWebhookSignature(dispatchedContent, rzpSig, testWebhookSecret) is True

        payloadDict = json.loads(dispatchedContent.decode("utf-8"))
        assert payloadDict["event"] == "mesh.price_drop.triggered" and payloadDict["skuId"] == testChairSkuId
        assert payloadDict["targetPricePaise"] == 350000 and payloadDict["savingsPaise"] == 0

    assert await manager.cancelPriceDropAlert(alert.alertId) is True
    assert len(await manager.getAlertsForSku(testChairSkuId)) == 0


def testTemporalQuoteTransitionActivatesAtStartsAtUnix() -> None:
    """5. Verifies seamless dynamic quote transition from upcoming to active at startsAtUnix boundary."""
    tStart, tEnd = 1724480000, 1724566400
    promo = ScheduledPromotionSchema(
        campaignId="CAMP-TRANSITION", name="Transition Flash Sale",
        startsAtUnix=tStart, endsAtUnix=tEnd, discountBps=3000,
    )
    # 1. Clock at T_start - 1 (1724479999) -> Upcoming promotion, base price offered
    evalBefore = evaluateTemporalPromotions(testChairBasePricePaise, [promo], currentTimeUnix=tStart - 1)
    assert evalBefore.offeredUnitPricePaise == testChairBasePricePaise
    assert len(evalBefore.activePromotions) == 0 and len(evalBefore.upcomingPromotions) == 1
    assert evalBefore.upcomingPromotions[0].campaignId == "CAMP-TRANSITION"

    # 2. Clock advances to T_start (1724480000) -> Active promotion, discounted price offered
    evalAtStart = evaluateTemporalPromotions(testChairBasePricePaise, [promo], currentTimeUnix=tStart)
    assert evalAtStart.offeredUnitPricePaise == 294000
    assert len(evalAtStart.activePromotions) == 1 and len(evalAtStart.upcomingPromotions) == 0
    assert evalAtStart.activePromotions[0].campaignId == "CAMP-TRANSITION"

    # 3. Clock advances past T_end (1724566401) -> Promotion expired, base price offered
    evalExpired = evaluateTemporalPromotions(testChairBasePricePaise, [promo], currentTimeUnix=tEnd + 1)
    assert evalExpired.offeredUnitPricePaise == testChairBasePricePaise
    assert len(evalExpired.activePromotions) == 0 and len(evalExpired.upcomingPromotions) == 0
