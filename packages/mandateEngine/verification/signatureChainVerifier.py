"""Cryptographic hash-chain and signature binding verification for AP2 mandates."""

from pydantic import BaseModel

from ..crypto.jcsCanonicalizer import canonicalizeJson, computeSha256Digest
from ..mandates.cartMandateSchema import CartMandate
from ..mandates.executionMandateSchema import ExecutionMandate
from ..mandates.intentMandateSchema import IntentMandate

signatureKeys: frozenset[str] = frozenset({"userSignature", "merchantSignature", "agentSignature"})


def computeMandateHash(mandateModel: BaseModel) -> str:
    """Computes SHA-256 hash over canonical JCS bytes with signatures stripped."""
    dataDict = mandateModel.model_dump()
    unsignedDict = {k: v for k, v in dataDict.items() if k not in signatureKeys}
    return computeSha256Digest(canonicalizeJson(unsignedDict))


def verifyMandateChain(
    intentMandate: IntentMandate,
    cartMandate: CartMandate,
    executionMandate: ExecutionMandate,
) -> bool:
    """Verifies that ExecutionMandate binds authentic hashes of M_I and M_C."""
    computedIntentHash = computeMandateHash(intentMandate)
    if computedIntentHash != executionMandate.intentMandateHash:
        from ..settlement.settlementExceptions import (
            MandateHashChainMismatchException,
        )

        raise MandateHashChainMismatchException(
            f"Intent mandate hash mismatch: expected {computedIntentHash}, got {executionMandate.intentMandateHash}"
        )

    computedCartHash = computeMandateHash(cartMandate)
    if computedCartHash != executionMandate.cartMandateHash:
        from ..settlement.settlementExceptions import (
            MandateHashChainMismatchException,
        )

        raise MandateHashChainMismatchException(
            f"Cart mandate hash mismatch: expected {computedCartHash}, got {executionMandate.cartMandateHash}"
        )

    return True


verifyMandateHashChain = verifyMandateChain
