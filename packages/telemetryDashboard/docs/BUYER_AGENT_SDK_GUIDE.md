# AI Buyer Agent SDK & AP2 Protocol Guide

A developer guide for integrating autonomous AI buyer agents with Ed25519 mandate signing, bilateral discount curves, and sub-300ms vector self-healing.

---

## 1. SDK Installation

Install the official standalone buyer agent SDK for your target runtime:

```typescript
// TypeScript / Node.js
npm install @razoragent/buyer-sdk-ts
```

```python
# Python 3.11+
pip install razoragent-buyer-sdk-py
```

---

## 2. Client Initialization & Key Management

Derive your buyer agent DID and configure the AP2 Budget Gate limits:

```typescript
import { RazorAgentClient } from "@razoragent/buyer-sdk-ts";

const buyerAgent = new RazorAgentClient({
  agentDid: "did:key:z6MkuP1Y...agentKey",
  privateKeyHex: process.env.BUYER_ED25519_PRIVATE_KEY!,
  gatewayUrl: "http://localhost:8000", // Mandate Engine Settlement Coordinator (Port 8000)
  maxDailyBudgetPaise: 5000000, // INR 50,000.00 AP2 Budget Gate
});
```

```python
import os
from razoragent_buyer_sdk import RazorAgentClient, AgentKeyManager

keyManager = AgentKeyManager.from_hex(os.environ["BUYER_ED25519_PRIVATE_KEY"])
buyerAgent = RazorAgentClient(
    key_manager=keyManager,
    gateway_url="http://localhost:8000",  # Mandate Engine Settlement Coordinator (Port 8000)
    max_budget_paise=5000000  # INR 50,000.00 AP2 Budget Gate
)
```

---

## 3. The 4-Phase Mandate Chaining Lifecycle (INV-02)

Every transaction executes across a four-stage cryptographic mandate chain:

```
┌────────────────────────────────────────────────────────────────────────┐
│                       AP2 TRIPLE-MANDATE CHAIN                         │
├───────────────────┬───────────────────┬────────────────────────────────┤
│ Mandate Type      │ Signer            │ Invariant Function             │
├───────────────────┼───────────────────┼────────────────────────────────┤
│ Intent ($M_I$)    │ User / CFO Agent  │ Max budget & spending limit    │
│ Cart ($M_C$)      │ Merchant Enclave  │ Stock lock & statutory GST     │
│ Execution ($M_E$) │ Buyer AI Agent    │ Canonical hash authorization   │
│ Amend ($M_A$)     │ Dual-Signed (A2A) │ Vector substitution (<300ms)   │
└───────────────────┴───────────────────┴────────────────────────────────┘
```

---

## 4. MCP Product Discovery & Cart Formulation

Search semantic catalogs with 4-tier automated discount stacking:

```typescript
// Search Semantic Catalog & Formulate Cart
const searchResults = await buyerAgent.catalog.search({
  query: "100% organic cotton oxford shirt size L",
  maxPricePaise: 350000,
  limit: 5,
});

const cart = await buyerAgent.cart.create({
  merchantDid: searchResults[0].merchantDid,
  items: [{ skuId: searchResults[0].skuId, quantity: 2 }],
});
```

```python
# Search Semantic Catalog & Formulate Cart
searchResults = await buyerAgent.search_catalog(
    query="100% organic cotton oxford shirt size L",
    max_price_paise=350000,
    limit=5
)

cart = await buyerAgent.create_cart(
    merchant_did=searchResults[0]["merchant_did"],
    items=[{"sku_id": searchResults[0]["sku_id"], "quantity": 2}]
)
```

---

## 5. Bilateral Dynamic Negotiation & Monotonic Concessions (INV-06)

Execute Rubinstein-Ståhl bargaining rounds under HTTP 402 micro-metering:

```typescript
// Bilateral Autonomous Negotiation & Sign ExecutionMandate (ME)
const negotiationResult = await buyerAgent.negotiate({
  cartId: cart.cartId,
  targetDiscountBps: 800,
  reservationPricePaise: 640000,
});

const executionMandate = await buyerAgent.mandates.signExecution({
  cartId: cart.cartId,
  agreedAmountPaise: negotiationResult.finalPaise,
});
```

```python
# Bilateral Autonomous Negotiation & Sign ExecutionMandate (ME)
negotiationResult = await buyerAgent.negotiate(
    cart_id=cart["cart_id"],
    target_discount_bps=800,
    reservation_price_paise=640000
)

executionMandate = await buyerAgent.sign_execution_mandate(
    cart_id=cart["cart_id"],
    agreed_amount_paise=negotiationResult["final_paise"]
)
```

---

## 6. Atomic Inventory Reservation & Fencing Tokens (INV-07)

Reserve stock atomically with a 60-second Redis Lua lock and monotonic fencing token:

```typescript
// Atomic Stock Lock Reservation
const stockLock = await buyerAgent.inventory.reserveLock({
  skuId: "sku_cotton_oxford_shirt",
  quantity: 2,
  ttlSeconds: 60,
});

console.log("Stock Locked:", stockLock.reservationId, "FencingToken:", stockLock.fencingToken);
```

```python
# Atomic Stock Lock Reservation
stockLock = await buyerAgent.reserve_stock(
    sku_id="sku_cotton_oxford_shirt",
    quantity=2,
    ttl_seconds=60
)

print(f"Stock Locked: {stockLock['reservation_id']}, FencingToken: {stockLock['fencing_token']}")
```

---

## 7. AP2 Two-Phase Commit Settlement Saga Execution

Submit the cryptographic mandate chain to the AP2 enclave for 3-way split transfer:

```typescript
// Submit to AP2 Cryptographic Settlement Enclave
const receipt = await buyerAgent.settlement.execute({
  mandateHash: executionMandate.sha256Hash,
  mandateSignature: executionMandate.ed25519Signature,
});

console.log("Settlement Confirmed:", receipt.razorpayPaymentId);
```

```python
# Submit to AP2 Cryptographic Settlement Enclave
receipt = await buyerAgent.execute_settlement(
    mandate_hash=executionMandate["sha256_hash"],
    mandate_signature=executionMandate["ed25519_signature"]
)

print(f"Settlement Confirmed: {receipt['razorpay_payment_id']}")
```
