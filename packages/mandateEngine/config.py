"""Configuration settings for Layer 4 mandateEngine."""

import os
from pydantic import BaseModel, ConfigDict, Field

# Key ids that are not credentials: the client's own default and the value shipped in
# .env.example. A developer who copies the example file verbatim has supplied nothing,
# and must not be silently switched onto the live transport on the strength of it.
placeholderRazorpayKeyIds: frozenset = frozenset(
    {"", "rzp_test_mock", "rzp_test_MockApiKey12345"}
)


class MandateEngineSettings(BaseModel):
    """Runtime configuration settings for Mandate & Settlement Engine."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    redisUrl: str = Field(
        default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        description="Redis connection URL for nonce ledger and state",
    )

    razorpayKeyId: str = Field(
        default_factory=lambda: os.getenv("RAZORPAY_KEY_ID", ""),
        description="Razorpay Test Mode key id; blank or placeholder selects the mock ledger",
    )

    razorpayKeySecret: str = Field(
        default_factory=lambda: os.getenv("RAZORPAY_KEY_SECRET", ""),
        description="Razorpay Test Mode key secret; blank selects the mock ledger",
    )

    allowUnboundedClientServerTime: bool = Field(
        default_factory=lambda: os.getenv("ALLOW_CLIENT_SERVER_TIME", "").lower()
        in ("1", "true", "yes"),
        description=(
            "Test seam. When true, /api/v1/settlement/execute accepts any serverTime instead of "
            "requiring it to sit near the real clock. Never enable outside a test run: serverTime "
            "overrides mandate expiry, inventory-lock expiry, the NTP drift window, cumulative "
            "spend expiry and the GSTR-1 invoice date."
        ),
    )

    razorpayWebhookSecret: str = Field(
        default_factory=lambda: os.getenv("RAZORPAY_WEBHOOK_SECRET", ""),
        description=(
            "Shared secret for verifying inbound Razorpay webhook deliveries. Blank disables "
            "the receiver: POST /api/v1/webhooks/razorpay answers 503 rather than accepting a "
            "payload it cannot verify."
        ),
    )

    routeTransportLive: bool = Field(
        default_factory=lambda: os.getenv("RAZORPAY_ROUTE_LIVE", "").lower()
        in ("1", "true", "yes"),
        description=(
            "Opt-in for LIVE Route capture and split transfers. Off by default even when "
            "credentials are present, because /v1/transfers needs Route activation and real "
            "linked account ids, and /v1/payments/{id}/capture needs a payment this mesh did "
            "not create. Supplying credentials alone enables the Orders API and nothing else."
        ),
    )

    @property
    def hasRazorpayCredentials(self) -> bool:
        """True only when both halves of a real Razorpay key pair are present.

        Deliberately conservative: settlement falls back to the deterministic mock
        ledger unless someone has actually supplied credentials, because a run that
        silently posts nowhere is worse than one that says it is mocked.
        """
        return (
            self.razorpayKeyId not in placeholderRazorpayKeyIds
            and bool(self.razorpayKeySecret)
        )


def getMandateEngineSettings() -> MandateEngineSettings:
    """Instantiates and returns frozen MandateEngineSettings instance."""
    return MandateEngineSettings()


defaultMandateSettings = getMandateEngineSettings()

__all__ = [
    "MandateEngineSettings",
    "defaultMandateSettings",
    "getMandateEngineSettings",
    "placeholderRazorpayKeyIds",
]
