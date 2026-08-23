"""PyNaCl Ed25519 cryptographic signer implementation."""

from typing import Any
import nacl.signing

from razoragentMesh.packages.mandateEngine.cryptoKeyUtils import formatDid
from razoragentMesh.packages.mandateEngine.jcsCanonicalizer import canonicalizeJson


class Ed25519Signer:
    """Asymmetric Ed25519 signer producing RFC 8785 detached signatures."""

    def __init__(self, privateKeyHex: str) -> None:
        if not isinstance(privateKeyHex, str) or len(privateKeyHex.strip()) != 64:
            raise ValueError("privateKeyHex must be a 64-character hexadecimal string")
        self._signingKey = nacl.signing.SigningKey(bytes.fromhex(privateKeyHex.strip()))
        self._publicKeyHex = self._signingKey.verify_key.encode().hex().lower()
        self._agentDid = formatDid(self._publicKeyHex)

    def getPublicKeyHex(self) -> str:
        """Returns the public key as a 64-character lowercase hex string."""
        return self._publicKeyHex

    def getAgentDid(self) -> str:
        """Returns the agent DID identifier."""
        return self._agentDid

    def signCanonicalBytes(self, canonicalBytes: bytes) -> str:
        """Generates a 64-byte (128 hex character) detached Ed25519 signature."""
        signedObject = self._signingKey.sign(canonicalBytes)
        return signedObject.signature.hex().lower()

    def signPayload(self, payload: Any) -> str:
        """Canonicalizes payload using JCS and returns the detached signature hex."""
        canonicalBytes = canonicalizeJson(payload)
        return self.signCanonicalBytes(canonicalBytes)
