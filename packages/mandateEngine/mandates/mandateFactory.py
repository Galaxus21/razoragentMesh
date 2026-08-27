"""Mandate Factory for lifecycle creation, hashing, and hash-chain verification."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from ..crypto.ed25519Signer import Ed25519Signer
from ..crypto.jcsCanonicalizer import canonicalizeJson
from ..crypto.nonceGenerator import generateNonce
from ..verification.signatureChainVerifier import (
    computeMandateHash,
    verifyMandateChain,
    verifyMandateHashChain,
)
from .amendmentMandateSchema import AmendmentMandate
from .cartMandateSchema import (
    CartItemSchema,
    CartMandate,
    TaxBreakdownSchema,
)
from .executionMandateSchema import ExecutionMandate
from .intentMandateSchema import IntentMandate

defaultCurrency: str = "INR"
defaultIntentValiditySeconds: int = 86400


def createSignedIntentMandate(
    mandateId: str, userSigner: Ed25519Signer, delegatedAgentDid: str, maxBudgetPaise: int,
    upiCircleDelegationToken: str, singleTransactionLimitPaise: int,
    authorizedCategories: Optional[list[str]] = None, validUntilTimestamp: Optional[int] = None,
    nonce: Optional[str] = None, timestamp: Optional[int] = None,
) -> IntentMandate:
    """Constructs and signs a new IntentMandate (M_I)."""
    timestampUnix = timestamp or int(time.time())
    nonceValue = nonce or generateNonce()
    categories = authorizedCategories or []
    validUntil = validUntilTimestamp or (timestampUnix + defaultIntentValiditySeconds)
    mandatePayload = _buildIntentPayload(
        mandateId, userSigner.getAgentDid(), delegatedAgentDid, maxBudgetPaise,
        upiCircleDelegationToken, singleTransactionLimitPaise, categories, validUntil, nonceValue, timestampUnix,
    )
    detachedSignature = userSigner.signCanonicalBytes(canonicalizeJson(mandatePayload))
    return IntentMandate(
        mandateId=mandateId, userDid=userSigner.getAgentDid(), delegatedAgentDid=delegatedAgentDid,
        maxBudgetPaise=maxBudgetPaise, currency=defaultCurrency, authorizedCategories=categories,
        validUntilTimestamp=validUntil, upiCircleDelegationToken=upiCircleDelegationToken,
        singleTransactionLimitPaise=singleTransactionLimitPaise, nonce=nonceValue, timestamp=timestampUnix, userSignature=detachedSignature,
    )


def createSignedCartMandate(
    cartId: str, merchantSigner: Ed25519Signer, merchantGstin: str, merchantStateCode: str,
    buyerDeliveryPincode: str, buyerDeliveryStateCode: str, items: list[CartItemSchema],
    taxableSubtotalPaise: int, taxBreakdown: TaxBreakdownSchema, shippingPaise: int,
    discountPaise: int, totalPaise: int, inventoryLockToken: str, inventoryLockExpiresAt: int,
    nonce: Optional[str] = None, timestamp: Optional[int] = None,
) -> CartMandate:
    """Constructs and signs a new CartMandate (M_C)."""
    timestampUnix = timestamp or int(time.time())
    nonceValue = nonce or generateNonce()
    mandatePayload = _buildCartUnsignedPayload(
        cartId, merchantSigner.getAgentDid(), merchantGstin, merchantStateCode,
        buyerDeliveryPincode, buyerDeliveryStateCode, items, taxableSubtotalPaise,
        taxBreakdown, shippingPaise, discountPaise, totalPaise,
        inventoryLockToken, inventoryLockExpiresAt, nonceValue, timestampUnix,
    )
    detachedSignature = merchantSigner.signCanonicalBytes(canonicalizeJson(mandatePayload))
    return CartMandate(
        cartId=cartId, merchantDid=merchantSigner.getAgentDid(), merchantGstin=merchantGstin,
        merchantStateCode=merchantStateCode, buyerDeliveryPincode=buyerDeliveryPincode,
        buyerDeliveryStateCode=buyerDeliveryStateCode, items=items, taxableSubtotalPaise=taxableSubtotalPaise,
        taxBreakdown=taxBreakdown, shippingPaise=shippingPaise, discountPaise=discountPaise,
        totalPaise=totalPaise, inventoryLockToken=inventoryLockToken, inventoryLockExpiresAt=inventoryLockExpiresAt,
        nonce=nonceValue, timestamp=timestampUnix, merchantSignature=detachedSignature,
    )


def createSignedExecutionMandate(
    executionId: str, buyerAgentSigner: Ed25519Signer, intentMandate: IntentMandate,
    cartMandate: CartMandate, settlementAmountPaise: int, upiCircleToken: str,
    nonce: Optional[str] = None, timestamp: Optional[int] = None,
) -> ExecutionMandate:
    """Constructs and signs a new ExecutionMandate (M_E) binding Intent and Cart hashes."""
    timestampUnix = timestamp or int(time.time())
    nonceValue = nonce or generateNonce()
    intentHash = computeMandateHash(intentMandate)
    cartHash = computeMandateHash(cartMandate)
    mandatePayload = {
        "buyerAgentDid": buyerAgentSigner.getAgentDid(), "cartMandateHash": cartHash,
        "currency": defaultCurrency, "executionId": executionId, "intentMandateHash": intentHash,
        "nonce": nonceValue, "settlementAmountPaise": settlementAmountPaise, "timestamp": timestampUnix,
        "upiCircleToken": upiCircleToken,
    }
    detachedSignature = buyerAgentSigner.signCanonicalBytes(canonicalizeJson(mandatePayload))
    return ExecutionMandate(
        executionId=executionId, buyerAgentDid=buyerAgentSigner.getAgentDid(),
        intentMandateHash=intentHash, cartMandateHash=cartHash, settlementAmountPaise=settlementAmountPaise,
        currency=defaultCurrency, upiCircleToken=upiCircleToken, nonce=nonceValue, timestamp=timestampUnix, agentSignature=detachedSignature,
    )


def createSignedAmendmentMandate(
    amendmentId: str, buyerAgentSigner: Ed25519Signer, merchantSigner: Ed25519Signer,
    previousCartMandate: CartMandate, newCartMandate: CartMandate,
    substitutedSkuMapping: dict[str, str], priceDeltaPaise: int, amendmentReason: str,
    nonce: Optional[str] = None, timestamp: Optional[int] = None,
) -> AmendmentMandate:
    """Constructs dual-signed AmendmentMandate (M_A) for out-of-stock healing."""
    timestampUnix = timestamp or int(time.time())
    nonceValue = nonce or generateNonce()
    previousHash = computeMandateHash(previousCartMandate)
    newHash = computeMandateHash(newCartMandate)
    mandatePayload = {
        "amendmentId": amendmentId, "amendmentReason": amendmentReason,
        "newCartMandateHash": newHash, "nonce": nonceValue, "previousCartMandateHash": previousHash,
        "priceDeltaPaise": priceDeltaPaise, "substitutedSkuMapping": substitutedSkuMapping, "timestamp": timestampUnix,
    }
    canonicalPayloadBytes = canonicalizeJson(mandatePayload)
    return AmendmentMandate(
        amendmentId=amendmentId, previousCartMandateHash=previousHash, newCartMandateHash=newHash,
        substitutedSkuMapping=substitutedSkuMapping, priceDeltaPaise=priceDeltaPaise,
        amendmentReason=amendmentReason, nonce=nonceValue, timestamp=timestampUnix,
        agentSignature=buyerAgentSigner.signCanonicalBytes(canonicalPayloadBytes),
        merchantSignature=merchantSigner.signCanonicalBytes(canonicalPayloadBytes),
    )


def _buildIntentPayload(
    mandateId: str, userDid: str, delegatedAgentDid: str, maxBudgetPaise: int,
    upiCircleDelegationToken: str, singleTransactionLimitPaise: int,
    authorizedCategories: list[str], validUntilTimestamp: int, nonceValue: str,
    timestampUnix: int,
) -> dict[str, Any]:
    """Constructs dictionary for IntentMandate canonical serialization."""
    return {
        "authorizedCategories": authorizedCategories, "currency": defaultCurrency,
        "delegatedAgentDid": delegatedAgentDid, "mandateId": mandateId,
        "maxBudgetPaise": maxBudgetPaise, "nonce": nonceValue,
        "singleTransactionLimitPaise": singleTransactionLimitPaise, "timestamp": timestampUnix,
        "upiCircleDelegationToken": upiCircleDelegationToken, "userDid": userDid,
        "validUntilTimestamp": validUntilTimestamp,
    }


def _buildCartUnsignedPayload(
    cartId: str, merchantDid: str, merchantGstin: str, merchantStateCode: str,
    buyerDeliveryPincode: str, buyerDeliveryStateCode: str, items: list[CartItemSchema],
    taxableSubtotalPaise: int, taxBreakdown: TaxBreakdownSchema, shippingPaise: int,
    discountPaise: int, totalPaise: int, inventoryLockToken: str,
    inventoryLockExpiresAt: int, nonceValue: str, timestampUnix: int,
) -> dict[str, Any]:
    """Constructs cart dictionary for JCS canonicalization."""
    return {
        "buyerDeliveryPincode": buyerDeliveryPincode,
        "buyerDeliveryStateCode": buyerDeliveryStateCode,
        "cartId": cartId,
        "discountPaise": discountPaise,
        "inventoryLockExpiresAt": inventoryLockExpiresAt,
        "inventoryLockToken": inventoryLockToken,
        "items": [item.model_dump() for item in items],
        "merchantDid": merchantDid,
        "merchantGstin": merchantGstin,
        "merchantStateCode": merchantStateCode,
        "nonce": nonceValue,
        "shippingPaise": shippingPaise,
        "taxBreakdown": taxBreakdown.model_dump(),
        "taxableSubtotalPaise": taxableSubtotalPaise,
        "timestamp": timestampUnix,
        "totalPaise": totalPaise,
    }


__all__ = [
    "computeMandateHash",
    "createSignedAmendmentMandate",
    "createSignedCartMandate",
    "createSignedExecutionMandate",
    "createSignedIntentMandate",
    "defaultCurrency",
    "defaultIntentValiditySeconds",
    "verifyMandateChain",
    "verifyMandateHashChain",
]
