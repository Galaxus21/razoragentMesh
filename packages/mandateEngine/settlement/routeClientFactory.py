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

ordersLiveMessage: str = "Razorpay Orders: LIVE test mode (key id %s); order creation will reach the API"
ordersMockMessage: str = (
    "Razorpay Orders: MOCK (set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET to use Test Mode); "
    "no order creation will reach the API"
)

routeTransfersLiveMessage: str = (
    "Razorpay Route transfers: LIVE transport selected (key id %s); split transfers will reach the API"
)
routeTransfersMockMessage: str = (
    "Razorpay Route transfers: MOCK ledger (set RAZORPAY_ROUTE_LIVE=true once Route is activated and "
    "linked accounts exist); no split transfer will reach the API"
)


def buildRouteClient(
    settings: MandateEngineSettings = defaultMandateSettings,
) -> RazorpayRouteClient:
    """Builds a Route client decoupling the Orders API from Route transfers."""
    if settings.hasRazorpayCredentials:
        logger.info(ordersLiveMessage, settings.razorpayKeyId)
    else:
        logger.warning(ordersMockMessage)

    if settings.routeTransportLive:
        logger.info(routeTransfersLiveMessage, settings.razorpayKeyId)
    else:
        logger.warning(routeTransfersMockMessage)

    return RazorpayRouteClient(
        apiKey=settings.razorpayKeyId,
        apiSecret=settings.razorpayKeySecret,
        isMockMode=not settings.routeTransportLive,
        ordersLive=settings.hasRazorpayCredentials,
    )


__all__ = ["buildRouteClient"]
