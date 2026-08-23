"""Merchant profile, registration, and cryptographic keypair schemas."""

from pydantic import BaseModel, ConfigDict, Field

from ..constants.merchantConstants import (
    gstinRegexPattern,
    pinCodeRegexPattern,
    razorpayRouteAccountPrefix,
)

# Merchant Registration Field Limits & Patterns
minBusinessNameLength: int = 2
maxBusinessNameLength: int = 200
razorpayAccountIdRegexPattern: str = rf"^{razorpayRouteAccountPrefix}[a-zA-Z0-9_]+$"


class MerchantRegistrationRequest(BaseModel):
    """Payload for onboarding and registering a merchant in the mesh network."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    businessName: str = Field(
        min_length=minBusinessNameLength,
        max_length=maxBusinessNameLength,
    )
    gstin: str = Field(pattern=gstinRegexPattern)
    razorpayAccountId: str = Field(pattern=razorpayAccountIdRegexPattern)
    contactEmail: str
    originPincode: str = Field(pattern=pinCodeRegexPattern)


class MerchantProfile(BaseModel):
    """Public merchant profile stored and broadcasted in RazorAgent Mesh."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    merchantDid: str
    publicKeyHex: str
    businessName: str
    gstin: str
    razorpayAccountId: str
    contactEmail: str
    originPincode: str
    registeredAtTimestamp: int


class MerchantKeypairRecord(BaseModel):
    """Cryptographic keypair record for merchant digital identity and signing."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    merchantDid: str
    publicKeyHex: str
    privateKeyHex: str
    registeredAtTimestamp: int


__all__ = [
    "MerchantKeypairRecord",
    "MerchantProfile",
    "MerchantRegistrationRequest",
    "maxBusinessNameLength",
    "minBusinessNameLength",
    "razorpayAccountIdRegexPattern",
]
