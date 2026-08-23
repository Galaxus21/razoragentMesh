"""PyNaCl Ed25519 key generation and DID utility functions."""

import nacl.signing

didPrefix: str = "did:agent:"
keyHexLength: int = 64


def generateKeyPair() -> tuple[str, str]:
    """Generates a fresh 32-byte Ed25519 signing keypair in hexadecimal format."""
    signingKey = nacl.signing.SigningKey.generate()
    privateKeyHex = signingKey.encode().hex()
    publicKeyHex = signingKey.verify_key.encode().hex()
    return privateKeyHex, publicKeyHex


def formatDid(publicKeyHex: str) -> str:
    """Formats a 32-byte public key hex into a standardized Decentralized Identifier (DID)."""
    return f"{didPrefix}{publicKeyHex.lower()}"


def extractPublicKeyFromDid(did: str) -> str:
    """Extracts raw hexadecimal public key from a DID identifier."""
    if not did.startswith(didPrefix):
        raise ValueError(f"Invalid DID format: '{did}', expected prefix '{didPrefix}'")
    publicKeyHex = did[len(didPrefix):].strip()
    if len(publicKeyHex) != keyHexLength:
        raise ValueError(f"Invalid public key length in DID: expected {keyHexLength} hex chars, got {len(publicKeyHex)}")
    return publicKeyHex.lower()
