"""Pins the bound on the client-supplied `serverTime` clock override.

`serverTime` rides on the unsigned outer envelope of /api/v1/settlement/execute -- outside all
three mandate signatures -- and is threaded into every expiry decision the saga makes: mandate
validity (budgetGate), inventory-lock expiry (twoPhaseCommitSaga), the nonce ledger's own NTP
drift window, cumulative-spend expiry (settlementLedger), and the date stamped on the GSTR-1 tax
invoice (gstrInvoiceEngine).

Unbounded, that is a clock the caller owns: `serverTime=0` settles an expired delegation and
back-dates a statutory invoice, and no signature is broken doing it. Only the MCP
`execute_settlement` tool ever closed the hole, by hardcoding real time and never exposing the
field; the HTTP surface and both buyer SDKs passed it straight through.

These tests run with the seam explicitly OFF. The rest of the suite enables it -- see the
`allowClientServerTimeForDeterminism` fixture in conftest.py -- because several settlement tests
legitimately need a fixed clock.
"""

import os
import time
from typing import Any, Iterator

import pytest
from fastapi.testclient import TestClient

from razoragentMesh.packages.mandateEngine.mandateApp import createMandateApp
from razoragentMesh.tests.testMandateAppSettlementRoutes import (
    _buildTestMandateTriplet,
    testMerchantAccountId,
)

# Values a caller would reach for. Epoch zero is the cheapest way to make every expiry check pass.
epochZero: int = 0
farFutureUnixSeconds: int = 4102444800  # 2100-01-01
staleButPlausibleUnixSeconds: int = 1700000000  # 2023-11-14


@pytest.fixture()
def clockOverrideRefused() -> Iterator[None]:
    """Turns the documented test seam off, restoring whatever the session fixture set."""
    previousValue = os.environ.get("ALLOW_CLIENT_SERVER_TIME")
    os.environ.pop("ALLOW_CLIENT_SERVER_TIME", None)
    yield
    if previousValue is not None:
        os.environ["ALLOW_CLIENT_SERVER_TIME"] = previousValue


def _settlementBody(serverTime: Any, paymentId: str) -> dict:
    """Builds a fully signed, otherwise-valid settlement request."""
    intentMandate, cartMandate, executionMandate = _buildTestMandateTriplet()[:3]
    body = {
        "intentMandate": intentMandate.model_dump(),
        "cartMandate": cartMandate.model_dump(),
        "executionMandate": executionMandate.model_dump(),
        "merchantAccount": testMerchantAccountId,
        "paymentId": paymentId,
    }
    if serverTime is not None:
        body["serverTime"] = serverTime
    return body


@pytest.mark.parametrize(
    "spoofedServerTime,label",
    [
        (epochZero, "epoch zero"),
        (farFutureUnixSeconds, "year 2100"),
        (staleButPlausibleUnixSeconds, "two years stale"),
    ],
)
def testSettlementRefusesAClockTheCallerControls(
    clockOverrideRefused: None, spoofedServerTime: int, label: str
) -> None:
    """A serverTime far from the real clock is refused before the saga runs.

    The refusal must arrive as a 4xx naming the field, not as a downstream expiry error: the
    caller supplied something inadmissible, rather than a valid request that failed a check.
    """
    client = TestClient(createMandateApp(), raise_server_exceptions=False)
    response = client.post(
        "/api/v1/settlement/execute",
        json=_settlementBody(spoofedServerTime, f"pay_spoof_{spoofedServerTime}"),
    )
    assert response.status_code == 400, (
        f"{label} serverTime was accepted with status {response.status_code}; "
        "an unbounded clock override settles expired mandates"
    )
    assert "serverTime" in str(response.json()["detail"])


def testSettlementAcceptsAServerTimeNearTheRealClock(clockOverrideRefused: None) -> None:
    """Honest clock skew still works -- the bound is the NTP drift window, not equality.

    Without this the guard could be 'reject every serverTime', which would pass the tests above
    while breaking every legitimate caller whose clock is a second out.
    """
    client = TestClient(createMandateApp(), raise_server_exceptions=False)
    response = client.post(
        "/api/v1/settlement/execute",
        json=_settlementBody(int(time.time()) + 1, "pay_honest_clock"),
    )
    # The chain itself is stale by design (its mandates are pinned to 2023), so this gets past the
    # clock gate and is refused further in. What matters is that it is NOT the 400 above.
    assert response.status_code != 400 or "serverTime" not in str(response.json().get("detail", ""))


def testOmittingServerTimeIsAlwaysAllowed(clockOverrideRefused: None) -> None:
    """The field is optional; omitting it means 'use the server's own clock'."""
    client = TestClient(createMandateApp(), raise_server_exceptions=False)
    response = client.post(
        "/api/v1/settlement/execute", json=_settlementBody(None, "pay_no_server_time")
    )
    detail = str(response.json().get("detail", ""))
    assert "serverTime" not in detail, f"omitting serverTime was rejected: {detail}"


def testTheSeamIsOffByDefault(clockOverrideRefused: None) -> None:
    """The permissive mode must require an explicit opt-in, never a default.

    A guard whose default is 'allow' is not a guard. This pins the direction of the default so a
    later refactor cannot invert it quietly.
    """
    from razoragentMesh.packages.mandateEngine.config import getMandateEngineSettings

    assert getMandateEngineSettings().allowUnboundedClientServerTime is False
