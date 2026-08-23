"""PyNaCl Ed25519 key generation and DID utility functions."""

import nacl.signing


def generateKeyPair() -> tuple[str, str]:
    """Generates a fresh 32-byte Ed25519 signing keypair in hexadecimal format."""
    signingKey = nacl.signing.SigningKey.generate()
    privateKeyHex = signingKey.encode().hex()
    publicKeyHex = signingKey.verify_key.encode().hex()
    return privateKeyHex, publicKeyHex


def formatDid(publicKeyHex: str) -> str:
    """Formats a 32-byte public key hex into a standardized Decentralized Identifier (DID)."""
    return f"did:agent:{publicKeyHex.lower()}"


def extractPublicKeyFromDid(did: str) -> str:
    """Extracts raw hexadecimal public key from a DID identifier."""
    prefix = "did:agent:"
    if not did.startswith(prefix):
        raise ValueError(f"Invalid DID format: '{did}', expected prefix '{prefix}'")
    publicKeyHex = did[len(prefix):].strip()
    if len(publicKeyHex) != 64:
        raise ValueError(f"Invalid public key length in DID: expected 64 hex chars, got {len(publicKeyHex)}")
    return publicKeyHex.lower()
