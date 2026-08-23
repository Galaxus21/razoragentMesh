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
│ Layer 5: Telemetry      │ Real-Time SSE Stream + 5-Panel React/Next.js Live Dashboard       │
└─────────────────────────┴───────────────────────────────────────────────────────────────────┘
```

---

## 2. 10-Scenario Adversarial Benchmark Matrix

All 10 benchmark scenarios are implemented under `tests/benchmarkHarness/` with genuine cryptographic and mathematical invariants:

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
- Python 3.13+ (or 3.11+)
- Node.js 22+ LTS
- Docker & Docker Compose

### 1. Clone & Configure Environment
```bash
cp .env.example .env
```

### 2. Run Test Suite & Benchmark Harness
```bash
# Run all 10 adversarial benchmark scenarios
python -m pytest tests/benchmarkHarness/ -v

# Run multi-layer end-to-end integration tests
python -m pytest tests/integration/ -v
```

### 3. One-Command Docker Startup
```bash
docker-compose up --build
```

Services exposed:
- **Telemetry Dashboard:** `http://localhost:3000`
- **Mandate Settlement Engine:** `http://localhost:8000`
- **MCP Server:** `http://localhost:4001`
- **Qdrant Vector DB:** `http://localhost:6333`
- **Redis Nonce Ledger:** `localhost:6379`

---

## 4. 5-Minute Interactive Demo Walkthrough

1. **Discovery:** Open Telemetry Dashboard at `http://localhost:3000`. Observe live MCP tool calls (`get_live_sku_quote`) discovering merchant pricing tiers.
2. **Dynamic B2B Negotiation:** Watch the live dual-curve convergence chart as Buyer Agent and Merchant negotiate bulk pricing over 3 turns with ₹0.50 micro-escrow debits.
3. **Cryptographic Mandate Signing:** Inspect the AP2 mandate explorer displaying real-time Ed25519 signature badges for $M_I$, $M_C$, and $M_E$.
4. **OOS Self-Healing:** Trigger an out-of-stock event on SKU-101 and watch the Vector Diff Viewer substitute SKU-104 in $< 300\text{ms}$.
5. **Razorpay Route 2PC Settlement:** Watch the live webhook feed capture payment and execute 3-way split transfers to Merchant, Protocol, and Logistics accounts.
