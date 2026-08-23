import hashlib
import json
import os
import sys
from typing import Any, Dict
import nacl.encoding
import nacl.signing

# Script Constants
fixturesDir = os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures")
keyFilePath = os.path.join(fixturesDir, "agentKeyFixtures.json")


def generateEd25519KeyRecord(seedString: str) -> Dict[str, str]:
    """Derives deterministic Ed25519 signing keypair from seed string."""
    seedBytes = hashlib.sha256(seedString.encode("utf-8")).digest()
    signingKey = nacl.signing.SigningKey(seedBytes)
    verifyKey = signingKey.verify_key

    pubHex = verifyKey.encode(encoder=nacl.encoding.HexEncoder).decode("utf-8").lower()
    privHex = seedBytes.hex().lower()

    return {
        "did": f"did:agent:{pubHex}",
        "publicKeyHex": pubHex,
        "privateKeyHex": privHex,
        "seedHex": privHex,
    }


def generateAllTestKeys() -> int:
    """Generates deterministic cryptographic keypairs for all protocol actors."""
    os.makedirs(fixturesDir, exist_ok=True)

    agentKeys = {
        "userCfo": generateEd25519KeyRecord("user-cfo-seed-2026"),
        "buyerAgent": generateEd25519KeyRecord("buyer-agent-seed-2026"),
        "merchantNode": generateEd25519KeyRecord("merchant-node-seed-2026"),
        "attackerNode": generateEd25519KeyRecord("attacker-sybil-seed-2026"),
        "platformNode": generateEd25519KeyRecord("platform-treasury-seed-2026"),
    }

    with open(keyFilePath, "w", encoding="utf-8") as fileHandle:
        json.dump(agentKeys, fileHandle, indent=2)

    print(f"Generated {len(agentKeys)} cryptographic keypairs into {keyFilePath}:")
    for role, keyData in agentKeys.items():
        print(f"  [{role}] DID: {keyData['did']}")

    return 0


if __name__ == "__main__":
    sys.exit(generateAllTestKeys())
