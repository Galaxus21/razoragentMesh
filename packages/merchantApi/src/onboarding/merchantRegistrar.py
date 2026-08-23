"""Merchant onboarding registrar handling GSTIN validation, DID minting, and keypair generation."""

import re
import time
from nacl.signing import SigningKey

from ..constants.merchantConstants import (
    didMerchantPrefix,
    gstCharsTable,
    gstinLength,
    gstinRegexPattern,
)
from ..schemas.merchantSchema import (
    MerchantKeypairRecord,
    MerchantProfile,
    MerchantRegistrationRequest,
)

keyHexSubstrLength: int = 16


def _computeGstinChecksum(gstin14: str) -> str:
    """Calculates standard Indian GSTIN 15th character checksum using Luhn mod-36 algorithm."""
    total = 0
    for idx in range(14):
        val = gstCharsTable.index(gstin14[idx])
        factor = 1 if (idx % 2 == 0) else 2
        product = val * factor
        total += (product // 36) + (product % 36)
    checkCode = (36 - (total % 36)) % 36
    return gstCharsTable[checkCode]


def validateGstin(gstin: str) -> bool:
    """Validates an Indian GSTIN against format regex and mod-36 checksum."""
    if not isinstance(gstin, str):
        return False
    cleanGstin = gstin.strip().upper()
    if len(cleanGstin) != gstinLength:
        return False
    if not re.match(gstinRegexPattern, cleanGstin):
        return False
    expectedCheckChar = _computeGstinChecksum(cleanGstin[:14])
    return cleanGstin[14] == expectedCheckChar


def mintMerchantDid(publicKeyHex: str) -> str:
    """Mints a standardized merchant DID from public key hex prefix."""
    if not publicKeyHex:
        raise ValueError("Public key hex cannot be empty")
    cleanedHex = publicKeyHex.strip().lower()
    return f"{didMerchantPrefix}{cleanedHex[:keyHexSubstrLength]}"


def generateMerchantKeypair(request: MerchantRegistrationRequest) -> MerchantKeypairRecord:
    """Generates an Ed25519 cryptographic keypair and mints merchant DID."""
    signingKey = SigningKey.generate()
    privateKeyHex = signingKey.encode().hex()
    publicKeyHex = signingKey.verify_key.encode().hex()
    merchantDid = mintMerchantDid(publicKeyHex)

    return MerchantKeypairRecord(
        merchantDid=merchantDid,
        publicKeyHex=publicKeyHex,
        privateKeyHex=privateKeyHex,
        registeredAtTimestamp=int(time.time()),
    )


def buildMerchantProfile(
    request: MerchantRegistrationRequest,
    keypairRecord: MerchantKeypairRecord,
) -> MerchantProfile:
    """Constructs the public-facing merchant profile record."""
    return MerchantProfile(
        merchantDid=keypairRecord.merchantDid,
        publicKeyHex=keypairRecord.publicKeyHex,
        businessName=request.businessName,
        gstin=request.gstin,
        razorpayAccountId=request.razorpayAccountId,
        contactEmail=request.contactEmail,
        originPincode=request.originPincode,
        registeredAtTimestamp=keypairRecord.registeredAtTimestamp,
    )


__all__ = [
    "buildMerchantProfile",
    "generateMerchantKeypair",
    "mintMerchantDid",
    "validateGstin",
]
