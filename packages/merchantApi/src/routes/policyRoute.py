"""Merchant autonomous negotiation policy configuration routes."""

import time
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status

from ..constants.merchantConstants import redisMerchantPolicyKeyPrefix
from ..schemas.policySchema import NegotiationPolicy
from .dependencies import getRedisClient

policyRouter = APIRouter(prefix="/api/v1/merchant", tags=["merchant-policy"])


@policyRouter.put(
    "/{merchantDid}/policy",
    response_model=NegotiationPolicy,
    summary="Configure autonomous negotiation policy for merchant",
)
async def setPolicy(
    merchantDid: str,
    policy: NegotiationPolicy,
    redis: Any = Depends(getRedisClient),
) -> NegotiationPolicy:
    """Saves negotiation constraints, margin floors, and concession rates into Redis."""
    now = int(time.time())
    created = policy.createdAtTimestamp if policy.createdAtTimestamp > 0 else now
    syncedPolicy = policy.model_copy(
        update={
            "merchantDid": merchantDid,
            "createdAtTimestamp": created,
            "updatedAtTimestamp": now,
        }
    )
    policyKey = f"{redisMerchantPolicyKeyPrefix}{merchantDid}"
    await redis.set(policyKey, syncedPolicy.model_dump_json())
    return syncedPolicy


@policyRouter.get(
    "/{merchantDid}/policy",
    response_model=NegotiationPolicy,
    summary="Retrieve active negotiation policy for merchant",
)
async def getPolicy(
    merchantDid: str,
    redis: Any = Depends(getRedisClient),
) -> NegotiationPolicy:
    """Fetches stored negotiation parameters for autonomous agent settlement."""
    policyKey = f"{redisMerchantPolicyKeyPrefix}{merchantDid}"
    rawPayload = await redis.get(policyKey)
    if not rawPayload:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Negotiation policy not configured for merchant '{merchantDid}'",
        )

    rawText = rawPayload.decode("utf-8") if isinstance(rawPayload, bytes) else str(rawPayload)
    return NegotiationPolicy.model_validate_json(rawText)


__all__ = [
    "getPolicy",
    "policyRouter",
    "setPolicy",
]
