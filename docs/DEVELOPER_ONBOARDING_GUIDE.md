# RazorAgent Mesh v2.0 — Developer Onboarding Guide

An end-to-end, production-grade technical manual for software engineers, merchant platform developers, and autonomous agent architects integrating with **RazorAgent Mesh v2.0**.

---

## Table of Contents

1. [Executive Overview & Protocol Topology](#1-executive-overview--protocol-topology)
2. [System Prerequisites & Environment Setup](#2-system-prerequisites--environment-setup)
3. [Cryptographic Key Management & DID Minting](#3-cryptographic-key-management--did-minting)
4. [Step-by-Step Merchant Onboarding](#4-step-by-step-merchant-onboarding)
   - [Step 1: Merchant DID & Razorpay Route Registration](#step-1-merchant-did--razorpay-route-registration)
   - [Step 2: Autonomous Negotiation Policy Configuration](#step-2-autonomous-negotiation-policy-configuration)
   - [Step 3: Multi-Channel Catalog Ingestion](#step-3-multi-channel-catalog-ingestion)
   - [Step 4: Universal Product Protocol & Domain Facets](#step-4-universal-product-protocol--domain-facets)
   - [Step 5: Dynamic Bullion Pricing & MCX Spot Oracle](#step-5-dynamic-bullion-pricing--mcx-spot-oracle)
   - [Step 6: Statutory HSN Chapter Resolution & GST Tax Rules](#step-6-statutory-hsn-chapter-resolution--gst-tax-rules)
   - [Step 7: Programmatic SKU Authoring & Publishing](#step-7-programmatic-sku-authoring--publishing)
5. [Step-by-Step Buyer Agent Onboarding](#5-step-by-step-buyer-agent-onboarding)
   - [Step 1: Buyer SDK Installation](#step-1-buyer-sdk-installation)
   - [Step 2: Key Management & AP2 Budget Gate Limits](#step-2-key-management--ap2-budget-gate-limits)
   - [Step 3: User Spending Intent Mandate ($M_I$) Creation](#step-3-user-spending-intent-mandate-m_i-creation)
   - [Step 4: MCP Product Discovery & 4-Tier Discount Stacking](#step-4-mcp-product-discovery--4-tier-discount-stacking)
   - [Step 5: HTTP 402 PoW Challenge Resolution & B2B Bargaining](#step-5-http-402-pow-challenge-resolution--b2b-bargaining)
   - [Step 6: Atomic Stock Reservation with Monotonic Fencing](#step-6-atomic-stock-reservation-with-monotonic-fencing)
   - [Step 7: Cart ($M_C$), Execution ($M_E$), and Amendment ($M_A$) Mandates](#step-7-cart-m_c-execution-m_e-and-amendment-m_a-mandates)
   - [Step 8: Two-Phase Commit (2PC) Settlement Saga Execution](#step-8-two-phase-commit-2pc-settlement-saga-execution)
6. [Complete Executable End-to-End Implementations](#6-complete-executable-end-to-end-implementations)
   - [TypeScript Implementation](#typescript-implementation)
   - [Python Implementation](#python-implementation)
7. [Error Handling, HTTP Status Codes & Troubleshooting](#7-error-handling-http-status-codes--troubleshooting)

---

## 1. Executive Overview & Protocol Topology

**RazorAgent Mesh v2.0** is an open, decentralized agentic commerce protocol designed for autonomous machine-to-machine transactions over Indian sovereign payment rails (UPI Circle, Razorpay Route) and tax frameworks (GST Rule 46 / GSTR-1).

### Protocol Architecture

The protocol operates across 5 distinct cryptographic, discovery, negotiation, and settlement layers:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                 RAZORAGENT MESH TOPOLOGY                               │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ Layer 0: Ingress Anti-Spam & Sybil Shield                                              │
│   └── SHA-256 Dynamic Proof-of-Work (PoW) difficulty challenges + Anti-Replay Ledger  │
│                                                                                        │
│ Layer 1: Deterministic Discovery Enclave (MCP Server)                                  │
│   └── Anthropic JSON-RPC 2.0 Tools (get_live_sku_quote, reserve_inventory_lock,       │
│       verify_shipping_sla) + 4-Tier Auto-Discount Engine + HMAC-SHA256 Quote Digest   │
│                                                                                        │
│ Layer 2: HTTP 402-INR Dynamic Negotiation Gateway                                      │
│   └── Micro-escrow pre-auth + Rubinstein-Ståhl game-theoretic bilateral bargaining │
│   └── Monotonic concessions + AST Commercial Contract compilation                     │
│                                                                                        │
│ Layer 3: Sub-300ms Vector Healing Enclave                                              │
│   └── Qdrant ANN cosine similarity vector search + AutoVectorizer                      │
│                                                                                        │
│ Layer 4: AP2 Cryptographic Settlement Enclave                                          │
│   └── Ed25519 triple-mandate chain (M_I -> M_C -> M_E -> M_A) + RFC 8785 JCS           │
│   └── Deterministic Integer Paise Math (INV-01) + GST Floor Division (INV-02)         │
│   └── 2PC Settlement Saga Coordinator + 3-Way Razorpay Route Split + LIFO Rollback     │
│   └── GSTR-1 Rule 46 Tax Invoice Generation with SHA-256 Audit Seal                    │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Core Mathematical & Cryptographic Invariants

| Invariant | Name | Formulation / Specification | Enforcement Point |
|---|---|---|---|
| **INV-01** | Integer Paise Arithmetic | All monetary values represented in positive integers ($\mathbb{Z}^+$ paise, where ₹1.00 = 100 paise). Floating-point floats are strictly rejected. | `arithmeticEnclave.py`, `jcsCanonicalizer.ts` |
| **INV-02** | Zero-Penny GST Split | $\text{CGST} = \lfloor (\text{Taxable} \times \lfloor \text{Rate} / 2 \rfloor) / 100 \rfloor$, $\text{SGST} = \lfloor (\text{Taxable} \times \text{Rate}) / 100 \rfloor - \text{CGST}$, $\text{IGST} = \lfloor (\text{Taxable} \times \text{Rate}) / 100 \rfloor$ | `gstrInvoiceEngine.py`, `pricingEngine.ts` |
| **INV-03** | Ed25519 Canonical Signatures | Detached 64-byte Ed25519 cryptographic signatures generated over RFC 8785 JSON Canonicalization Scheme (JCS) byte buffers. | `AgentKeyManager`, `Ed25519Verifier` |
| **INV-04** | AP2 Budget Gate Invariant | $\text{SettlementAmountPaise} \le \min(\text{MaxBudgetPaise}, \text{SingleTransactionLimitPaise})$ with category whitelisting. | `budgetGate.py`, `agentMandateBuilder.ts` |
| **INV-05** | Anti-Replay Monotonic Nonces | Nonces are single-use UUIDv4/hex strings recorded via Redis atomic `SETNX` with a 120s TTL and a tight clock drift window $[T - 5\text{s}, T + 60\text{s}]$. | `nonceLedger.py` |
| **INV-06** | Negotiation Monotonicity | Buyer bids are strictly non-decreasing ($B_t \ge B_{t-1}$); seller asks are strictly non-increasing ($A_t \le A_{t-1}$), bounded by seller margin floor. | `bidStateMachine.py` |
| **INV-07** | Atomic Inventory Fencing | Redis Lua script executes atomic stock decrement and increments a monotonic fencing token, preventing concurrent double-allocation. | `inventoryLocker.ts`, `redisLockManager.ts` |

---

## 2. System Prerequisites & Environment Setup

### 2.1 Hardware & Runtime Requirements

- **Node.js**: v20.10.0+ (LTS) with `npm` v10+
- **Python**: v3.11.0+ (compatible with Python 3.12 and 3.13) with `pip` and `virtualenv`
- **Docker & Docker Compose**: Docker v24+ (Compose v2.20+)
- **Redis**: v7.0+ (standalone or clustered with Pub/Sub support)
- **Qdrant**: v1.7.0+ (Vector Search Engine running on port 6333)

### 2.2 Repository Layout

```
razoragentMesh/
├── packages/
│   ├── buyerSdkTs/         # TypeScript Buyer SDK (@razorpay/agent-buyer-sdk)
│   ├── buyerSdkPy/         # Python Buyer SDK (razoragent_buyer_sdk)
│   ├── catalogSanitizer/   # Input normalization & currency validation
│   ├── mandateEngine/      # AP2 Settlement Enclave & GSTR-1 Invoicing (Port 8000)
│   ├── mcpServer/          # Model Context Protocol JSON-RPC Server (Port 8001 / Stdio)
│   ├── merchantApi/        # Merchant Registration, Policy & Ingestion (Port 4002)
│   ├── vectorHealer/       # Vector substitution & healing engine (Port 6333 Qdrant)
│   └── x402Gateway/        # PoW Ingress & Negotiation State Machine (Port 8000)
├── docker-compose.yml      # Infrastructure orchestration (Redis, Qdrant, Microservices)
└── .env.example            # Environment configuration template
```

### 2.3 Environment Variable Template (`.env`)

Create a `.env` file in `razoragentMesh/` based on the template below:

```bash
# ==============================================================================
# RAZORAGENT MESH — ENVIRONMENT CONFIGURATION
# ==============================================================================

# Razorpay Test Mode Credentials
RAZORPAY_KEY_ID=rzp_test_MockApiKey12345
RAZORPAY_KEY_SECRET=MockApiSecretKey67890

# Infrastructure Endpoints
REDIS_URL=redis://localhost:6379/0
QDRANT_HOST=localhost
QDRANT_PORT=6333
MERCHANT_API_PORT=4002
MERCHANT_API_URL=http://localhost:4002

# Ed25519 Cryptographic Keys (Hex Seeds / 32-byte Private Keys)
MERCHANT_PRIVATE_KEY_HEX=ac262c2b5daf3f4272ed052f7b331cbb6152588ae58dfb022f71c7b8a2c45364
BUYER_AGENT_PRIVATE_KEY_HEX=ad1b82a9cce6d36564c79f026ff7479072875d80cb85b5b95a3478df90572270
USER_CFO_PRIVATE_KEY_HEX=ec89f8790fa0bc33882dd0c02c67a79a0a68f6976f52010b7e656564db3c9f8a

# Layer 1 MCP Quote HMAC Signing Key
HMAC_SECRET_KEY=razoragent_mesh_hmac_secret_key_2026
```

### 2.4 Launching Local Infrastructure

Start Redis and Qdrant via Docker Compose:

```bash
# From razoragentMesh directory
docker compose up -d redis qdrant
```

Verify service health:
```bash
# Redis Ping
docker compose exec redis redis-cli ping
# Output: PONG

# Qdrant Health Check
curl http://localhost:6333/healthz
# Output: {"title":"qdrant - vector search engine","version":"..."}
```

---

## 3. Cryptographic Key Management & DID Minting

All actors in the mesh (Merchants, Buyer Agents, CFO/Users) are identified by Decentralized Identifiers (DIDs) rooted in Ed25519 public verification keys.

### 3.1 DID Specifications

| Actor Type | DID Format | Public Key Component | Example |
|---|---|---|---|
| **Merchant** | `did:razoragent:merchant:<hex16>` | First 16 hex characters of Ed25519 Verify Key | `did:razoragent:merchant:9f8e7d6c5b4a3210` |
| **Buyer Agent** | `did:razoragent:buyer:<hex16>` | First 16 hex characters of Ed25519 Verify Key | `did:razoragent:buyer:ad1b82a9cce6d365` |
| **User / CFO** | `did:razoragent:user:<hex16>` | First 16 hex characters of Ed25519 Verify Key | `did:razoragent:user:ec89f8790fa0bc33` |

### 3.2 Keypair Generation & Signing (Python / PyNaCl)

```python
import json
import nacl.signing
import nacl.encoding
import hashlib

def generateActorKeypair() -> dict:
    """Generates an Ed25519 signing keypair and derives the RazorAgent DID."""
    signingKey = nacl.signing.SigningKey.generate()
    verifyKey = signingKey.verify_key
    
    privateKeyHex = signingKey.encode(encoder=nacl.encoding.HexEncoder).decode("utf-8")
    publicKeyHex = verifyKey.encode(encoder=nacl.encoding.HexEncoder).decode("utf-8")
    actorDid = f"did:razoragent:merchant:{publicKeyHex[:16]}"
    
    return {
        "did": actorDid,
        "privateKeyHex": privateKeyHex,
        "publicKeyHex": publicKeyHex
    }

def canonicalizeAndSign(payload: dict, privateKeyHex: str) -> str:
    """Canonicalizes payload per RFC 8785 (JCS) and generates detached Ed25519 signature."""
    # RFC 8785 deterministic serialization: sorted keys, no whitespace separators
    canonicalJson = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    canonicalBytes = canonicalJson.encode("utf-8")
    
    signingKey = nacl.signing.SigningKey(privateKeyHex, encoder=nacl.encoding.HexEncoder)
    signed = signingKey.sign(canonicalBytes)
    # Return detached 64-byte signature in hex (128 characters)
    return signed.signature.hex()
```

### 3.3 Keypair Generation & Signing (TypeScript / TweetNaCl)

```typescript
import nacl from "tweetnacl";
import { canonicalizeJson, computeSha256Digest } from "@razorpay/agent-buyer-sdk";

export class AgentKeyManager {
  private readonly _keyPair: nacl.SignKeyPair;

  private constructor(keyPair: nacl.SignKeyPair) {
    this._keyPair = keyPair;
  }

  public static generate(): AgentKeyManager {
    return new AgentKeyManager(nacl.sign.keyPair());
  }

  public static fromSecretKey(secretKeyHex: string): AgentKeyManager {
    const secretBytes = Buffer.from(secretKeyHex, "hex");
    return new AgentKeyManager(nacl.sign.keyPair.fromSecretKey(secretBytes));
  }

  public getPublicKeyHex(): string {
    return Buffer.from(this._keyPair.publicKey).toString("hex");
  }

  public getAgentDid(): string {
    return `did:razoragent:buyer:${this.getPublicKeyHex().slice(0, 16)}`;
  }

  public signPayload(payload: Record<string, unknown>): string {
    const canonicalBytes = canonicalizeJson(payload);
    const signatureBytes = nacl.sign.detached(canonicalBytes, this._keyPair.secretKey);
    return Buffer.from(signatureBytes).toString("hex");
  }
}
```

---

## 4. Step-by-Step Merchant Onboarding

The Merchant Onboarding flow registers regulatory credentials, provisions autonomous negotiation parameters, ingests multi-vertical product catalogs, configures dynamic bullion pricing rules, and publishes SKUs to the mesh.

### Step 1: Merchant DID & Razorpay Route Registration

Merchants submit statutory GSTIN details, their registered Razorpay Route linked account (`acc_...`), contact email, and dispatch origin pincode to the `merchantApi` service on port `4002`.

#### Validation Rules
1. **GSTIN Checksum**: Verified via Indian GST Luhn Mod-36 algorithm (`^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$`).
2. **Razorpay Route Account**: Must match prefix `acc_` with minimum length 14.
3. **Origin Pincode**: 6 digits starting with 1-9 (`^[1-9][0-9]{5}$`).

#### Registration Request
```bash
curl -X POST http://localhost:4002/api/v1/merchant/register \
  -H "Content-Type: application/json" \
  -d '{
    "businessName": "Tanishq Flagship Enclave",
    "gstin": "27AAACG0123M1Z5",
    "razorpayAccountId": "acc_N0xMerchantGold99",
    "contactEmail": "ops@tanishq.example.com",
    "originPincode": "400001"
  }'
```

#### Registration Response (HTTP 201 Created)
```json
{
  "merchantDid": "did:razoragent:merchant:9f8e7d6c5b4a3210",
  "publicKeyHex": "9f8e7d6c5b4a3210fedcba9876543210fedcba9876543210fedcba9876543210",
  "businessName": "Tanishq Flagship Enclave",
  "gstin": "27AAACG0123M1Z5",
  "razorpayAccountId": "acc_N0xMerchantGold99",
  "contactEmail": "ops@tanishq.example.com",
  "originPincode": "400001",
  "registeredAtTimestamp": 1724750000
}
```

---

### Step 2: Autonomous Negotiation Policy Configuration

Merchants define their automated concession limits for bilateral bargaining with AI buyer agents. The negotiation state machine enforces these boundaries server-side.

#### Policy Parameters
- `marginFloorBps`: Maximum discount floor in basis points (e.g., `800` = 8.00% max discount).
- `minimumOrderQuantity`: Minimum order quantity eligible for dynamic bargaining.
- `autoAcceptSpreadPaise`: Spread in paise below which a counter-offer is automatically accepted.
- `maxNegotiationTurns`: Maximum allowable Rubinstein-Ståhl bargaining turns ($N \le 10$, default `5`).

#### Policy Request
```bash
curl -X PUT http://localhost:4002/api/v1/merchant/did:razoragent:merchant:9f8e7d6c5b4a3210/policy \
  -H "Content-Type: application/json" \
  -d '{
    "merchantDid": "did:razoragent:merchant:9f8e7d6c5b4a3210",
    "marginFloorBps": 800,
    "minimumOrderQuantity": 1,
    "autoAcceptSpreadPaise": 50,
    "maxNegotiationTurns": 5,
    "createdAtTimestamp": 1724750000,
    "updatedAtTimestamp": 1724750000
  }'
```

---

### Step 3: Multi-Channel Catalog Ingestion

RazorAgent Mesh provides four distinct programmatic ingestion adapters:

#### A. Direct Single-SKU REST Ingestion
Endpoint: `POST /api/v1/merchant/{merchantDid}/catalog`

```bash
curl -X POST http://localhost:4002/api/v1/merchant/did:razoragent:merchant:9f8e7d6c5b4a3210/catalog \
  -H "Content-Type: application/json" \
  -d '{
    "skuId": "SKU-COTTON-TSHIRT-BLK-L",
    "merchantDid": "did:razoragent:merchant:9f8e7d6c5b4a3210",
    "title": "Classic Organic Cotton Crewneck T-Shirt - Black / L",
    "description": "100% combed organic cotton jersey with reinforced collar and bio-wash finish",
    "category": "apparel",
    "hsnCode": "6109",
    "gstRatePercent": 5,
    "baseUnitPricePaise": 99900,
    "availableStock": 150,
    "originPincode": "400001",
    "currency": "INR",
    "volumeTiers": [
      { "minQuantity": 5, "discountBps": 500 },
      { "minQuantity": 20, "discountBps": 1000 }
    ],
    "minimumOrderQuantity": 1,
    "apparelFacet": {
      "size": "L",
      "color": "Black",
      "fabric": ["100% Organic Cotton", "Combed Jersey"],
      "fitType": "Regular",
      "gender": "UNISEX"
    }
  }'
```

#### B. Bulk CSV Catalog Batch Upload (Up to 500 rows/batch)
Endpoint: `POST /api/v1/merchant/{merchantDid}/bulk-csv`

Create `catalog_batch.csv`:
```csv
skuId,title,description,category,hsnCode,gstRatePercent,baseUnitPriceInr,availableStock,originPincode,size,color,fabric,purityCarat,grossWeightGrams,activeSalt,dosageMg,allergens,isVeg
SKU-TSHIRT-WHT-M,Organic Cotton Tee White M,100% Cotton,apparel,6109,5,899.00,100,400001,M,White,"100% Cotton",,,,,,,
SKU-GOLD-RING-18K,18K Diamond Solitaire Ring,18K Gold,jewelry,7113,3,45000.00,10,400001,,,,18,4.5,,,,
SKU-PARACETAMOL-650,Dolo 650mg Tablet,Paracetamol,pharma,3004,5,32.50,500,400001,,,,,Paracetamol,650,,,
SKU-ALMOND-MILK-1L,Raw Unsweetened Almond Milk 1L,Almond Milk,fmcg,2202,12,240.00,80,400001,,,,,,,"Tree Nuts",true
```

Upload CSV via cURL:
```bash
curl -X POST http://localhost:4002/api/v1/merchant/did:razoragent:merchant:9f8e7d6c5b4a3210/bulk-csv \
  -F "file=@catalog_batch.csv"
```

#### C. Shopify Webhook Ingestion
Endpoint: `POST /api/v1/merchant/{merchantDid}/shopify-sync`

Receives standard Shopify `products/create` and `products/update` webhooks. Variants are automatically mapped to SKU format `SHOPIFY-{productId}-{variantId}` and Shopify tags are parsed into domain facets (`promo:...`, `allergens:...`, `salt:...`, `18k`/`22k`/`24k`).

#### D. ERP Delta Stock & Price Sync
Endpoint: `POST /api/v1/merchant/{merchantDid}/erp-sync`

```bash
curl -X POST http://localhost:4002/api/v1/merchant/did:razoragent:merchant:9f8e7d6c5b4a3210/erp-sync \
  -H "Content-Type: application/json" \
  -d '{
    "merchantDid": "did:razoragent:merchant:9f8e7d6c5b4a3210",
    "batchId": "erp_sync_batch_9921",
    "deltas": [
      {
        "skuId": "SKU-COTTON-TSHIRT-BLK-L",
        "stockDelta": -5,
        "newUnitPricePaise": 94900
      }
    ]
  }'
```

---

### Step 4: Universal Product Protocol & Domain Facets

RazorAgent Mesh supports 4 multi-industry domain facets:

```json
{
  "apparelFacet": {
    "size": "XL",
    "color": "Navy Blue",
    "fabric": ["100% Linen", "Breathable Weave"],
    "fitType": "Slim",
    "gender": "M"
  },
  "fmcgFacet": {
    "allergens": ["Gluten", "Lactose"],
    "shelfLifeDays": 180,
    "isVeg": true,
    "fssaiNumber": "10019022009831"
  },
  "jewelryFacet": {
    "purityCarat": 22,
    "grossWeightGrams": 12.5,
    "hallmarkNumber": "BIS-MH-881923"
  },
  "pharmaFacet": {
    "activeSalt": "Amoxicillin and Potassium Clavulanate",
    "dosageMg": 625,
    "schedule": "H",
    "prescriptionRequired": true
  }
}
```

---

### Step 5: Dynamic Bullion Pricing & MCX Spot Oracle

For precious metals (Gold 24K, Gold 22K, Silver), merchants can attach a `DynamicPricingRule` to evaluate real-time quotations linked directly to MCX spot feeds.

#### Mathematical Valuation Formula

$$\text{GoldCostPaise} = \lfloor \text{NetWeightGrams} \times \text{SpotRatePaisePerGram} \times \text{PurityMultiplier} \rfloor$$

$$\text{TaxableAmountPaise} = \text{GoldCostPaise} + \text{MakingChargesPaise} + \text{StoneChargesPaise}$$

$$\text{GSTPaise} = \lfloor (\text{TaxableAmountPaise} \times \text{GstRatePercent}) / 100 \rfloor$$

$$\text{UnitPricePaise} = \text{TaxableAmountPaise} + \text{GSTPaise}$$

#### Bullion SKU Payload with Dynamic Pricing Attachment
```json
{
  "skuId": "SKU-GOLD-CHAIN-22K-10G",
  "merchantDid": "did:razoragent:merchant:9f8e7d6c5b4a3210",
  "title": "22K Solid Yellow Gold Rope Chain (10g)",
  "description": "BIS Hallmarked 22 Karat Yellow Gold Chain with lobster clasp",
  "category": "jewelry",
  "hsnCode": "7113",
  "gstRatePercent": 3,
  "baseUnitPricePaise": 6228000,
  "availableStock": 25,
  "originPincode": "400001",
  "jewelryFacet": {
    "purityCarat": 22,
    "grossWeightGrams": 10.0,
    "hallmarkNumber": "BIS-MH-998231",
    "dynamicPricingRule": {
      "pricingType": "FORMULA_SPOT_LINKED",
      "oracleFeedSymbol": "MCX_GOLD_22K_INR_PER_GRAM",
      "purityMultiplier": 1.0,
      "netWeightGrams": 10.0,
      "makingChargesPaise": 450000,
      "makingChargesType": "FIXED_PAISE",
      "stoneChargesPaise": 0,
      "maxQuoteTtlSeconds": 60
    }
  }
}
```

---

### Step 6: Statutory HSN Chapter Resolution & GST Tax Rules

RazorAgent Mesh enforces statutory GST rates based on Indian HSN/SAC classifications:

| Category | HSN Code | Statutory GST Rate | Tax Split (Intra-State) | Tax Split (Inter-State) |
|---|---|---|---|---|
| **Precious Jewelry** | `7113` | **3%** | 1.5% CGST + 1.5% SGST | 3.0% IGST |
| **Apparel (< ₹1,000)** | `6109` | **5%** | 2.5% CGST + 2.5% SGST | 5.0% IGST |
| **Apparel (> ₹1,000)** | `6203` | **12%** | 6.0% CGST + 6.0% SGST | 12.0% IGST |
| **Pharmaceuticals** | `3004` | **5%** / **12%** | 2.5% CGST + 2.5% SGST | 5.0% / 12.0% IGST |
| **Packaged Foods (FMCG)**| `2106` | **12%** / **18%** | 6.0% CGST + 6.0% SGST | 12.0% / 18.0% IGST |
| **Electronics & Hardware**| `8471` | **18%** | 9.0% CGST + 9.0% SGST | 18.0% IGST |
| **Luxury / Automobiles** | `8703` | **28%** | 14.0% CGST + 14.0% SGST | 28.0% IGST |

---

### Step 7: Programmatic SKU Authoring & Publishing

Merchants can use a lightweight Python or Node.js publishing script to automate catalog registration and live updates:

```python
import httpx
import asyncio

async def publishCatalogItem(merchantDid: str, listing: dict):
    async with httpx.AsyncClient(base_url="http://localhost:4002") as client:
        response = await client.post(f"/api/v1/merchant/{merchantDid}/catalog", json=listing)
        if response.status_code == 201:
            print(f"✅ SKU '{listing['skuId']}' published successfully!")
        else:
            print(f"❌ Failed to publish SKU: [{response.status_code}] {response.text}")

if __name__ == "__main__":
    sampleListing = {
        "skuId": "SKU-LINEN-SHIRT-WHT-M",
        "merchantDid": "did:razoragent:merchant:9f8e7d6c5b4a3210",
        "title": "Pure French Linen Shirt - White / M",
        "description": "Breathable 100% flax linen shirt with mother of pearl buttons",
        "category": "apparel",
        "hsnCode": "6205",
        "gstRatePercent": 12,
        "baseUnitPricePaise": 249900,
        "availableStock": 50,
        "originPincode": "400001",
        "currency": "INR",
        "volumeTiers": [{"minQuantity": 3, "discountBps": 600}],
        "apparelFacet": {
            "size": "M",
            "color": "White",
            "fabric": ["100% Flax Linen"],
            "fitType": "Regular",
            "gender": "M"
        }
    }
    asyncio.run(publishCatalogItem("did:razoragent:merchant:9f8e7d6c5b4a3210", sampleListing))
```

---

## 5. Step-by-Step Buyer Agent Onboarding

AI Buyer Agents execute automated purchasing workflows within principal-delegated spending constraints.

### Step 1: Buyer SDK Installation

#### TypeScript / Node.js
```bash
npm install @razorpay/agent-buyer-sdk tweetnacl uuid
```

#### Python
```bash
pip install razoragent_buyer_sdk pynacl httpx pydantic
```

---

### Step 2: Key Management & AP2 Budget Gate Limits

Initialize the `AgentKeyManager` and configure the human principal's spending delegation limits:

```typescript
import { AgentKeyManager, RazorAgentClient } from "@razorpay/agent-buyer-sdk";

// 1. Initialize Buyer Agent & Human Signers
const userSigner = AgentKeyManager.generate();
const buyerAgentSigner = AgentKeyManager.generate();

// 2. Initialize Unified Mesh Client
const client = new RazorAgentClient({
  mcpServerUrl: "http://localhost:8001",
  mandateEngineUrl: "http://localhost:8000",
  x402GatewayUrl: "http://localhost:8000",
  buyerKeyManager: buyerAgentSigner,
});
```

---

### Step 3: User Spending Intent Mandate ($M_I$) Creation

The user signs an immutable **Intent Mandate ($M_I$)** establishing strict financial and category limits:

```typescript
import { createSignedIntentMandate } from "@razorpay/agent-buyer-sdk";

const intentMandate = createSignedIntentMandate(
  {
    delegatedAgentDid: buyerAgentSigner.getAgentDid(),
    maxBudgetPaise: 10000000,             // ₹1,00,000.00 Max Total Budget
    singleTransactionLimitPaise: 7000000, // ₹70,000.00 Max Single Transaction
    upiCircleDelegationToken: "upi_circle_tok_991823",
    authorizedCategories: ["jewelry", "apparel"],
    validUntilTimestamp: Math.floor(Date.now() / 1000) + 86400, // 24 Hours
  },
  userSigner
);
```

---

### Step 4: MCP Product Discovery & 4-Tier Discount Stacking

The buyer agent queries the Layer 1 MCP tool `get_live_sku_quote` and receives a dynamic quote with automated discount stacking and tax breakdown.

#### 4-Tier Auto-Discount Pipeline
1. **Tier 1: Volume Discount**: Basis points based on requested quantity.
2. **Tier 2: Campaign Promo**: Promo codes (e.g. `FESTIVE10`, 10% off capped at ₹20.00).
3. **Tier 3: UPI Rail Incentive**: Flat ₹1.50 (150 paise) incentive on UPI Circle rail.
4. **Tier 4: Corporate Partner Promo**: Additional 5% discount for corporate accounts (`CORP_5PCT`).

```typescript
// 1. Discover Real-time Quote with Auto-Discounts
const quote = await client.getLiveSkuQuote("SKU-GOLD-CHAIN-22K-10G", 1, {
  deliveryPincode: "560001",
  promoCode: "FESTIVE10",
});

// 2. Verify Zonal Shipping SLA (Zone A/B/C)
const sla = await client.verifyShippingSla("560001", 100);
```

---

### Step 5: HTTP 402 PoW Challenge Resolution & B2B Bargaining

If the SKU requires dynamic negotiation, the gateway challenges the buyer with an HTTP 402 Payment Required status containing a cryptographic SHA-256 Proof-of-Work puzzle.

```typescript
import { solvePowChallenge, generatePowHeaders } from "@razorpay/agent-buyer-sdk";

// The RazorAgentClient automatically solves PoW challenges and executes turns:
// 1. Solve SHA-256 challenge (find nonce where SHA256(challenge + nonce) has D leading zeros)
// 2. Debit turn fee (₹0.50) from micro-escrow session
// 3. Negotiate turn over Rubinstein-Ståhl state machine until contract convergence
```

---

### Step 6: Atomic Stock Reservation with Monotonic Fencing

The buyer locks stock for 60 seconds via `reserve_inventory_lock`. The enclave executes an atomic Redis Lua script, returning a lock token and monotonic fencing token:

```typescript
const lock = await client.reserveInventoryLock("SKU-GOLD-CHAIN-22K-10G", 1, {
  lockTtlSeconds: 60,
  quoteHash: quote.quoteHash,
});

console.log("Acquired Lock Token:", lock.lockToken);
console.log("Monotonic Fencing Token:", lock.fencingToken);
```

---

### Step 7: Cart ($M_C$), Execution ($M_E$), and Amendment ($M_A$) Mandates

```typescript
import { createSignedCartMandate, createSignedExecutionMandate } from "@razorpay/agent-buyer-sdk";

// 1. Merchant signs Cart Mandate (M_C)
const cartMandate = createSignedCartMandate(
  {
    merchantGstin: "27AAACG0123M1Z5",
    merchantStateCode: "27", // Maharashtra
    buyerDeliveryPincode: "560001",
    buyerDeliveryStateCode: "29", // Karnataka (Inter-state IGST)
    items: [
      {
        skuId: "SKU-GOLD-CHAIN-22K-10G",
        hsnCode: "7113",
        quantity: 1,
        unitPricePaise: quote.finalUnitPricePaise,
        gstRatePercent: 3,
        lineTotalPaise: quote.finalUnitPricePaise * 1,
      },
    ],
    taxableSubtotalPaise: quote.finalUnitPricePaise,
    taxBreakdown: quote.taxBreakdown,
    shippingPaise: sla.shippingFeePaise,
    discountPaise: quote.totalSavingsPaise,
    totalPaise: quote.finalUnitPricePaise + quote.taxBreakdown.totalTaxPaise + sla.shippingFeePaise,
    inventoryLockToken: lock.lockToken,
    inventoryLockExpiresAt: lock.expiresAtUnixMs,
  },
  merchantSigner
);

// 2. Buyer Agent signs Execution Mandate (M_E) binding H(M_I) and H(M_C)
const executionMandate = createSignedExecutionMandate(
  {
    intentMandate,
    cartMandate,
    settlementAmountPaise: cartMandate.totalPaise,
    upiCircleToken: intentMandate.upiCircleDelegationToken,
  },
  buyerAgentSigner
);
```

---

### Step 8: Two-Phase Commit (2PC) Settlement Saga Execution

The buyer agent submits the mandate chain to `POST /api/v1/settlement/execute`.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                          2PC SETTLEMENT SAGA COORDINATOR                               │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ PHASE 1: Verify & Capture                                                              │
│   ├── Nonce Ledger SETNX check + Clock Drift [T-5s, T+60s]                             │
│   ├── Ed25519 signature verification on M_I, M_C, M_E                                  │
│   ├── AP2 Budget Gate verification (GrossTotal <= maxBudget, whitelists, expiry)       │
│   └── Primary Razorpay Route / UPI Circle payment capture                              │
│                                                                                        │
│ PHASE 2: Route Split Transfers (Sequential)                                            │
│   ├── 1. Merchant Net Payout: (CartTotal - ProtocolFee - Shipping) -> acc_...          │
│   ├── 2. Protocol Fee: ₹0.50 (50 paise) -> acc_mesh_protocol_fee                      │
│   └── 3. Logistics Payout: ShippingPaise -> acc_logistics_express                      │
│                                                                                        │
│ COMPENSATION ROLLBACK (If Transfer 2 or 3 Fails):                                      │
│   └── Reverse completed transfers in LIFO Order + Enqueue to Compensation DLQ          │
│                                                                                        │
│ GSTR-1 TAX INVOICE ISSUANCE:                                                           │
│   └── Generate GST Rule 46 invoice with itemized tax splits + 64-char SHA-256 seal     │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Complete Executable End-to-End Implementations

### TypeScript Implementation

```typescript
import {
  AgentKeyManager,
  RazorAgentClient,
  createSignedIntentMandate,
  createSignedCartMandate,
} from "@razorpay/agent-buyer-sdk";

async function runAutonomousPurchaseFlow() {
  // 1. Initialize Actor Cryptographic Key Managers
  const userSigner = AgentKeyManager.generate();
  const buyerAgentSigner = AgentKeyManager.generate();
  const merchantSigner = AgentKeyManager.generate();

  // 2. Initialize Client
  const client = new RazorAgentClient({
    mcpServerUrl: "http://localhost:8001",
    mandateEngineUrl: "http://localhost:8000",
    x402GatewayUrl: "http://localhost:8000",
    buyerKeyManager: buyerAgentSigner,
  });

  // 3. Human User delegates spending authorization via Signed Intent Mandate (M_I)
  const intentMandate = createSignedIntentMandate(
    {
      delegatedAgentDid: buyerAgentSigner.getAgentDid(),
      maxBudgetPaise: 10000000,             // ₹1,00,000.00
      singleTransactionLimitPaise: 7000000, // ₹70,000.00
      upiCircleDelegationToken: "upi_circle_del_tok_991823",
      authorizedCategories: ["jewelry", "apparel"],
      validUntilTimestamp: Math.floor(Date.now() / 1000) + 86400,
    },
    userSigner
  );

  // 4. Query live SKU quote with automated discount stacking
  const quote = await client.getLiveSkuQuote("SKU-GOLD-CHAIN-22K-10G", 1, {
    deliveryPincode: "560001",
    promoCode: "FESTIVE10",
  });

  // 5. Query Shipping SLA
  const sla = await client.verifyShippingSla("560001", 100);

  // 6. Acquire atomic 60-second Redis stock lock
  const lock = await client.reserveInventoryLock("SKU-GOLD-CHAIN-22K-10G", 1, {
    lockTtlSeconds: 60,
    quoteHash: quote.quoteHash,
  });

  // 7. Merchant issues signed Cart Mandate (M_C)
  const cartMandate = createSignedCartMandate(
    {
      merchantGstin: "27AAACG0123M1Z5",
      merchantStateCode: "27",
      buyerDeliveryPincode: "560001",
      buyerDeliveryStateCode: "29",
      items: [
        {
          skuId: "SKU-GOLD-CHAIN-22K-10G",
          hsnCode: "7113",
          quantity: 1,
          unitPricePaise: quote.finalUnitPricePaise,
          gstRatePercent: 3,
          lineTotalPaise: quote.finalUnitPricePaise * 1,
        },
      ],
      taxableSubtotalPaise: quote.finalUnitPricePaise,
      taxBreakdown: quote.taxBreakdown,
      shippingPaise: sla.shippingFeePaise,
      discountPaise: quote.totalSavingsPaise,
      totalPaise: quote.finalUnitPricePaise + quote.taxBreakdown.totalTaxPaise + sla.shippingFeePaise,
      inventoryLockToken: lock.lockToken,
      inventoryLockExpiresAt: lock.expiresAtUnixMs,
    },
    merchantSigner
  );

  // 8. Execute 2PC Settlement Saga
  const settlementResult = await client.executeAutonomousPurchase({
    skuId: "SKU-GOLD-CHAIN-22K-10G",
    quantity: 1,
    intentMandate,
    cartMandate,
    merchantAccount: "acc_N0xMerchantGold99",
    paymentId: "pay_RzpLiveTest99812",
    serverTime: Math.floor(Date.now() / 1000),
  });

  console.log("✅ Settlement Saga Complete!");
  console.log("Status:", settlementResult.status);
  console.log("GSTR-1 Invoice Number:", settlementResult.invoice.invoiceNumber);
  console.log("Cryptographic Audit Seal:", settlementResult.invoice.cryptographicAuditHash);
}

runAutonomousPurchaseFlow().catch(console.error);
```

---

### Python Implementation

```python
import asyncio
import time
from razoragent_buyer_sdk import (
    AgentKeyManager,
    CartItemSchema,
    CartMandate,
    ExecutionMandate,
    IntentMandate,
    MeshSlaConfig,
    RazorAgentClient,
    TaxBreakdownSchema,
    createCartMandate,
    createExecutionMandate,
    createIntentMandate,
)

async def runPythonBuyerFlow():
    # 1. Initialize Actor Key Managers
    userSigner = AgentKeyManager.generate()
    buyerAgentSigner = AgentKeyManager.generate()
    merchantSigner = AgentKeyManager.generate()

    config = MeshSlaConfig(gatewayBaseUrl="http://localhost:8000")

    async with RazorAgentClient(config=config, keyManager=buyerAgentSigner) as client:
        # 2. Human user signs Intent Mandate (M_I)
        intentMandate = createIntentMandate(
            mandateId="M-I-001",
            userKeyManager=userSigner,
            delegatedAgentDid=buyerAgentSigner.getAgentDid(),
            maxBudgetPaise=10000000,
            singleTransactionLimitPaise=7000000,
            upiCircleDelegationToken="upi_circle_tok_py_9921",
            authorizedCategories=["jewelry", "apparel"],
            validUntilTimestamp=int(time.time()) + 86400,
        )

        # 3. Discover Quote & Reserve Stock
        quote = await client.getLiveSkuQuote("SKU-GOLD-CHAIN-22K-10G", quantity=1, deliveryPincode="560001")
        lock = await client.reserveInventoryLock("SKU-GOLD-CHAIN-22K-10G", quantity=1, quoteHash=quote.quote_hash)

        # 4. Merchant signs Cart Mandate (M_C)
        cartMandate = createCartMandate(
            cartId="M-C-001",
            merchantKeyManager=merchantSigner,
            merchantGstin="27AAACG0123M1Z5",
            merchantStateCode="27",
            buyerDeliveryPincode="560001",
            buyerDeliveryStateCode="29",
            items=[
                CartItemSchema(
                    skuId="SKU-GOLD-CHAIN-22K-10G",
                    hsnCode="7113",
                    quantity=1,
                    unitPricePaise=quote.offered_unit_price_paise,
                    gstRatePercent=3,
                    lineTotalPaise=quote.offered_unit_price_paise * 1,
                )
            ],
            taxableSubtotalPaise=quote.offered_unit_price_paise,
            taxBreakdown=TaxBreakdownSchema(
                cgstPaise=quote.tax_breakdown.cgst_paise,
                sgstPaise=quote.tax_breakdown.sgst_paise,
                igstPaise=quote.tax_breakdown.igst_paise,
                totalTaxPaise=quote.tax_breakdown.total_tax_paise,
            ),
            shippingPaise=7000,
            discountPaise=quote.total_savings_paise,
            totalPaise=quote.offered_unit_price_paise + quote.tax_breakdown.total_tax_paise + 7000,
            inventoryLockToken=lock.lock_token,
            inventoryLockExpiresAt=lock.expires_at_unix_ms,
        )

        # 5. Buyer agent signs Execution Mandate (M_E)
        executionMandate = createExecutionMandate(
            executionId="M-E-001",
            buyerKeyManager=buyerAgentSigner,
            intentMandate=intentMandate,
            cartMandate=cartMandate,
            settlementAmountPaise=cartMandate.totalPaise,
            upiCircleToken=intentMandate.upiCircleDelegationToken,
        )

        # 6. Submit to 2PC Settlement Enclave
        settlementResult = await client.executeSettlement(
            intentMandate=intentMandate,
            cartMandate=cartMandate,
            executionMandate=executionMandate,
            merchantAccount="acc_N0xMerchantGold99",
            paymentId="pay_RzpPyTest99812",
            serverTime=int(time.time()),
        )

        print(f"✅ Settlement Success: {settlementResult.status}")
        print(f"Invoice Number: {settlementResult.invoice.invoiceNumber}")
        print(f"Audit Hash: {settlementResult.invoice.cryptographicAuditHash}")

if __name__ == "__main__":
    asyncio.run(runPythonBuyerFlow())
```

---

## 7. Error Handling, HTTP Status Codes & Troubleshooting

### 7.1 Common HTTP Status Codes

| HTTP Code | Error Condition | Root Cause & Resolution |
|---|---|---|
| **`400 Bad Request`** | `InvalidGstinException` | GSTIN fails Indian Luhn Mod-36 checksum. Verify format `27AAACG0123M1Z5`. |
| **`400 Bad Request`** | `BudgetExceededViolation` | Cart total exceeds $M_I.\text{maxBudgetPaise}$. Adjust intent budget or request price concession. |
| **`400 Bad Request`** | `SignatureVerificationFailedException` | Ed25519 signature invalid over RFC 8785 canonical bytes. Re-check signing key and payload canonicalizer. |
| **`402 Payment Required`** | `Http402RequiredError` | Ingress PoW challenge or micro-escrow debit required. Ensure SDK has `autoSolvePow=true`. |
| **`404 Not Found`** | `CatalogNotFoundException` | Requested `skuId` does not exist for the specified `merchantDid`. |
| **`409 Conflict`** | `NonceReplayException` | The nonce in $M_E$ was previously used or timestamp drifted outside $[T-5\text{s}, T+60\text{s}]$. |
| **`409 Conflict`** | `InsufficientStockException` | Inventory count is below requested quantity. Intercept and route to Vector Healer. |
| **`502 Bad Gateway`** | `SettlementCompensationTriggeredException` | Razorpay Route split payout failed. Automatic LIFO rollback was executed and queued to DLQ. |

### 7.2 Troubleshooting Guide

#### 1. "Nonce replay detected or timestamp drift"
- **Cause**: Server timestamp and client timestamp differ by more than 5 seconds in the past or 60 seconds in the future.
- **Fix**: Synchronize client host clocks using NTP (`sudo apt install chrony && chronyd -q`).

#### 2. "Floating point values rejected in JCS canonicalizer"
- **Cause**: Monetary inputs contain floats (e.g. `99.50` instead of `9950`).
- **Fix**: Adhere strictly to **INV-01**: Pass all prices, taxes, and discounts in integer paise.

#### 3. "StalePriceQuoteException: Price quote is stale"
- **Cause**: Dynamic bullion quote exceeded its `maxQuoteTtlSeconds` (default 60s).
- **Fix**: Refresh quote via `get_live_sku_quote` immediately prior to issuing $M_C$ and $M_E$.
