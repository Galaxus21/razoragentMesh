"""Cryptographic nonce and timestamp generator."""

import time
import uuid

noncePrefix: str = "nonce_"


def generateNonce() -> str:
    """Generates a collision-resistant UUIDv4-based nonce string."""
    return f"{noncePrefix}{uuid.uuid4().hex}"


def generateTimestampedNonce() -> tuple[str, int]:
    """Generates a fresh nonce paired with current UTC Unix epoch seconds."""
    nonce = generateNonce()
    currentTimestamp = int(time.time())
    return nonce, currentTimestamp
