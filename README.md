# 🚀 RazorAgent Mesh: Autonomous Settlement Protocol for Agentic Commerce

> **Track 01:** AI Growth & Agentic Commerce (Razorpay AI Buildathon 2026)  
> **Author:** Shubham Verma  
> **Target Program:** Razorpay AI Builder Internship (Bangalore HQ)  
> **Status:** Production Architecture (Version 2.0 Hardened)

---

## 1. Executive Overview

**RazorAgent Mesh** is the **"Stripe for the Autonomous Agentic Economy"** — an end-to-end, machine-to-machine (M2M) commerce and settlement protocol built natively on Razorpay rails.

As autonomous AI agents (enterprise procurement bots, ERP replenishment loops, and consumer AI assistants) replace human shoppers, existing HTML checkouts and manual 2FA become insurmountable friction points. RazorAgent Mesh provides a 4-layer autonomous commerce protocol with **bounded cryptographic safety**, **zero floating-point math drift**, and **100% Indian regulatory compliance** (RBI 2FA / NPCI UPI Circle / GST Rule 46).

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                               RAZORAGENT MESH PROTOCOL STACK                                │
├─────────────────────────┬───────────────────────────────────────────────────────────────────┤
│ Layer 0: Ingress Shield │ Untrusted Catalog Sanitization (Zero-Width/ANSI/Markdown Filter)   │
│ Layer 1: Discovery      │ Anthropic Model Context Protocol (MCP) JSON-RPC 2.0 Tools         │
│ Layer 2: Negotiation    │ Fiat-Native HTTP 402-INR Micro-Metering + AST Contract State Mach │
│ Layer 3: Resilience     │ Sub-300ms Vector Similarity (Qdrant) + Negative Constraint Filter │
│ Layer 4: Settlement     │ Google AP2 Mandates + NPCI UPI Circle + Razorpay Route Split Rails │
│ Layer 5: Telemetry      │ Real-Time SSE Stream + 13-Route React/Next.js Live Dashboard      │
└─────────────────────────┴───────────────────────────────────────────────────────────────────┘
```

---

## 2. Adversarial Benchmark Matrix (TC-01 → TC-25)

The 10 core protocol scenarios below are implemented under `tests/benchmarkHarness/` with genuine cryptographic and mathematical invariants. Protocol hardening extended the matrix to **TC-25** (ingestion & normalization, bullion & dynamic pricing, Smart Wait & temporal alerts) — see [`GUIDE.md`](./GUIDE.md) for the full mapping:

| Test ID | Scenario Name | Invariants Verified | Assertions & Expected Outcome |
| :--- | :--- | :--- | :--- |
| **TC-01** | Nominal A2A Settlement Handshake | Full happy path: Discovery $\to$ 60s lock $\to$ AP2 Ed25519 signing $\to$ ₹4,200 single-turn settlement. | • `status == "captured"`<br>• `amountPaise == 420000`<br>• `stock == initial - 1` |
| **TC-02** | B2B Multi-Turn Dynamic Negotiation | 3-turn Rubinstein-Ståhl bargaining with monotonic concessions and ₹0.50/turn micro-escrow debit. | • `turns == 3`<br>• `unitPrice == 335000`<br>• `gross == 19765000`<br>• `microFees == 150` |
| **TC-03** | Budget Breach Defense (The Bar) | Cart ₹12,000 vs delegated budget ₹10,000. AP2 Budget Gate intercepts before gateway. | • `BudgetExceededViolation`<br>• `Razorpay API calls: 0`<br>• `₹0 charged` |
| **TC-04** | OOS Vector Self-Healing | SKU-101 OOS auto-substitutes SKU-104 (+₹50) via Qdrant Cosine similarity $\ge 0.85$ in $<300\text{ms}$. | • `healingLatencyMs < 300`<br>• `substitute == "SKU-104"`<br>• `dualSignature == VALID` |
| **TC-05** | Negative Constraint Filtering | Peanut allergen blacklist rejects candidate SKU-201 and selects SKU-205. | • `constraintViolations == 0`<br>• `selected == "SKU-205"` |
| **TC-06** | Anti-Spam Sybil PoW Defense | 100 concurrent spam bids: 1st receives HTTP 402 challenge with PoW; 99 rejected with 402. | • `rejectedSpamCount == 99`<br>• `serverLoad == 0%` |
| **TC-07** | Nonce Replay & Signature Tampering | Replaying consumed nonce after 30s raises `NonceReplayException` (409); payload tampering caught by Ed25519. | • `NonceReplayException`<br>• `SignatureVerificationException` |
| **TC-08** | Float Math Drift Interception | Injected float (e.g. `1976.501`) raises `ArithmeticDriftException`; 100% integer-paise conservation. | • `ArithmeticDriftException`<br>• `mathHallucinations == 0.000%` |
| **TC-09** | Concurrency Double-Spend Lock Race | 2 parallel agents lock last 1 unit simultaneously via Redis Lua. Exactly 1 succeeds, 1 gets 409. | • Agent A: `200 OK`<br>• Agent B: `409 Conflict`<br>• `stock == 0` |
| **TC-10** | Route Split Rollback (2PC) | Secondary split failure triggers 2PC saga compensation via `reverseTransfer()`. | • `reverseTransfer()` executed<br>• `state == VOID`<br>• All splits refunded |

---

## 3. Quickstart & Installation

### Prerequisites
- Docker & Docker Compose
- (Optional for running tests locally: Python 3.13+ and Node.js 22+)

### 1. Launch Full Stack with Docker Compose
From inside `razoragentMesh/`, launch the entire container topology:

```bash
docker compose up --build
```

Services exposed:
- **Telemetry Dashboard & SKU Studio:** [http://localhost:3000](http://localhost:3000)
- **Mandate Settlement Engine API Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Merchant Onboarding & Bullion API Docs:** [http://localhost:4002/docs](http://localhost:4002/docs)
- **x402 Dynamic Negotiation Gateway Docs:** [http://localhost:4003/docs](http://localhost:4003/docs)
- **MCP Discovery Server (JSON-RPC 2.0):** `http://localhost:4001`
- **Qdrant Vector DB Console:** [http://localhost:6333/dashboard](http://localhost:6333/dashboard)
- **Redis Nonce Ledger:** `localhost:6379`

To stop all services:
```bash
docker compose down
```

### 2. Run Test Suites & Invariant Benchmarks (1,545 Tests)
```bash
# Python Backend Core & Python Buyer SDK (1,212 tests)
python -m pytest tests/ packages/buyerSdkPy/tests/ -q --tb=short

# MCP Server Discovery Tools (112 tests)
Push-Location packages/mcpServer; npm test; Pop-Location

# TypeScript Buyer SDK (91 tests)
Push-Location packages/buyerSdkTs; npm test; Pop-Location

# Telemetry Dashboard & SKU Studio (130 tests)
Push-Location packages/telemetryDashboard; npm test; Pop-Location
```

---

## 3.1 Documentation Index

Technical documentation lives in [`packages/telemetryDashboard/docs/`](./packages/telemetryDashboard/docs/)
and is rendered live by the dashboard at `/docs/*`. It is co-located with the service that serves it,
so the Docker build context stays self-contained.

| Document | Live route | Scope |
|---|---|---|
| [`SETUP_GUIDE.md`](./packages/telemetryDashboard/docs/SETUP_GUIDE.md) | `/docs/setup` | Environment, container topology, and local setup |
| [`DEVELOPER_ONBOARDING_GUIDE.md`](./packages/telemetryDashboard/docs/DEVELOPER_ONBOARDING_GUIDE.md) | `/docs/onboarding` | Full protocol topology, merchant onboarding, and buyer-agent lifecycle in TS and Python |
| [`BUYER_AGENT_SDK_GUIDE.md`](./packages/telemetryDashboard/docs/BUYER_AGENT_SDK_GUIDE.md) | `/docs/buyer-sdk` | AI buyer agent SDK and AP2 protocol |
| [`MERCHANT_ONBOARDING_GUIDE.md`](./packages/telemetryDashboard/docs/MERCHANT_ONBOARDING_GUIDE.md) | `/docs/merchant-guide` | Merchant onboarding and the universal SKU Studio |
| [`TELEMETRY_OBSERVABILITY_GUIDE.md`](./packages/telemetryDashboard/docs/TELEMETRY_OBSERVABILITY_GUIDE.md) | `/docs/telemetry` | SSE streaming architecture, KPIs, and the 12 canonical event schemas |
| [`GSTR1_INVOICE_SPECIFICATION.md`](./packages/telemetryDashboard/docs/GSTR1_INVOICE_SPECIFICATION.md) | `/docs/gstr1-invoice` | Statutory GST compliance, integer-paise arithmetic, JCS audit digest |

Architecture and presentation material: [`GUIDE.md`](./GUIDE.md). Completed milestone log:
[`PROJECT.md`](./PROJECT.md).

---

## 4. 5-Minute Interactive Demo Walkthrough

1. **Discovery:** Open Telemetry Dashboard at `http://localhost:3000`. Observe live MCP tool calls (`get_live_sku_quote`) discovering merchant pricing tiers.
2. **Dynamic B2B Negotiation:** Watch the live dual-curve convergence chart as Buyer Agent and Merchant negotiate bulk pricing over 3 turns with ₹0.50 micro-escrow debits.
3. **Cryptographic Mandate Signing:** Inspect the AP2 mandate explorer displaying real-time Ed25519 signature badges for $M_I$, $M_C$, and $M_E$.
4. **OOS Self-Healing:** Trigger an out-of-stock event on SKU-101 and watch the Vector Diff Viewer substitute SKU-104 in $< 300\text{ms}$.
5. **Razorpay Route 2PC Settlement:** Watch the live webhook feed capture payment and execute 3-way split transfers to Merchant, Protocol, and Logistics accounts.
