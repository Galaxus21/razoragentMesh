# Project: RazorAgent Mesh Refactoring

> **Status: COMPLETED MILESTONE RECORD (M1–M5).** This is the work log for the math-isolation,
> durable-DLQ, GSTIN-validation, and property-test milestones — all delivered. It is kept for
> traceability, not as a live architecture reference.
>
> For the current architecture see [`GUIDE.md`](./GUIDE.md); for the ongoing knowledge graph see
> [`../.agents/rules/project-knowledge-base.md`](../.agents/rules/project-knowledge-base.md).

## Architecture
RazorAgent Mesh is a production-grade autonomous agent commerce mesh consisting of:
- **Layer 1: Merchant Ingestion & Onboarding** (`packages/merchantApi`) — Merchant registrar, catalog indexing, vector search, GSTIN verification.
- **Layer 2: x402 Gateway & Negotiation** (`packages/x402Gateway`) — Proof-of-work challenge, micro-escrow, and Rubinstein-Ståhl bilateral bargaining FSM.
- **Layer 3: Vector Self-Healing** (`packages/vectorHealer`) — Out-of-stock autonomous healing and SKU substitution.
- **Layer 4: Mandate Engine & 2PC Settlement** (`packages/mandateEngine`) — Cryptographic mandate verification (Ed25519 JCS), statutory tax breakdown, and two-phase commit (2PC) distributed settlement saga with Razorpay Route.
- **Client SDKs** (`packages/buyerSdkPy`, `packages/buyerSdkTs`) — Standalone buyer agents. Zero-drift integer-paise arithmetic lives in the `mandateEngine` arithmetic enclave, not a separate package.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Math Isolation & Zero-Drift Arithmetic | Consolidate integer-paise math, GST/TCS split logic, and ArithmeticDriftException | M1 (DONE) | Prior Work |
| 2 | Durable Compensation Event Schema | Frozen immutable Pydantic model for 2PC compensation failures | M2 | Survey / R1 |
| 3 | Redis-Backed Compensation DLQ | Queue manager for enqueuing failed reversals and managing dead letter queue | M2 | Survey / R1 |
| 4 | Asynchronous DLQ Worker | Background worker with exponential backoff and idempotency keys for eventual compensation | M2 | Survey / R1 |
| 5 | 2PC Saga DLQ Integration | Replace sync rollback abort in TwoPhaseCommitSaga with durable DLQ push on reversal error | M2 | Survey / R1 |
| 6 | Canonical GSTIN Mod-36 Validator | Radix-36 Luhn check-digit computation and validation in mandate engine | M3 | Survey / R2 |
| 7 | CartMandate Pydantic @field_validator | Enforce statutory GSTIN format and Luhn Mod-36 checksum before signature & settlement | M3 | Survey / R2 |
| 8 | Test Fixture GSTIN Alignment | Align mock merchant GSTINs to valid check digits while asserting bad digit rejection | M3 | Survey / R2 |
| 9 | Hypothesis & Fast-Check Dependencies | Add hypothesis to Python packages and fast-check to TypeScript package configurations | M4 | DONE |
| 10 | Property Test: Zero-Drift Conservation | Hypothesis & fast-check suites verifying cgst + sgst == total_gst and bill split invariance | M4 | DONE |
| 11 | Property Test: Monotonic Negotiation | Hypothesis suite verifying Rubinstein-Ståhl FSM rejects any non-monotonic bid sequence | M4 | DONE |
| 12 | Property Test: Luhn Mod-36 Invariants | Hypothesis suite verifying valid GSTIN roundtrip and single-char mutation falsification | M4 | DONE |
| 13 | Property Test: Ed25519 JCS Canonical Invariants | Hypothesis & fast-check suites verifying canonical JCS ordering, sign/verify, and float ban | M4 | DONE |
| 14 | Standardize Vector Payload Schema Naming | Consistent O(1) in-place Qdrant payload patching standardized to `in_stock` field | M5 | DONE |
| 15 | Comprehensive Monorepo Regression Gate | Verify all 1,564 tests and new property test suites pass with zero regressions | M5 | DONE |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Math Isolation (Prior Work) | Integer paise arithmetic consolidation in enclaveMath | None | DONE |
| 2 | Failure Recovery (Durable DLQ) | Redis-backed DLQ, CompensationEvent, Async Worker, 2PC Saga integration | M1 | DONE |
| 3 | Statutory Compliance (GSTIN Validation) | Canonical Luhn Mod-36 validator, CartMandate @field_validator | M1 | DONE |
| 4 | Property-Based Test Suite | Hypothesis & fast-check suites for zero-drift, FSM, Luhn, and Ed25519 JCS | M2, M3 | DONE |
| 5 | Full Monorepo Test & Acceptance Gate | Monorepo test execution across Python and TypeScript packages | M4 | DONE |

## Interface Contracts
### 1. Compensation DLQ (`packages/mandateEngine/settlement/compensationDlq.py`)
- `CompensationEvent`: Frozen Pydantic model (`eventId`, `idempotencyKey`, `transferId`, `amountPaise`, `recipientAccountId`, `paymentId`, `reason`, `retryCount`, `maxRetries`, `status`, `createdAt`, `metadata`).
- `CompensationDlq`:
  - `enqueueReversal(transferId: str, amountPaise: int, recipientAccountId: Optional[str], paymentId: Optional[str], reason: str, metadata: Optional[dict] = None) -> CompensationEvent`
  - `isAlreadyCompensated(transferId: str) -> bool`
  - `markCompensated(transferId: str, reversalId: Optional[str] = None) -> None`
  - `popPendingEvent() -> Optional[CompensationEvent]`
  - `escalateToDeadLetter(event: CompensationEvent) -> None`
- `CompensationDlqWorker`:
  - `processNext() -> Optional[CompensationEvent]`
  - `processAllPending() -> int`
  - `runWorkerLoop(pollIntervalSeconds: float = 1.0, stopEvent: Optional[asyncio.Event] = None)`
  - Backoff: `initialBackoffSeconds * (backoffMultiplier ** (retryCount - 1))`

### 2. GSTIN Validation (`packages/mandateEngine/tax/gstinValidator.py` & `cartMandateSchema.py`)
- `validateGstin(gstin: str) -> bool`: Validates 15-character statutory format and Luhn Mod-36 check character.
- `computeGstinChecksum(gstin14: str) -> str`: Computes the 15th check character for a 14-character GSTIN prefix.
- `CartMandate.validate_merchant_gstin(cls, v: str) -> str`: Pydantic `@field_validator("merchantGstin")` raising `ValueError("Invalid Indian GSTIN: failed format or Luhn Mod-36 checksum verification")`.

### 3. Property Test Suites (`tests/property/` & `packages/buyerSdkTs/test/`)
- `tests/property/test_property_enclave_math.py`: Hypothesis suite for zero-drift paise conservation.
- `tests/property/test_property_negotiation_fsm.py`: Hypothesis suite for Rubinstein-Ståhl monotonicity.
- `tests/property/test_property_gstin_luhn.py`: Hypothesis suite for Luhn Mod-36 roundtrip & mutation falsification.
- `tests/property/test_property_jcs_ed25519.py`: Hypothesis suite for Ed25519 canonical JCS signature invariants & float rejection.
- `packages/buyerSdkTs/test/propertyBased.test.ts`: Fast-check suite for TS JCS canonicalization and Ed25519 signature invariants.

## Code Layout
- `packages/mandateEngine/settlement/compensationDlq.py` — DLQ event, queue manager, and async worker.
- `packages/mandateEngine/settlement/twoPhaseCommitSaga.py` — 2PC saga with DLQ compensation.
- `packages/mandateEngine/settlement/razorpayRouteClient.py` — Route client with reversal failure simulation.
- `packages/mandateEngine/tax/gstinValidator.py` — Canonical Luhn Mod-36 GSTIN validator.
- `packages/mandateEngine/mandates/cartMandateSchema.py` — CartMandate schema with `@field_validator("merchantGstin")`.
- `packages/merchantApi/src/onboarding/merchantRegistrar.py` — Re-exports or leverages canonical validator.
- `tests/unit/testCompensationDlq.py` — Unit tests for DLQ event, queue, worker, idempotency, backoff.
- `tests/unit/testCartMandateGstinValidation.py` — Unit tests for CartMandate GSTIN validation.
- `tests/property/` — Hypothesis property-based test suites.
- `packages/buyerSdkTs/test/propertyBased.test.ts` — fast-check property-based test suite.
