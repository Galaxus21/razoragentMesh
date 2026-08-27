"""Merchant onboarding registrar handling GSTIN validation, DID minting, and keypair generation."""

import time
from nacl.signing import SigningKey

try:
    from razoragentMesh.packages.mandateEngine.tax.gstinValidator import (
        computeGstinChecksum,
        validateGstin,
    )
except ImportError:
    try:
        from packages.mandateEngine.tax.gstinValidator import (
            computeGstinChecksum,
            validateGstin,
        )
    except ImportError:
        from mandateEngine.tax.gstinValidator import (
            computeGstinChecksum,
            validateGstin,
        )

from ..constants.merchantConstants import (
    didMerchantPrefix,
)
from ..schemas.merchantSchema import (
    MerchantKeypairRecord,
    MerchantProfile,
    MerchantRegistrationRequest,
)

keyHexSubstrLength: int = 16

# Backwards compatibility alias
_computeGstinChecksum = computeGstinChecksum


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
    "computeGstinChecksum",
    "generateMerchantKeypair",
    "mintMerchantDid",
    "validateGstin",
]
