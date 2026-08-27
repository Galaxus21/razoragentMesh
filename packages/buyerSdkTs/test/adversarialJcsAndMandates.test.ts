import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  canonicalizeJsonString,
  canonicalizeJson,
  computeSha256Digest,
  canonicalizeAndHash
} from "../src/jcsCanonicalizer.js";
import { AgentKeyManager } from "../src/agentKeyManager.js";
import {
  computeMandateHash,
  createSignedIntentMandate,
  createSignedCartMandate,
  createSignedExecutionMandate,
  createSignedAmendmentMandate,
  verifyMandateChain
} from "../src/agentMandateBuilder.js";
import { ArithmeticDriftException, MandateVerificationError } from "../src/types.js";

describe("JCS Canonicalization & Mandate Invariants Adversarial Suite", () => {
  const userKeyManager = AgentKeyManager.generate();
  const agentKeyManager = AgentKeyManager.generate();
  const merchantKeyManager = AgentKeyManager.generate();

  it("should defensively reject all float variants and special number values", () => {
    // Basic floats
    assert.throws(() => canonicalizeJsonString({ amount: 99.99 }), (e: unknown) => e instanceof ArithmeticDriftException);
    assert.throws(() => canonicalizeJsonString({ amount: 0.0001 }), (e: unknown) => e instanceof ArithmeticDriftException);
    assert.throws(() => canonicalizeJsonString({ amount: -0.5 }), (e: unknown) => e instanceof ArithmeticDriftException);

    // Deep nested floats
    assert.throws(
      () => canonicalizeJsonString({ a: { b: [{ c: 1.1 }] } }),
      (e: unknown) => e instanceof ArithmeticDriftException
    );

    // Special IEEE-754 numbers
    assert.throws(() => canonicalizeJsonString({ nanVal: Number.NaN }), (e: unknown) => e instanceof ArithmeticDriftException);
    assert.throws(() => canonicalizeJsonString({ infVal: Number.POSITIVE_INFINITY }), (e: unknown) => e instanceof ArithmeticDriftException);
    assert.throws(() => canonicalizeJsonString({ negInf: Number.NEGATIVE_INFINITY }), (e: unknown) => e instanceof ArithmeticDriftException);

    // Non-integer exponential notation
    assert.throws(() => canonicalizeJsonString({ expFloat: 1.25e1 }), (e: unknown) => e instanceof ArithmeticDriftException);

    // Set and Map floats
    assert.throws(() => canonicalizeJsonString({ tags: new Set([10.5]) }), (e: unknown) => e instanceof ArithmeticDriftException);
    assert.throws(() => canonicalizeJsonString({ nestedSet: new Set([new Set([10.5])]) }), (e: unknown) => e instanceof ArithmeticDriftException);
    assert.throws(() => canonicalizeJsonString({ mapVal: new Map([["key", 10.5]]) }), (e: unknown) => e instanceof ArithmeticDriftException);
    assert.throws(() => canonicalizeJsonString({ mapKey: new Map([[10.5, "val"]]) }), (e: unknown) => e instanceof ArithmeticDriftException);
  });

  it("should accept valid integer paise numbers and deep nested structures", () => {
    const complexPayload = {
      zebra: 100,
      apple: 0,
      negativeInt: -50,
      nested: {
        charlie: [3, 2, 1],
        bravo: { delta: 999 }
      },
      tags: new Set(["beta", "alpha"]),
      unicodeField: "Razorpay ⚡ Autonomous Agent"
    };

    const canonicalString = canonicalizeJsonString(complexPayload);
    assert.ok(canonicalString.startsWith('{"apple":0,'));
    assert.ok(canonicalString.includes('"tags":["alpha","beta"]'));
    assert.ok(canonicalString.includes('"charlie":[3,2,1]'));
  });

  it("should enforce integer budget ceiling and transaction limit rules in IntentMandate", () => {
    // Zero budget
    assert.throws(
      () =>
        createSignedIntentMandate(
          {
            delegatedAgentDid: agentKeyManager.getAgentDid(),
            maxBudgetPaise: 0,
            singleTransactionLimitPaise: 50000,
            upiCircleDelegationToken: "upi_tok_1"
          },
          userKeyManager
        ),
      (e: unknown) => e instanceof ArithmeticDriftException
    );

    // Negative budget
    assert.throws(
      () =>
        createSignedIntentMandate(
          {
            delegatedAgentDid: agentKeyManager.getAgentDid(),
            maxBudgetPaise: -1000,
            singleTransactionLimitPaise: 50000,
            upiCircleDelegationToken: "upi_tok_1"
          },
          userKeyManager
        ),
      (e: unknown) => e instanceof ArithmeticDriftException
    );

    // Zero limit
    assert.throws(
      () =>
        createSignedIntentMandate(
          {
            delegatedAgentDid: agentKeyManager.getAgentDid(),
            maxBudgetPaise: 50000,
            singleTransactionLimitPaise: 0,
            upiCircleDelegationToken: "upi_tok_1"
          },
          userKeyManager
        ),
      (e: unknown) => e instanceof ArithmeticDriftException
    );

    // Negative limit
    assert.throws(
      () =>
        createSignedIntentMandate(
          {
            delegatedAgentDid: agentKeyManager.getAgentDid(),
            maxBudgetPaise: 50000,
            singleTransactionLimitPaise: -500,
            upiCircleDelegationToken: "upi_tok_1"
          },
          userKeyManager
        ),
      (e: unknown) => e instanceof ArithmeticDriftException
    );
  });

  it("should enforce CartMandate non-empty items constraint", () => {
    assert.throws(
      () =>
        createSignedCartMandate(
          {
            merchantGstin: "29AABCU9603R1ZJ",
            merchantStateCode: "29",
            buyerDeliveryPincode: "560001",
            buyerDeliveryStateCode: "29",
            items: [],
            taxableSubtotalPaise: 0,
            taxBreakdown: { cgstPaise: 0, sgstPaise: 0, igstPaise: 0, totalTaxPaise: 0 },
            totalPaise: 0,
            inventoryLockToken: "lock_0",
            inventoryLockExpiresAt: 1700000000
          },
          merchantKeyManager
        ),
      /Cart must contain at least one item/
    );
  });

  it("should verify mandate chain boundaries and failure conditions exhaustively", () => {
    const baseTimestamp = 1700000000;
    const intentMandate = createSignedIntentMandate(
      {
        delegatedAgentDid: agentKeyManager.getAgentDid(),
        maxBudgetPaise: 100000,
        singleTransactionLimitPaise: 50000,
        upiCircleDelegationToken: "upi_tok_chain_001",
        validUntilTimestamp: baseTimestamp + 3600,
        timestamp: baseTimestamp
      },
      userKeyManager
    );

    const cartMandate = createSignedCartMandate(
      {
        merchantGstin: "29AABCU9603R1ZJ",
        merchantStateCode: "29",
        buyerDeliveryPincode: "560001",
        buyerDeliveryStateCode: "29",
        items: [
          {
            skuId: "SKU-CHAIN-1",
            quantity: 1,
            unitPricePaise: 40000,
            hsnCode: "8504",
            gstRatePercent: 18,
            lineTotalPaise: 40000
          }
        ],
        taxableSubtotalPaise: 40000,
        taxBreakdown: { cgstPaise: 3600, sgstPaise: 3600, igstPaise: 0, totalTaxPaise: 7200 },
        totalPaise: 47200,
        inventoryLockToken: "lock_chain_001",
        inventoryLockExpiresAt: baseTimestamp + 300,
        timestamp: baseTimestamp
      },
      merchantKeyManager
    );

    const executionMandate = createSignedExecutionMandate(
      {
        intentMandate,
        cartMandate,
        settlementAmountPaise: 47200,
        upiCircleToken: intentMandate.upiCircleDelegationToken,
        timestamp: baseTimestamp + 10
      },
      agentKeyManager
    );

    // Valid chain
    assert.equal(verifyMandateChain(intentMandate, cartMandate, executionMandate), true);

    // Intent hash mismatch
    const tamperedExecIntentHash = { ...executionMandate, intentMandateHash: "0".repeat(64) };
    assert.throws(
      () => verifyMandateChain(intentMandate, cartMandate, tamperedExecIntentHash),
      (e: unknown) => e instanceof MandateVerificationError && e.message.includes("Intent mandate hash mismatch")
    );

    // Cart hash mismatch
    const tamperedExecCartHash = { ...executionMandate, cartMandateHash: "0".repeat(64) };
    assert.throws(
      () => verifyMandateChain(intentMandate, cartMandate, tamperedExecCartHash),
      (e: unknown) => e instanceof MandateVerificationError && e.message.includes("Cart mandate hash mismatch")
    );

    // Settlement amount mismatch
    const tamperedExecAmount = {
      ...executionMandate,
      settlementAmountPaise: 40000,
      agentSignature: agentKeyManager.signPayload({
        ...executionMandate,
        settlementAmountPaise: 40000
      })
    };
    assert.throws(
      () => verifyMandateChain(intentMandate, cartMandate, tamperedExecAmount),
      (e: unknown) => e instanceof MandateVerificationError && e.message.includes("Settlement amount")
    );

    // Cart total exceeds single transaction limit
    const excessiveLimitCart = { ...cartMandate, totalPaise: 55000 };
    const excessiveLimitExec = {
      ...executionMandate,
      cartMandateHash: computeMandateHash(excessiveLimitCart as unknown as Record<string, unknown>),
      settlementAmountPaise: 55000
    };
    assert.throws(
      () => verifyMandateChain(intentMandate, excessiveLimitCart, excessiveLimitExec),
      (e: unknown) => e instanceof MandateVerificationError && e.message.includes("single transaction limit")
    );

    // Cart total exceeds max budget
    const lowBudgetIntent = { ...intentMandate, maxBudgetPaise: 40000, singleTransactionLimitPaise: 50000 };
    const lowBudgetExec = {
      ...executionMandate,
      intentMandateHash: computeMandateHash(lowBudgetIntent as unknown as Record<string, unknown>)
    };
    assert.throws(
      () => verifyMandateChain(lowBudgetIntent, cartMandate, lowBudgetExec),
      (e: unknown) => e instanceof MandateVerificationError && e.message.includes("exceeds intent max budget")
    );

    // Expired intent mandate
    const expiredExec = {
      ...executionMandate,
      timestamp: intentMandate.validUntilTimestamp + 1
    };
    assert.throws(
      () => verifyMandateChain(intentMandate, cartMandate, expiredExec),
      (e: unknown) => e instanceof MandateVerificationError && e.message.includes("Intent mandate expired")
    );
  });
});
