"""Chooses the Route transport the deployment's credentials actually permit.

Both service entry points used to construct `RazorpayRouteClient(isMockMode=True)`
literally, so every settlement the system had ever performed went through the mock
ledger no matter what was in the environment. The decision now lives in one place and
is driven by configuration, so supplying Razorpay Test Mode credentials is sufficient
to exercise the live transport, and supplying nothing keeps the deterministic ledger.

The fallback direction is deliberate. Absent or placeholder credentials select the
mock, because a settlement that silently posts nowhere is worse than one that says it
is mocked -- and the mode is logged at construction either way, so which transport ran
is never a matter of inference.
"""

import logging

from ..config import MandateEngineSettings, defaultMandateSettings
from .razorpayRouteClient import RazorpayRouteClient

logger = logging.getLogger(__name__)

liveTransportMessage: str = (
    "Razorpay Route: LIVE transport selected (key id %s); settlements will reach the API"
)
mockTransportMessage: str = (
    "Razorpay Route: MOCK ledger selected; no settlement will reach the Razorpay API. "
    "Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET to use Test Mode."
)


def buildRouteClient(
    settings: MandateEngineSettings = defaultMandateSettings,
) -> RazorpayRouteClient:
    """Builds a Route client bound to live credentials when they are present."""
    if not settings.hasRazorpayCredentials:
        logger.warning(mockTransportMessage)
        return RazorpayRouteClient(isMockMode=True)

    logger.info(liveTransportMessage, settings.razorpayKeyId)
    return RazorpayRouteClient(
        apiKey=settings.razorpayKeyId,
        apiSecret=settings.razorpayKeySecret,
        isMockMode=False,
    )


__all__ = ["buildRouteClient"]
