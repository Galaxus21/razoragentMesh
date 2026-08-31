# 🚀 RazorAgent Mesh: Autonomous Settlement Protocol for Agentic Commerce

> **Track 01:** AI Growth & Agentic Commerce (Razorpay AI Buildathon 2026)  
> **Author:** Shubham Verma  
> **Target Program:** Razorpay AI Builder Internship (Bangalore HQ)  
> **Status:** Production Architecture (Version 2.0 Hardened)

---

## 1. Executive Overview

**RazorAgent Mesh** is the **"Stripe for the Autonomous Agentic Economy"** — an end-to-end, machine-to-machine (M2M) commerce and settlement protocol built natively on Razorpay rails.

As autonomous AI agents (enterprise procurement bots, ERP replenishment loops, and consumer AI assistants) replace human shoppers, existing HTML checkouts and manual 2FA become insurmountable friction points. RazorAgent Mesh provides a 6-layer autonomous commerce protocol with **bounded cryptographic safety**, **zero floating-point math drift**, and **100% Indian regulatory compliance** (RBI 2FA / NPCI UPI Circle / GST Rule 46).

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

The 10 core protocol scenarios below live under `tests/benchmarkHarness/`. Seven exercise real production code; three (TC-05, TC-06, TC-09) reimplement their subject and are listed under Known limitations rather than counted as evidence. Protocol hardening extended the matrix to **TC-25** (ingestion & normalization, bullion & dynamic pricing, Smart Wait & temporal alerts) — see [`GUIDE.md`](./GUIDE.md) for the full mapping:

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
- **MCP Discovery Server:** two transports. MCP JSON-RPC 2.0 over **stdio** for agent runtimes,
  and a **REST adapter on [http://localhost:4001](http://localhost:4001)** (`/health`,
  `/api/v1/tools`, `/api/v1/quote`, `/api/v1/lock`, `/api/v1/sla`) for the buyer SDKs, whose
  calls are plain HTTP. To exercise the stdio transport directly:

  ```bash
  echo '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | docker run -i --rm razoragent_mcp_server:latest node dist/mcpServerMain.js
  ```
- **Qdrant Vector DB Console:** [http://localhost:6333/dashboard](http://localhost:6333/dashboard)
- **Redis Nonce Ledger:** `localhost:6379`

Nothing else is required. A one-shot `catalog-seeder` service loads
`tests/fixtures/catalogFixtures.json` into Redis and Qdrant once both report healthy, and
`merchant-api` waits for it to exit 0 — so the stack never comes up against an empty catalog.
Every service declares a healthcheck, and the dashboard starts only once all four report healthy.

**Catalog contents.** Two sets of SKUs are live, and both are quotable through the same path:

| Source | Example ids | Where they come from |
|---|---|---|
| Compiled fixtures | `SKU-LAPTOP-101`, `SKU-CHAIR-001`, `SKU-OIL-201` | `packages/mcpServer/src/catalog/catalogFixtures.ts`, baked into the image |
| Seeded catalog | `SKU-001`, `SKU-101`, `SKU-201` | `tests/fixtures/catalogFixtures.json`, loaded by `catalog-seeder` |

The MCP server reads `mesh:catalog:*` out of Redis at startup and merges it over the compiled
fixtures, then follows the `mesh:catalog:updates` channel for later changes. So a SKU published
through the Merchant Studio survives a restart, and a seeded SKU is quotable immediately.

A live quote, against the running stack:

```bash
curl "http://localhost:4001/api/v1/quote?skuId=SKU-LAPTOP-101&quantity=2&deliveryPincode=560001&buyerAgentDid=did:agent:demo.buyer.001"
```

`buyerAgentDid` must match `^did:agent:[a-z0-9_.:-]+$`; the quote tool returns HTTP 422 otherwise.

To stop all services:
```bash
docker compose down
```

To stop them and discard the seeded catalog as well:
```bash
docker compose down -v
```

### 2. Run Test Suites & Invariant Benchmarks

The load-bearing evidence is not the size of the suite. It is these three things, which
run in about a minute:

```bash
# 10 adversarial benchmark scenarios TC-01..TC-10, one per failure mode (19 tests)
python -m pytest tests/benchmarkHarness/ -v

# 30 property-based invariants under Hypothesis (enclave math, GSTIN Luhn, JCS/Ed25519, negotiation FSM)
python -m pytest tests/property/ -v

# 12 golden GST vectors asserted against BOTH the Python enclave and the TypeScript
# pricing engine in one test -- the TS half runs in a real node subprocess
python -m pytest tests/testCrossSdkTsPyCompatibility.py -v
```

Then the full matrix:

```bash
python -m pytest tests/ packages/buyerSdkPy/tests/ -q --tb=short
Push-Location packages/mcpServer; npm test; Pop-Location
Push-Location packages/buyerSdkTs; npm test; Pop-Location
Push-Location packages/telemetryDashboard; npm test; Pop-Location
```

<!-- testcounts:start -->
<!-- Generated by scripts/countTests.py -- do not edit by hand. -->

| Suite | Tests | Command that produced this number |
|---|---:|---|
| Python backend + Python Buyer SDK | 1252 | `python -m pytest tests/ packages/buyerSdkPy/tests/ --collect-only -q` |
| MCP discovery server | 133 | `cd packages/mcpServer && npm test` |
| TypeScript Buyer SDK | 94 | `cd packages/buyerSdkTs && npm test` |
| Telemetry dashboard + SKU Studio | 258 | `cd packages/telemetryDashboard && npm test` |
| **Total** | **1,737** | `python scripts/countTests.py` |

<!-- testcounts:end -->

### Continuous integration

`.github/workflows/ci.yml` runs five jobs on every push. Three of them exist to stop this README
from lying:

| Job | What it fails on |
|---|---|
| `python` | Backend and Python SDK suites |
| `typescript` | Type check and test the MCP server, TypeScript SDK and dashboard |
| `claims` | A stale cross-language GST formula in the docs, or a statutory constant with no citation |
| `docs` | A guide naming a method, argument, port, route or example region the code does not have; a stale generated reference; an example that fails to compile or run |
| `test-counts` | A documented test count that disagrees with measurement |

The `docs` job also *executes* `examples/typescript/mandateChain.ts` and
`examples/python/mandateChain.py`, which build a full AP2 mandate chain, verify it, edit the cart,
and exit non-zero unless the first verifies and the second is refused.

Every number in that table is produced by `python scripts/countTests.py`, which CI runs
with `--check` so the table cannot drift from measurement (rule V-01). Treat the total as
inventory, not as evidence: a statutory GST bug in this repository survived 1,545 of these
tests, because no test compared the two implementations against each other. The benchmarks,
property invariants, and cross-language vectors above are what actually constrain behaviour.

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

Repository-level documentation not served by the dashboard:

| Document | Scope |
|---|---|
| [`docs/STATUTORY_RATES.md`](./docs/STATUTORY_RATES.md) | Where tax rates live, their citations and verification dates, and the procedure for keeping them true |
| [`GUIDE.md`](./GUIDE.md) | Architecture and presentation material |
| [`PROJECT.md`](./PROJECT.md) | Completed milestone log |

---

## 4. 5-Minute Interactive Demo Walkthrough

1. **Discovery:** Open Telemetry Dashboard at `http://localhost:3000`. Observe live MCP tool calls (`get_live_sku_quote`) discovering merchant pricing tiers.
2. **Dynamic B2B Negotiation:** Watch the live dual-curve convergence chart as Buyer Agent and Merchant negotiate bulk pricing over 3 turns with ₹0.50 micro-escrow debits.
3. **Cryptographic Mandate Signing:** Inspect the AP2 mandate explorer displaying real-time Ed25519 signature badges for $M_I$, $M_C$, and $M_E$.
4. **OOS Self-Healing:** Trigger an out-of-stock event on SKU-101 and watch the Vector Diff Viewer substitute SKU-104 in $< 300\text{ms}$.
5. **Razorpay Route 2PC Settlement:** Watch the live webhook feed capture payment and execute 3-way split transfers to Merchant, Protocol, and Logistics accounts.

---

## 5. Scope & Limitations

This is a protocol prototype built for the Razorpay AI Buildathon, not a production payments
system. The boundaries below are deliberate engineering choices made to keep the protocol layer
the focus, and they are stated here so they read as decisions rather than oversights.

### Deliberately out of scope

**No authentication or authorization on the HTTP surface.** Merchant routes
(`POST/PUT/DELETE` on catalog, policy, bulk-ingest, registration) are open, and merchant
identity is a path parameter. Anyone who can reach the API can mutate any merchant's catalog.
Production would need API keys or mTLS plus per-merchant authorization; the *agent-facing*
settlement path is separately protected by Ed25519 mandate verification and AP2 delegation
binding, which is where the protocol's security claims actually live.

**No rate limiting or anti-abuse on the merchant API.** The x402 gateway does implement
proof-of-work and micro-escrow for agent negotiation, but the merchant surface has neither.

**Single-tenant assumptions.** There is no tenant isolation in Redis keyspaces or Qdrant
collections beyond naming conventions.

**Razorpay integration runs in mock mode by default.** `RazorpayRouteClient(isMockMode=True)`
simulates capture, transfer and reversal. The live HTTP path exists and is exercised by tests,
but the demo does not move real money.

### Known limitations of what *is* implemented

**TCS rates are not effective-dated.** Section 52 rates are a single set of constants reflecting
the rate currently in force (0.5% per Notification 15/2024-Central Tax). Reissuing an invoice
for a supply made before 10 July 2024 would apply today's rate rather than the rate in force on
the supply date. See [docs/STATUTORY_RATES.md](docs/STATUTORY_RATES.md).

**The cumulative budget cap fails open.** If Redis is unavailable, `SettlementLedger` logs a
warning and allows the settlement rather than blocking it — a deliberate choice so that a
degraded cache cannot halt a live demo. Production should fail closed.

**Test coverage is mock-backed.** The suite runs against `fakeredis` and in-process doubles for
Qdrant and Razorpay. It verifies protocol logic thoroughly; it does not verify real
infrastructure behaviour under failure.

**Settlement has only ever run in mock mode.** `RazorpayRouteClient` accepts `apiKey`,
`apiSecret` and `isMockMode`, but both places the application constructs it pass
`isMockMode=True` literally and no credentials, and nothing reads the `RAZORPAY_KEY_ID` /
`RAZORPAY_KEY_SECRET` that `docker-compose.yml` sets. Every settlement this repository has
executed went through the mock ledger, and no environment variable can change that. The 2PC saga,
compensation and invoicing around it are real.

**Three benchmark files assert their own reimplementations.**
`testTc05NegativeConstraint.py`, `testTc06AntiSpamSybil.py` and `testTc09ConcurrencyDoubleLock.py`
import no production module at all -- they define the subsystem under test and then exercise that
definition, so they would pass unchanged if `packages/` were deleted. `tests/unit/testBenchmarkHarnessIntegrity.py`
freezes the count at three so a fourth cannot appear. The other benchmarks do import real code.

**The idempotency header name is provider-specific and unverified.**
`headerIdempotencyKey` in `razorpayRouteClient.py` must be confirmed against the current
Razorpay API reference before live use. The mechanism is correct regardless of the header
string.

### Where the engineering effort actually went

Integer-paise arithmetic with no floating point in any monetary path; RFC 8785 JCS
canonicalization verified byte-identical across the Python and TypeScript SDKs; statutory GST
computed so CGST and SGST are equal by construction; AP2 mandate chain verification with
delegation binding, cumulative budget enforcement and cart replay defence; and a 2PC settlement
saga with durable Redis-backed compensation.
