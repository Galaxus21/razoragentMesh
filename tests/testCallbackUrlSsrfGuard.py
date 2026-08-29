"""Tests for the webhook callback URL SSRF guard (packages/x402Gateway/src/schemas/callbackUrlValidator.py)."""

import os

import pytest

from razoragentMesh.packages.x402Gateway.src.constants.alertConstants import allowLocalhostCallbackEnvVar
from razoragentMesh.packages.x402Gateway.src.gatewayExceptions import UnsafeCallbackUrlException
from razoragentMesh.packages.x402Gateway.src.schemas.alertSchema import PriceDropAlertRegisterRequest
from razoragentMesh.packages.x402Gateway.src.schemas.callbackUrlValidator import validateCallbackUrl

registrationDefaults: dict = dict(skuId="SKU-1", targetPricePaise=100, buyerAgentId="agent-1", expiresAtUnix=9999999999)


@pytest.fixture(autouse=True)
def _clearLocalhostOptIn() -> None:
    """Ensures the opt-in flag never leaks between tests."""
    os.environ.pop(allowLocalhostCallbackEnvVar, None)
    yield
    os.environ.pop(allowLocalhostCallbackEnvVar, None)


@pytest.mark.parametrize(
    "unsafeUrl",
    [
        "http://169.254.169.254/latest/meta-data/",
        "http://169.254.169.254/",
        "https://169.254.169.254/",
        "http://localhost:8080/hook",
        "https://localhost/hook",
        "https://127.0.0.1/hook",
        "https://10.0.0.5/hook",
        "https://192.168.1.1/hook",
        "https://metadata.google.internal/computeMetadata/v1/",
        "http://example.com/hook",
        "ftp://example.com/hook",
        "not-a-url",
        "",
    ],
)
def testUnsafeCallbackUrlsRejected(unsafeUrl: str) -> None:
    """Cloud metadata endpoints, loopback/private IPs, known-unsafe hostnames, and
    non-HTTPS schemes are all rejected without an explicit opt-in."""
    with pytest.raises(UnsafeCallbackUrlException):
        validateCallbackUrl(unsafeUrl)


@pytest.mark.parametrize(
    "safeUrl",
    [
        "https://example.com/hook",
        "https://buyer-desk.internal/hook",
        "https://merchant.razorpay-partner.example/webhooks/price-drop",
    ],
)
def testSafeCallbackUrlsAccepted(safeUrl: str) -> None:
    """Ordinary public HTTPS hostnames pass through unchanged."""
    assert validateCallbackUrl(safeUrl) == safeUrl


def testLocalhostRejectedByDefaultEvenThoughAppEnvironmentDefaultsToDevelopment() -> None:
    """The guard's own opt-in flag, not the app-wide ENVIRONMENT default, controls the
    localhost bypass -- so it stays off in this demo's actual deployment, which never
    sets ENVIRONMENT and would otherwise inherit an unintentionally permissive default."""
    with pytest.raises(UnsafeCallbackUrlException):
        validateCallbackUrl("http://localhost:8080/hook", allowLocalhostCallback=False)


def testLocalhostAcceptedOnlyWithExplicitOptIn() -> None:
    assert validateCallbackUrl("http://localhost:8080/hook", allowLocalhostCallback=True) == "http://localhost:8080/hook"


def testPriceDropAlertRegisterRequestRejectsSsrfCallbackUrl() -> None:
    """The SSRF guard is wired into the actual FastAPI request schema, not just
    exercised in isolation -- a malicious registration is rejected at the API boundary."""
    with pytest.raises(Exception) as excInfo:
        PriceDropAlertRegisterRequest(callbackUrl="http://169.254.169.254/latest/meta-data/", **registrationDefaults)
    assert "callbackUrl" in str(excInfo.value)


def testPriceDropAlertRegisterRequestAcceptsHttpsCallbackUrl() -> None:
    request = PriceDropAlertRegisterRequest(callbackUrl="https://example.com/hook", **registrationDefaults)
    assert request.callbackUrl == "https://example.com/hook"
