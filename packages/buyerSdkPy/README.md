# RazorAgent Buyer SDK (`razoragent_buyer_sdk`)

Standalone Python SDK for autonomous AI buyer agents operating within the **RazorAgent Mesh v2.0** decentralized commerce ecosystem.

## Features

- **Asymmetric Key Management & DIDs:** Ed25519 key generation and `did:agent:<pubkey_hex>` minting using PyNaCl.
- **Deterministic AP2 Mandates:** RFC 8785 JSON Canonicalization Scheme (JCS) and SHA-256 hash-chain binding ($M_I \to M_C \to M_E$).
- **Anti-Spam Proof of Work (PoW):** High-throughput SHA-256 solver for x402-INR gateway challenges.
- **Unified Async Client:** High-performance `httpx.AsyncClient` wrapper supporting SKU discovery, inventory locks, 402 challenge handling, and 2PC settlement sagas.
- **Zero Floating-Point Financial Arithmetic:** All monetary values strictly enforced in integer paise.

## Installation

```bash
pip install razoragent_buyer_sdk
```

## Quick Start

```python
import asyncio
from razoragent_buyer_sdk import AgentKeyManager, AgentMandateBuilder, RazorAgentClient

async def main():
    # 1. Initialize buyer keypair
    keyManager = AgentKeyManager.generateKeypair()
    print("Buyer Agent DID:", keyManager.getAgentDid())

    # 2. Instantiate unified client
    async with RazorAgentClient(keyManager=keyManager) as client:
        # Get live quote
        quote = await client.getLiveSkuQuote("SKU-001", quantity=1, deliveryPincode="560001")
        print("Offered Unit Price:", quote.offered_unit_price_paise)

if __name__ == "__main__":
    asyncio.run(main())
```
