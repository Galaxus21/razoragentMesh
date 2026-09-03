"""Pins the service each client method addresses, not just the path it requests.

Every other test in this package asserts `request.url.path` against a transport mock that answers
whatever it is asked. That is why the client could send seven of its eight calls to the mandate
engine -- which serves exactly one of them -- through a fully green suite: the path was right, the
host was wrong, and nothing compared the two.

`MeshSlaConfig` declares four base URLs and the client read only `gatewayBaseUrl`. These tests
assert the pairing (method -> host) rather than either half on its own, so a regression that
re-binds one base URL fails here instead of at a judge's terminal.
"""

from typing import List, Optional, Tuple

import httpx
import pytest
from razoragent_buyer_sdk import AgentKeyManager, MeshSlaConfig, RazorAgentClient

# Distinct, obviously-fake hosts: an assertion failure then names which service was addressed
# rather than printing three variations on 127.0.0.1.
mandateEngineHost = "http://mandate-engine.test"
mcpServerHost = "http://mcp-server.test"
x402GatewayHost = "http://x402-gateway.test"
merchantApiHost = "http://merchant-api.test"

routingTestConfig = MeshSlaConfig(
    gatewayBaseUrl=mandateEngineHost,
    mcpBaseUrl=mcpServerHost,
    merchantApiBaseUrl=merchantApiHost,
    x402GatewayBaseUrl=x402GatewayHost,
)


def _recordingClient(
    responseFactory,
) -> Tuple[httpx.AsyncClient, List[httpx.Request]]:
    """Builds a transport that records every request and replies with a canned body."""
    recorded: List[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded.append(request)
        return responseFactory(request)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler)), recorded


def _origin(request: httpx.Request) -> str:
    """Returns scheme://host of a recorded request, the half the old tests never checked."""
    return f"{request.url.scheme}://{request.url.host}"


async def _captureOrigin(invoke, responseFactory) -> Tuple[str, str]:
    """Runs one client call and returns the (origin, path) it actually addressed."""
    httpClient, recorded = _recordingClient(responseFactory)
    async with httpClient:
        client = RazorAgentClient(
            config=routingTestConfig,
            keyManager=AgentKeyManager.generate(),
            httpClient=httpClient,
        )
        try:
            await invoke(client)
        except Exception:
            # The response bodies below are deliberately minimal; a parse failure after the
            # request was recorded does not affect what this test measures.
            pass
    assert recorded, "the client made no HTTP request at all"
    return _origin(recorded[0]), recorded[0].url.path


def _jsonResponse(payload: Optional[dict] = None):
    return lambda request: httpx.Response(200, json=payload if payload is not None else {})


@pytest.mark.asyncio
async def testQuoteAndLockAddressTheMcpServer() -> None:
    """/api/v1/quote and /api/v1/lock are served by the MCP server, not the mandate engine."""
    quoteOrigin, quotePath = await _captureOrigin(
        lambda client: client.getLiveSkuQuote("SKU-001", "560001"), _jsonResponse()
    )
    assert quoteOrigin == mcpServerHost, f"getLiveSkuQuote addressed {quoteOrigin}"
    assert quotePath == "/api/v1/quote"

    lockOrigin, lockPath = await _captureOrigin(
        lambda client: client.reserveInventoryLock("SKU-001", "hash"), _jsonResponse()
    )
    assert lockOrigin == mcpServerHost, f"reserveInventoryLock addressed {lockOrigin}"
    assert lockPath == "/api/v1/lock"


@pytest.mark.asyncio
async def testEscrowAndChallengeAddressTheX402Gateway() -> None:
    """The whole /api/v1/mesh/* family belongs to the x402 gateway."""
    for description, invoke, expectedPath in [
        ("getPowChallenge", lambda c: c.getPowChallenge(), "/api/v1/mesh/challenge"),
        ("createEscrowSession", lambda c: c.createEscrowSession(), "/api/v1/mesh/escrow"),
        ("releaseEscrow", lambda c: c.releaseEscrow("token"), "/api/v1/mesh/escrow/release"),
    ]:
        origin, path = await _captureOrigin(invoke, _jsonResponse())
        assert origin == x402GatewayHost, f"{description} addressed {origin}"
        assert path == expectedPath


@pytest.mark.asyncio
async def testPriceDropAlertsAddressTheX402Gateway() -> None:
    """Price-drop alerts are an x402 gateway route; the mandate engine serves no such path."""
    registerOrigin, registerPath = await _captureOrigin(
        lambda client: client.handlePriceDropAlert("SKU-001", 1000, "http://localhost/cb", 2000000000),
        _jsonResponse(),
    )
    assert registerOrigin == x402GatewayHost, f"handlePriceDropAlert addressed {registerOrigin}"
    assert registerPath == "/api/v1/alerts/price-drop"

    cancelOrigin, cancelPath = await _captureOrigin(
        lambda client: client.cancelPriceDropAlert("alert-1"), _jsonResponse()
    )
    assert cancelOrigin == x402GatewayHost, f"cancelPriceDropAlert addressed {cancelOrigin}"
    assert cancelPath == "/api/v1/alerts/price-drop/alert-1"


@pytest.mark.asyncio
async def testSettlementAddressesTheMandateEngine() -> None:
    """The one route that always was on the mandate engine must stay there."""
    from razoragent_buyer_sdk import createExecutionMandate
    from razoragent_buyer_sdk.models import CartMandate, IntentMandate

    # Built inline rather than via a fixture so this file states its own preconditions.
    keyManager = AgentKeyManager.generate()
    httpClient, recorded = _recordingClient(_jsonResponse())
    async with httpClient:
        client = RazorAgentClient(
            config=routingTestConfig, keyManager=keyManager, httpClient=httpClient
        )
        try:
            await client.executeSettlement(
                intentMandate=None,  # type: ignore[arg-type]
                cartMandate=None,  # type: ignore[arg-type]
                executionMandate=None,  # type: ignore[arg-type]
                merchantAccount="acc_test",
                paymentId="pay_test",
            )
        except Exception:
            pass

    # executeSettlement validates its mandates before sending, so a null chain never reaches the
    # transport. Assert the routing table directly instead -- the same table the client consults.
    from razoragent_buyer_sdk.constants import endpointSettlementExecute

    resolved = client._resolveUrl(endpointSettlementExecute)
    assert resolved == f"{mandateEngineHost}{endpointSettlementExecute}", resolved


@pytest.mark.asyncio
async def testEveryRoutedEndpointResolvesToADeclaredService() -> None:
    """No endpoint constant may fall through to a default host.

    The defect this guards against is not a wrong entry but a *missing* one: before this change
    an unrouted endpoint silently went to `gatewayBaseUrl`, which is how the fault stayed
    invisible. `_resolveUrl` now raises instead, and this test pins that.
    """
    from razoragent_buyer_sdk import constants

    client = RazorAgentClient(config=routingTestConfig, keyManager=AgentKeyManager.generate())
    routedEndpoints = [
        name for name in dir(constants) if name.startswith("endpoint")
    ]
    assert routedEndpoints, "no endpoint constants found to check"
    for name in routedEndpoints:
        endpoint = getattr(constants, name)
        resolved = client._resolveUrl(endpoint)
        assert resolved.startswith(("http://", "https://")), f"{name} -> {resolved}"
        assert resolved.endswith(endpoint), f"{name} lost its path: {resolved}"

    with pytest.raises(Exception):
        client._resolveUrl("/api/v1/not-a-real-route")
