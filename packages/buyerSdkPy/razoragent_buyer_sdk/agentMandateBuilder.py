"""AP2 Mandate lifecycle builder, canonical hashing, and cryptographic chain verifier."""

import time
from typing import Any, Dict, List, Optional
import uuid

from .agentKeyManager import (
    AgentKeyManager,
    canonicalizeJson,
    computeSha256Digest,
)
from .constants import (
    defaultCurrency,
    defaultIntentValiditySeconds,
)
from .exceptions import (
    MandateHashMismatchError,
    MandateValidationError,
)
from .models import (
    AmendmentMandate,
    CartItemSchema,
    CartMandate,
    ExecutionMandate,
    IntentMandate,
    TaxBreakdownSchema,
)


def _generateNonce() -> str:
    """Generates random single-use cryptographic nonce."""
    return f"nonce_{uuid.uuid4().hex}"


def computeMandateHash(mandateModel: Any) -> str:
    """Computes SHA-256 hash of unsigned mandate payload via RFC 8785 JCS canonicalization."""
    if hasattr(mandateModel, "model_dump"):
        dataDict = mandateModel.model_dump()
    elif isinstance(mandateModel, dict):
        dataDict = dict(mandateModel)
    else:
        raise ValueError("mandateModel must be a Pydantic model or dict")

    signatureKeys = {"userSignature", "merchantSignature", "agentSignature"}
    unsignedDict = {k: v for k, v in dataDict.items() if k not in signatureKeys}
    canonicalBytes = canonicalizeJson(unsignedDict)
    return computeSha256Digest(canonicalBytes)


def createIntentMandate(
    mandateId: str,
    userKeyManager: AgentKeyManager,
    delegatedAgentDid: str,
    maxBudgetPaise: int,
    upiCircleDelegationToken: str,
    singleTransactionLimitPaise: int,
    authorizedCategories: Optional[List[str]] = None,
    validUntilTimestamp: Optional[int] = None,
    nonce: Optional[str] = None,
    timestamp: Optional[int] = None,
) -> IntentMandate:
    """Constructs and signs a new IntentMandate (M_I)."""
    if maxBudgetPaise <= 0 or singleTransactionLimitPaise <= 0:
        raise MandateValidationError("maxBudgetPaise and singleTransactionLimitPaise must be > 0")

    ts = timestamp if timestamp is not None else int(time.time())
    non = nonce or _generateNonce()
    cats = authorizedCategories if authorizedCategories is not None else []
    validUntil = validUntilTimestamp if validUntilTimestamp is not None else (ts + defaultIntentValiditySeconds)

    payload: Dict[str, Any] = {
        "authorizedCategories": cats, "currency": defaultCurrency, "delegatedAgentDid": delegatedAgentDid,
        "mandateId": mandateId, "maxBudgetPaise": maxBudgetPaise, "nonce": non,
        "singleTransactionLimitPaise": singleTransactionLimitPaise, "timestamp": ts,
        "upiCircleDelegationToken": upiCircleDelegationToken, "userDid": userKeyManager.getAgentDid(),
        "validUntilTimestamp": validUntil,
    }

    sig = userKeyManager.signPayload(payload)
    return IntentMandate(
        mandateId=mandateId, userDid=userKeyManager.getAgentDid(), delegatedAgentDid=delegatedAgentDid,
        maxBudgetPaise=maxBudgetPaise, currency=defaultCurrency, authorizedCategories=cats,
        validUntilTimestamp=validUntil, upiCircleDelegationToken=upiCircleDelegationToken,
        singleTransactionLimitPaise=singleTransactionLimitPaise, nonce=non, timestamp=ts, userSignature=sig,
    )


def _buildCartMandatePayload(
    cartId: str, merchantDid: str, merchantGstin: str, merchantStateCode: str,
    buyerDeliveryPincode: str, buyerDeliveryStateCode: str, items: List[CartItemSchema],
    taxableSubtotalPaise: int, taxBreakdown: TaxBreakdownSchema, shippingPaise: int,
    discountPaise: int, totalPaise: int, inventoryLockToken: str,
    inventoryLockExpiresAt: int, nonce: str, timestamp: int,
) -> Dict[str, Any]:
    return {
        "buyerDeliveryPincode": buyerDeliveryPincode, "buyerDeliveryStateCode": buyerDeliveryStateCode,
        "cartId": cartId, "discountPaise": discountPaise, "inventoryLockExpiresAt": inventoryLockExpiresAt,
        "inventoryLockToken": inventoryLockToken, "items": [item.model_dump() for item in items],
        "merchantDid": merchantDid, "merchantGstin": merchantGstin,
        "merchantStateCode": merchantStateCode, "nonce": nonce, "shippingPaise": shippingPaise,
        "taxBreakdown": taxBreakdown.model_dump(), "taxableSubtotalPaise": taxableSubtotalPaise,
        "timestamp": timestamp, "totalPaise": totalPaise,
    }


def createCartMandate(
    cartId: str, merchantKeyManager: AgentKeyManager, merchantGstin: str,
    merchantStateCode: str, buyerDeliveryPincode: str, buyerDeliveryStateCode: str,
    items: List[CartItemSchema], taxableSubtotalPaise: int, taxBreakdown: TaxBreakdownSchema,
    shippingPaise: int, discountPaise: int, totalPaise: int,
    inventoryLockToken: str, inventoryLockExpiresAt: int,
    nonce: Optional[str] = None, timestamp: Optional[int] = None,
) -> CartMandate:
    """Constructs and signs a new CartMandate (M_C)."""
    ts = timestamp if timestamp is not None else int(time.time())
    non = nonce or _generateNonce()
    mDid = merchantKeyManager.getAgentDid()
    payload = _buildCartMandatePayload(
        cartId, mDid, merchantGstin, merchantStateCode, buyerDeliveryPincode,
        buyerDeliveryStateCode, items, taxableSubtotalPaise, taxBreakdown,
        shippingPaise, discountPaise, totalPaise, inventoryLockToken,
        inventoryLockExpiresAt, non, ts,
    )
    sig = merchantKeyManager.signPayload(payload)
    return CartMandate(
        cartId=cartId, merchantDid=mDid, merchantGstin=merchantGstin,
        merchantStateCode=merchantStateCode, buyerDeliveryPincode=buyerDeliveryPincode,
        buyerDeliveryStateCode=buyerDeliveryStateCode, items=items, taxableSubtotalPaise=taxableSubtotalPaise,
        taxBreakdown=taxBreakdown, shippingPaise=shippingPaise, discountPaise=discountPaise,
        totalPaise=totalPaise, inventoryLockToken=inventoryLockToken,
        inventoryLockExpiresAt=inventoryLockExpiresAt, nonce=non, timestamp=ts, merchantSignature=sig,
    )



def createExecutionMandate(
    executionId: str,
    buyerKeyManager: AgentKeyManager,
    intentMandate: IntentMandate,
    cartMandate: CartMandate,
    settlementAmountPaise: int,
    upiCircleToken: str,
    nonce: Optional[str] = None,
    timestamp: Optional[int] = None,
) -> ExecutionMandate:
    """Constructs and signs a new ExecutionMandate (M_E) binding Intent and Cart hashes."""
    ts = timestamp if timestamp is not None else int(time.time())
    non = nonce or _generateNonce()
    iHash = computeMandateHash(intentMandate)
    cHash = computeMandateHash(cartMandate)

    payload: Dict[str, Any] = {
        "buyerAgentDid": buyerKeyManager.getAgentDid(), "cartMandateHash": cHash,
        "currency": defaultCurrency, "executionId": executionId, "intentMandateHash": iHash,
        "nonce": non, "settlementAmountPaise": settlementAmountPaise, "timestamp": ts,
        "upiCircleToken": upiCircleToken,
    }

    sig = buyerKeyManager.signPayload(payload)
    return ExecutionMandate(
        executionId=executionId, buyerAgentDid=buyerKeyManager.getAgentDid(),
        intentMandateHash=iHash, cartMandateHash=cHash, settlementAmountPaise=settlementAmountPaise,
        currency=defaultCurrency, upiCircleToken=upiCircleToken, nonce=non, timestamp=ts, agentSignature=sig,
    )


def createAmendmentMandate(
    amendmentId: str,
    buyerKeyManager: AgentKeyManager,
    merchantKeyManager: AgentKeyManager,
    previousCartMandate: CartMandate,
    newCartMandate: CartMandate,
    substitutedSkuMapping: Dict[str, str],
    priceDeltaPaise: int,
    amendmentReason: str,
    nonce: Optional[str] = None,
    timestamp: Optional[int] = None,
) -> AmendmentMandate:
    """Constructs dual-signed AmendmentMandate (M_A) for out-of-stock or price updates."""
    ts = timestamp if timestamp is not None else int(time.time())
    non = nonce or _generateNonce()
    pHash = computeMandateHash(previousCartMandate)
    nHash = computeMandateHash(newCartMandate)

    payload: Dict[str, Any] = {
        "amendmentId": amendmentId, "amendmentReason": amendmentReason, "newCartMandateHash": nHash,
        "nonce": non, "previousCartMandateHash": pHash, "priceDeltaPaise": priceDeltaPaise,
        "substitutedSkuMapping": substitutedSkuMapping, "timestamp": ts,
    }

    cBytes = canonicalizeJson(payload)
    return AmendmentMandate(
        amendmentId=amendmentId, previousCartMandateHash=pHash, newCartMandateHash=nHash,
        substitutedSkuMapping=substitutedSkuMapping, priceDeltaPaise=priceDeltaPaise,
        amendmentReason=amendmentReason, nonce=non, timestamp=ts,
        agentSignature=buyerKeyManager.signCanonicalBytes(cBytes),
        merchantSignature=merchantKeyManager.signCanonicalBytes(cBytes),
    )


def verifyMandateHashChain(
    intentMandate: IntentMandate,
    cartMandate: CartMandate,
    executionMandate: ExecutionMandate,
    raiseOnMismatch: bool = True,
) -> bool:
    """Validates that ExecutionMandate binds exact cryptographic hashes of Intent and Cart."""
    expectedIntentHash = computeMandateHash(intentMandate)
    expectedCartHash = computeMandateHash(cartMandate)

    if executionMandate.intentMandateHash != expectedIntentHash:
        if raiseOnMismatch:
            raise MandateHashMismatchError(
                f"Intent hash mismatch: expected {expectedIntentHash}, got {executionMandate.intentMandateHash}"
            )
        return False

    if executionMandate.cartMandateHash != expectedCartHash:
        if raiseOnMismatch:
            raise MandateHashMismatchError(
                f"Cart hash mismatch: expected {expectedCartHash}, got {executionMandate.cartMandateHash}"
            )
        return False

    return True


def validateMandateInvariants(
    intentMandate: IntentMandate,
    cartMandate: CartMandate,
    executionMandate: ExecutionMandate,
    currentTime: Optional[int] = None,
) -> None:
    """Validates spending limits, temporal validity, and totals across the mandate chain."""
    now = currentTime if currentTime is not None else int(time.time())
    if now > intentMandate.validUntilTimestamp:
        raise MandateValidationError(f"Intent mandate expired at {intentMandate.validUntilTimestamp} (now: {now})")
    if executionMandate.settlementAmountPaise > intentMandate.maxBudgetPaise:
        raise MandateValidationError(f"Settlement amount exceeds max budget ({intentMandate.maxBudgetPaise})")
    if executionMandate.settlementAmountPaise > intentMandate.singleTransactionLimitPaise:
        raise MandateValidationError(f"Settlement amount exceeds single limit ({intentMandate.singleTransactionLimitPaise})")
    if cartMandate.totalPaise != executionMandate.settlementAmountPaise:
        raise MandateValidationError("Cart total does not match execution settlement amount")
    verifyMandateHashChain(intentMandate, cartMandate, executionMandate, raiseOnMismatch=True)


createSignedIntentMandate = createIntentMandate
createSignedCartMandate = createCartMandate
createSignedExecutionMandate = createExecutionMandate
createSignedAmendmentMandate = createAmendmentMandate


class AgentMandateBuilder:
    """AP2 Mandate lifecycle builder and validator factory."""

    createIntentMandate = staticmethod(createIntentMandate)
    createCartMandate = staticmethod(createCartMandate)
    createExecutionMandate = staticmethod(createExecutionMandate)
    createAmendmentMandate = staticmethod(createAmendmentMandate)
    computeHash = staticmethod(computeMandateHash)
    verifyHashChain = staticmethod(verifyMandateHashChain)
    validateInvariants = staticmethod(validateMandateInvariants)


__all__ = [
    "AgentMandateBuilder",
    "computeMandateHash",
    "createAmendmentMandate",
    "createCartMandate",
    "createExecutionMandate",
    "createIntentMandate",
    "createSignedAmendmentMandate",
    "createSignedCartMandate",
    "createSignedExecutionMandate",
    "createSignedIntentMandate",
    "validateMandateInvariants",
    "verifyMandateHashChain",
]
