"""Runs the Python buyer SDK's escrow client against the REAL x402 gateway app.

Why this file exists: every other test of these three methods mocks the transport. A
`MockTransport` answers whatever it is asked, so `createEscrowSession` and `releaseEscrow` passed
a fully green suite while being unable to complete a single real call:

  * the route answers 201 Created and the client accepted only 200, so SUCCESS raised;
  * the client sent a `currency` key to a model declared `extra="forbid"`, a 422;
  * the client posted the session token in the body, but the route reads it from the
    X-Mesh-Escrow-Token header and declares no body model at all -- another 422.

Three bugs, one root cause: nothing ever put the client and the route in the same process. So
this mounts the actual FastAPI app on an ASGI transport rather than asserting against a mock.
The suite that covers the gateway's own rules is tests/testX402Gateway.py; what is under test
here is only the SDK's half of the contract.
"""

import httpx
import pytest

from razoragentMesh.packages.buyerSdkPy.razoragent_buyer_sdk.models import MeshSlaConfig
from razoragentMesh.packages.buyerSdkPy.razoragent_buyer_sdk.razorAgentClient import (
    RazorAgentClient,
)
from razoragentMesh.packages.x402Gateway.src.gatewayApp import createGatewayApp

# Any host resolves: ASGITransport dispatches in-process and never opens a socket. Naming it
# after the service keeps a failure message readable.
gatewayTestBaseUrl = "http://x402-gateway.test"
testInitialHoldPaise = 5000


def _buildSdkClientBoundToGateway() -> RazorAgentClient:
    """Builds an SDK client whose HTTP calls land on the real gateway app, in process."""
    transport = httpx.ASGITransport(app=createGatewayApp())
    httpClient = httpx.AsyncClient(transport=transport, base_url=gatewayTestBaseUrl)
    config = MeshSlaConfig(x402GatewayBaseUrl=gatewayTestBaseUrl)
    return RazorAgentClient(config=config, httpClient=httpClient)


@pytest.mark.asyncio
async def testCreateEscrowSessionAcceptsTheRoutesCreatedStatus() -> None:
    """A successful creation must not be raised as a network error."""
    client = _buildSdkClientBoundToGateway()

    session = await client.createEscrowSession(initialHoldPaise=testInitialHoldPaise)

    assert session.sessionToken
    assert session.initialHoldPaise == testInitialHoldPaise
    assert session.remainingBalancePaise == testInitialHoldPaise
    assert session.isReleased is False


@pytest.mark.asyncio
async def testCreateEscrowSessionSendsNoFieldTheRouteForbids() -> None:
    """EscrowCreateRequest is extra="forbid"; an unexpected key is a 422, not a warning."""
    client = _buildSdkClientBoundToGateway()

    # Reaching a validated EscrowSession at all proves the payload matched the model exactly:
    # a stray key would have been rejected before any session existed.
    session = await client.createEscrowSession()

    assert session.buyerAgentDid == client.getAgentDid()


@pytest.mark.asyncio
async def testReleaseEscrowSendsTheTokenAsAHeader() -> None:
    """The release route reads X-Mesh-Escrow-Token; a JSON body is a 422."""
    client = _buildSdkClientBoundToGateway()
    session = await client.createEscrowSession(initialHoldPaise=testInitialHoldPaise)

    receipt = await client.releaseEscrow(session.sessionToken)

    assert receipt.sessionToken == session.sessionToken
    # Nothing was negotiated, so the whole hold comes back. A partial refund here would mean the
    # release had been charged for turns that never ran.
    assert receipt.refundedBalancePaise == testInitialHoldPaise
    assert receipt.totalDebitedPaise == 0


@pytest.mark.asyncio
async def testEscrowRoundTripLeavesNothingHeld() -> None:
    """Create then release, which is the whole lifecycle a negotiating buyer performs."""
    client = _buildSdkClientBoundToGateway()

    session = await client.createEscrowSession(initialHoldPaise=testInitialHoldPaise)
    receipt = await client.releaseEscrow(session.sessionToken)

    assert receipt.totalDebitedPaise + receipt.refundedBalancePaise == testInitialHoldPaise


@pytest.mark.asyncio
async def testGetPowChallengeReturnsASolvableChallenge() -> None:
    """The third method on this surface, checked against the real route for the same reason."""
    client = _buildSdkClientBoundToGateway()

    challenge = await client.getPowChallenge()

    assert challenge.challengeToken
    assert challenge.powDifficultyZeros > 0
