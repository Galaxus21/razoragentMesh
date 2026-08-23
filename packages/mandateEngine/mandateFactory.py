"""Mandate Factory for lifecycle creation, hashing, and hash-chain verification."""

import time
from typing import Any, Optional
from pydantic import BaseModel

from razoragentMesh.packages.mandateEngine.amendmentMandateSchema import AmendmentMandate
from razoragentMesh.packages.mandateEngine.cartMandateSchema import (
    CartItemSchema,
    CartMandate,
    TaxBreakdownSchema,
)
from razoragentMesh.packages.mandateEngine.ed25519Signer import Ed25519Signer
from razoragentMesh.packages.mandateEngine.executionMandateSchema import ExecutionMandate
from razoragentMesh.packages.mandateEngine.intentMandateSchema import IntentMandate
from razoragentMesh.packages.mandateEngine.jcsCanonicalizer import (
    canonicalizeJson,
    computeSha256Digest,
)
from razoragentMesh.packages.mandateEngine.nonceGenerator import generateNonce
from razoragentMesh.packages.mandateEngine.settlementExceptions import (
    MandateHashChainMismatchException,
)

SIGNATURE_KEYS = frozenset({"userSignature", "merchantSignature", "agentSignature"})


def computeMandateHash(mandateModel: BaseModel) -> str:
    """Computes SHA-256 hash over canonical JCS bytes with signatures stripped."""
    dataDict = mandateModel.model_dump()
    unsignedDict = {k: v for k, v in dataDict.items() if k not in SIGNATURE_KEYS}
    return computeSha256Digest(canonicalizeJson(unsignedDict))


def _buildIntentPayload(mandateId: str, userDid: str, agentDid: str, budget: int, upiTok: str, singleLimit: int, categories: list[str], validUntil: int, nonce: str, ts: int) -> dict[str, Any]:
    """Constructs dictionary for IntentMandate canonical serialization."""
    return {
        "authorizedCategories": categories, "currency": "INR", "delegatedAgentDid": agentDid,
        "mandateId": mandateId, "maxBudgetPaise": budget, "nonce": nonce,
        "singleTransactionLimitPaise": singleLimit, "timestamp": ts,
        "upiCircleDelegationToken": upiTok, "userDid": userDid, "validUntilTimestamp": validUntil,
    }


def createSignedIntentMandate(
    mandateId: str, userSigner: Ed25519Signer, delegatedAgentDid: str, maxBudgetPaise: int,
    upiCircleDelegationToken: str, singleTransactionLimitPaise: int,
    authorizedCategories: Optional[list[str]] = None, validUntilTimestamp: Optional[int] = None,
    nonce: Optional[str] = None, timestamp: Optional[int] = None,
) -> IntentMandate:
    """Constructs and signs a new IntentMandate (M_I)."""
    ts = timestamp or int(time.time())
    non = nonce or generateNonce()
    cats = authorizedCategories or []
    validUntil = validUntilTimestamp or (ts + 86400)
    pld = _buildIntentPayload(mandateId, userSigner.getAgentDid(), delegatedAgentDid, maxBudgetPaise, upiCircleDelegationToken, singleTransactionLimitPaise, cats, validUntil, non, ts)
    sig = userSigner.signCanonicalBytes(canonicalizeJson(pld))
    return IntentMandate(
        mandateId=mandateId, userDid=userSigner.getAgentDid(), delegatedAgentDid=delegatedAgentDid,
        maxBudgetPaise=maxBudgetPaise, currency="INR", authorizedCategories=cats,
        validUntilTimestamp=validUntil, upiCircleDelegationToken=upiCircleDelegationToken,
        singleTransactionLimitPaise=singleTransactionLimitPaise, nonce=non, timestamp=ts, userSignature=sig,
    )


def _buildCartUnsignedPayload(cartId: str, merchantDid: str, merchantGstin: str, merchantStateCode: str, pincode: str, deliveryState: str, items: list[CartItemSchema], subtotal: int, taxBreakdown: TaxBreakdownSchema, shipping: int, discount: int, total: int, lockToken: str, lockExpiry: int, nonce: str, timestamp: int) -> dict[str, Any]:
    """Constructs cart dictionary for JCS canonicalization."""
    return {
        "buyerDeliveryPincode": pincode, "buyerDeliveryStateCode": deliveryState, "cartId": cartId,
        "discountPaise": discount, "inventoryLockExpiresAt": lockExpiry, "inventoryLockToken": lockToken,
        "items": [item.model_dump() for item in items], "merchantDid": merchantDid,
        "merchantGstin": merchantGstin, "merchantStateCode": merchantStateCode, "nonce": nonce,
        "shippingPaise": shipping, "taxBreakdown": taxBreakdown.model_dump(),
        "taxableSubtotalPaise": subtotal, "timestamp": timestamp, "totalPaise": total,
    }


def createSignedCartMandate(
    cartId: str, merchantSigner: Ed25519Signer, merchantGstin: str, merchantStateCode: str,
    buyerDeliveryPincode: str, buyerDeliveryStateCode: str, items: list[CartItemSchema],
    taxableSubtotalPaise: int, taxBreakdown: TaxBreakdownSchema, shippingPaise: int,
    discountPaise: int, totalPaise: int, inventoryLockToken: str, inventoryLockExpiresAt: int,
    nonce: Optional[str] = None, timestamp: Optional[int] = None,
) -> CartMandate:
    """Constructs and signs a new CartMandate (M_C)."""
    ts = timestamp or int(time.time())
    non = nonce or generateNonce()
    pld = _buildCartUnsignedPayload(
        cartId, merchantSigner.getAgentDid(), merchantGstin, merchantStateCode,
        buyerDeliveryPincode, buyerDeliveryStateCode, items, taxableSubtotalPaise,
        taxBreakdown, shippingPaise, discountPaise, totalPaise,
        inventoryLockToken, inventoryLockExpiresAt, non, ts,
    )
    sig = merchantSigner.signCanonicalBytes(canonicalizeJson(pld))
    return CartMandate(
        cartId=cartId, merchantDid=merchantSigner.getAgentDid(), merchantGstin=merchantGstin,
        merchantStateCode=merchantStateCode, buyerDeliveryPincode=buyerDeliveryPincode,
        buyerDeliveryStateCode=buyerDeliveryStateCode, items=items, taxableSubtotalPaise=taxableSubtotalPaise,
        taxBreakdown=taxBreakdown, shippingPaise=shippingPaise, discountPaise=discountPaise,
        totalPaise=totalPaise, inventoryLockToken=inventoryLockToken, inventoryLockExpiresAt=inventoryLockExpiresAt,
        nonce=non, timestamp=ts, merchantSignature=sig,
    )


def createSignedExecutionMandate(
    executionId: str, buyerAgentSigner: Ed25519Signer, intentMandate: IntentMandate,
    cartMandate: CartMandate, settlementAmountPaise: int, upiCircleToken: str,
    nonce: Optional[str] = None, timestamp: Optional[int] = None,
) -> ExecutionMandate:
    """Constructs and signs a new ExecutionMandate (M_E) binding Intent and Cart hashes."""
    ts = timestamp or int(time.time())
    non = nonce or generateNonce()
    iHash = computeMandateHash(intentMandate)
    cHash = computeMandateHash(cartMandate)
    pld = {
        "buyerAgentDid": buyerAgentSigner.getAgentDid(), "cartMandateHash": cHash, "currency": "INR",
        "executionId": executionId, "intentMandateHash": iHash, "nonce": non,
        "settlementAmountPaise": settlementAmountPaise, "timestamp": ts, "upiCircleToken": upiCircleToken,
    }
    sig = buyerAgentSigner.signCanonicalBytes(canonicalizeJson(pld))
    return ExecutionMandate(
        executionId=executionId, buyerAgentDid=buyerAgentSigner.getAgentDid(), intentMandateHash=iHash,
        cartMandateHash=cHash, settlementAmountPaise=settlementAmountPaise, currency="INR",
        upiCircleToken=upiCircleToken, nonce=non, timestamp=ts, agentSignature=sig,
    )


def createSignedAmendmentMandate(
    amendmentId: str, buyerAgentSigner: Ed25519Signer, merchantSigner: Ed25519Signer,
    previousCartMandate: CartMandate, newCartMandate: CartMandate,
    substitutedSkuMapping: dict[str, str], priceDeltaPaise: int, amendmentReason: str,
    nonce: Optional[str] = None, timestamp: Optional[int] = None,
) -> AmendmentMandate:
    """Constructs dual-signed AmendmentMandate (M_A) for out-of-stock healing."""
    ts = timestamp or int(time.time())
    non = nonce or generateNonce()
    pHash = computeMandateHash(previousCartMandate)
    nHash = computeMandateHash(newCartMandate)
    pld = {
        "amendmentId": amendmentId, "amendmentReason": amendmentReason, "newCartMandateHash": nHash,
        "nonce": non, "previousCartMandateHash": pHash, "priceDeltaPaise": priceDeltaPaise,
        "substitutedSkuMapping": substitutedSkuMapping, "timestamp": ts,
    }
    b = canonicalizeJson(pld)
    return AmendmentMandate(
        amendmentId=amendmentId, previousCartMandateHash=pHash, newCartMandateHash=nHash,
        substitutedSkuMapping=substitutedSkuMapping, priceDeltaPaise=priceDeltaPaise,
        amendmentReason=amendmentReason, nonce=non, timestamp=ts,
        agentSignature=buyerAgentSigner.signCanonicalBytes(b),
        merchantSignature=merchantSigner.signCanonicalBytes(b),
    )


def verifyMandateHashChain(
    intentMandate: IntentMandate,
    cartMandate: CartMandate,
    executionMandate: ExecutionMandate,
) -> bool:
    """Verifies that ExecutionMandate binds authentic hashes of M_I and M_C."""
    computedIntentHash = computeMandateHash(intentMandate)
    if computedIntentHash != executionMandate.intentMandateHash:
        raise MandateHashChainMismatchException(
            f"Intent mandate hash mismatch: expected {computedIntentHash}, got {executionMandate.intentMandateHash}"
        )
    computedCartHash = computeMandateHash(cartMandate)
    if computedCartHash != executionMandate.cartMandateHash:
        raise MandateHashChainMismatchException(
            f"Cart mandate hash mismatch: expected {computedCartHash}, got {executionMandate.cartMandateHash}"
        )
    return True
