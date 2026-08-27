"""Unit tests for x402Gateway dependency injection providers and overrides."""

import pytest
from unittest.mock import MagicMock
from httpx import ASGITransport, AsyncClient

from razoragentMesh.packages.x402Gateway.src.dependencies import (
    AntiSpamSybilShield,
    EscrowClient,
    defaultAlertManager,
    defaultAntiSpamShield,
    defaultEscrowClient,
    getAlertManager,
    getAntiSpamShield,
    getEscrowClient,
    getGatewayRedisClient,
)
from razoragentMesh.packages.x402Gateway.src.gatewayApp import app


@pytest.mark.asyncio
async def testDefaultProvidersReturnSingletons() -> None:
    """Verifies that default providers return module-level singletons when app state is empty."""
    escrowClient = await getEscrowClient()
    alertManager = await getAlertManager()
    antiSpamShield = await getAntiSpamShield()

    assert escrowClient is defaultEscrowClient
    assert alertManager is defaultAlertManager
    assert antiSpamShield is defaultAntiSpamShield


@pytest.mark.asyncio
async def testAppStateOverridesProviders() -> None:
    """Verifies that app.state provides instances when available on request."""
    mockRequest = MagicMock()
    mockRedis = MagicMock()
    mockEscrow = MagicMock(spec=EscrowClient)
    mockAlerts = MagicMock()
    mockShield = MagicMock(spec=AntiSpamSybilShield)

    mockRequest.app.state.redis = mockRedis
    mockRequest.app.state.escrowClient = mockEscrow
    mockRequest.app.state.alertManager = mockAlerts
    mockRequest.app.state.antiSpamShield = mockShield

    assert await getGatewayRedisClient(mockRequest) is mockRedis
    assert await getEscrowClient(mockRequest) is mockEscrow
    assert await getAlertManager(mockRequest) is mockAlerts
    assert await getAntiSpamShield(mockRequest) is mockShield


@pytest.mark.asyncio
async def testFastApiDependencyOverrideEscrowRoute() -> None:
    """Verifies that FastAPI dependency_overrides work seamlessly on escrow routes."""
    mockEscrow = MagicMock()
    mockSession = MagicMock()
    mockSession.sessionToken = "esc_custom_test_token"
    mockSession.initialHoldPaise = 7500
    mockSession.remainingBalancePaise = 7500
    mockSession.debitedTotalPaise = 0
    mockSession.buyerAgentDid = "did:agent:custom_buyer"
    mockSession.expiresAtUnix = 1800000000

    async def mockCreateEscrowSession(buyerAgentDid: str, initialHoldPaise: int = 5000):
        return mockSession

    mockEscrow.createEscrowSession = mockCreateEscrowSession

    app.dependency_overrides[getEscrowClient] = lambda: mockEscrow
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post(
                "/api/v1/mesh/escrow",
                json={"buyerAgentDid": "did:agent:custom_buyer", "initialHoldPaise": 7500},
            )
            assert resp.status_code == 201
            assert resp.json()["sessionToken"] == "esc_custom_test_token"
    finally:
        app.dependency_overrides.pop(getEscrowClient, None)


@pytest.mark.asyncio
async def testFastApiDependencyOverrideAlertsRoute() -> None:
    """Verifies that FastAPI dependency_overrides work seamlessly on alerts routes."""
    mockAlertManager = MagicMock()
    mockAlert = MagicMock()
    mockAlert.alertId = "alert_mock_999"
    mockAlert.skuId = "SKU-OVERRIDE-01"
    mockAlert.targetPricePaise = 250000
    mockAlert.callbackUrl = "https://example.com/callback"
    mockAlert.buyerAgentId = "did:agent:buyer_mock"
    mockAlert.expiresAtUnix = 1900000000
    mockAlert.createdAtUnix = 1700000000
    mockAlert.status = "active"

    async def mockRegister(**kwargs):
        return mockAlert

    mockAlertManager.registerPriceDropAlert = mockRegister

    app.dependency_overrides[getAlertManager] = lambda: mockAlertManager
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post(
                "/api/v1/alerts/price-drop",
                json={
                    "skuId": "SKU-OVERRIDE-01",
                    "targetPricePaise": 250000,
                    "callbackUrl": "https://example.com/callback",
                    "buyerAgentId": "did:agent:buyer_mock",
                    "expiresAtUnix": 1900000000,
                },
            )
            assert resp.status_code == 201
            assert resp.json()["alertId"] == "alert_mock_999"
    finally:
        app.dependency_overrides.pop(getAlertManager, None)
