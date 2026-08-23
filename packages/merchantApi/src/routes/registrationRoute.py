"""Merchant onboarding and DID cryptographic registration route."""

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status

from ..constants.merchantConstants import redisMerchantProfileKeyPrefix
from ..onboarding.merchantRegistrar import (
    buildMerchantProfile,
    generateMerchantKeypair,
    validateGstin,
)
from ..onboarding.razorpayAccountLinker import validateRazorpayAccountId
from ..schemas.merchantSchema import (
    MerchantProfile,
    MerchantRegistrationRequest,
)
from .dependencies import getRedisClient

registrationRouter = APIRouter(prefix="/api/v1/merchant", tags=["merchant-registration"])


@registrationRouter.post(
    "/register",
    response_model=MerchantProfile,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new merchant and generate Ed25519 DID keypair",
)
async def registerMerchant(
    request: MerchantRegistrationRequest,
    redis: Any = Depends(getRedisClient),
) -> MerchantProfile:
    """Registers a merchant, validates regulatory GSTIN/Razorpay credentials, and mints an AP2 DID."""
    if not validateGstin(request.gstin):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Indian GSTIN format or checksum",
        )

    if not validateRazorpayAccountId(request.razorpayAccountId):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Razorpay Route account ID format",
        )

    keypairRecord = generateMerchantKeypair(request)
    profile = buildMerchantProfile(request, keypairRecord)

    profileKey = f"{redisMerchantProfileKeyPrefix}{profile.merchantDid}"
    keypairKey = f"mesh:merchant:keypair:{profile.merchantDid}"

    await redis.set(profileKey, profile.model_dump_json())
    await redis.set(keypairKey, keypairRecord.model_dump_json())

    return profile


__all__ = [
    "registerMerchant",
    "registrationRouter",
]
