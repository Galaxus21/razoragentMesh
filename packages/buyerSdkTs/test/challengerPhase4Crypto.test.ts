import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { AgentKeyManager } from "../src/agentKeyManager.js";
import {
  createSignedIntentMandate,
  createSignedCartMandate,
  createSignedExecutionMandate,
  verifyMandateChain
} from "../src/agentMandateBuilder.js";
import {
  ArithmeticDriftException,
  MandateVerificationError,
  CartMandate
} from "../src/types.js";
import { canonicalizeJsonString } from "../src/jcsCanonicalizer.js";

describe("Challenger 1 — Phase 4 Mandate Chain & Arithmetic Drift (buyerSdkTs)", () => {
  const userKeyManager = AgentKeyManager.generate();
  const buyerAgentKeyManager = AgentKeyManager.generate();
  const merchantKeyManager = AgentKeyManager.generate();
  const baseTime = 1720000000;

  const baseIntent = createSignedIntentMandate(
    {
      delegatedAgentDid: buyerAgentKeyManager.getAgentDid(),
      maxBudgetPaise: 500000,
      singleTransactionLimitPaise: 250000,
      upiCircleDelegationToken: "upi_token_challenger_001",
      validUntilTimestamp: baseTime + 7200,
      timestamp: baseTime
    },
    userKeyManager
  );

  const baseCart = createSignedCartMandate(
    {
      merchantGstin: "29AABCU9603R1ZJ",
      merchantStateCode: "29",
      buyerDeliveryPincode: "560001",
      buyerDeliveryStateCode: "29",
      items: [{ skuId: "SKU-TEST-001", quantity: 2, unitPricePaise: 100000, hsnCode: "85044090", gstRatePercent: 18, lineTotalPaise: 200000 }],
      taxableSubtotalPaise: 200000,
      taxBreakdown: { cgstPaise: 18000, sgstPaise: 18000, igstPaise: 0, totalTaxPaise: 36000 },
      totalPaise: 236000,
      inventoryLockToken: "lock_test_001",
      inventoryLockExpiresAt: baseTime + 600,
      timestamp: baseTime
    },
    merchantKeyManager
  );

  const baseExec = createSignedExecutionMandate(
    {
      intentMandate: baseIntent,
      cartMandate: baseCart,
      settlementAmountPaise: 236000,
      upiCircleToken: baseIntent.upiCircleDelegationToken,
      timestamp: baseTime + 30
    },
    buyerAgentKeyManager
  );

  describe("Mandate Chain Verification & Tamper Resistance", () => {
    it("should verify untampered valid mandate chain successfully", () => {
      const isValid = verifyMandateChain(baseIntent, baseCart, baseExec);
      assert.equal(isValid, true);
    });

    it("should reject tampered intent hash with MandateVerificationError", () => {
      const tamperedExec = { ...baseExec, intentMandateHash: "deadbeef" + "0".repeat(56) };
      assert.throws(
        () => verifyMandateChain(baseIntent, baseCart, tamperedExec),
        (err: unknown) => err instanceof MandateVerificationError && err.message.includes("Intent mandate hash mismatch")
      );
    });

    it("should reject tampered cart hash with MandateVerificationError", () => {
      const tamperedExec = { ...baseExec, cartMandateHash: "cafebabe" + "0".repeat(56) };
      assert.throws(
        () => verifyMandateChain(baseIntent, baseCart, tamperedExec),
        (err: unknown) => err instanceof MandateVerificationError && err.message.includes("Cart mandate hash mismatch")
      );
    });

    it("should reject tampered cart item price / total in cart mandate", () => {
      const tamperedCart: CartMandate = { ...baseCart, totalPaise: baseCart.totalPaise + 5000 };
      assert.throws(
        () => verifyMandateChain(baseIntent, tamperedCart, baseExec),
        (err: unknown) => err instanceof MandateVerificationError && err.message.includes("Cart mandate hash mismatch")
      );
    });

    it("should reject budget overspend (cart total > maxBudgetPaise)", () => {
      const tightIntent = createSignedIntentMandate(
        {
          delegatedAgentDid: buyerAgentKeyManager.getAgentDid(),
          maxBudgetPaise: 200000,
          singleTransactionLimitPaise: 250000,
          upiCircleDelegationToken: "upi_token_tight_001",
          validUntilTimestamp: baseTime + 7200,
          timestamp: baseTime
        },
        userKeyManager
      );

      const execTight = createSignedExecutionMandate(
        { intentMandate: tightIntent, cartMandate: baseCart, settlementAmountPaise: 236000, upiCircleToken: tightIntent.upiCircleDelegationToken, timestamp: baseTime + 30 },
        buyerAgentKeyManager
      );

      assert.throws(
        () => verifyMandateChain(tightIntent, baseCart, execTight),
        (err: unknown) => err instanceof MandateVerificationError && err.message.includes("exceeds intent max budget")
      );
    });

    it("should reject transaction limit overspend (cart total > singleTransactionLimitPaise)", () => {
      const lowLimitIntent = createSignedIntentMandate(
        {
          delegatedAgentDid: buyerAgentKeyManager.getAgentDid(),
          maxBudgetPaise: 500000,
          singleTransactionLimitPaise: 150000,
          upiCircleDelegationToken: "upi_token_low_limit_001",
          validUntilTimestamp: baseTime + 7200,
          timestamp: baseTime
        },
        userKeyManager
      );

      const execLowLimit = createSignedExecutionMandate(
        { intentMandate: lowLimitIntent, cartMandate: baseCart, settlementAmountPaise: 236000, upiCircleToken: lowLimitIntent.upiCircleDelegationToken, timestamp: baseTime + 30 },
        buyerAgentKeyManager
      );

      assert.throws(
        () => verifyMandateChain(lowLimitIntent, baseCart, execLowLimit),
        (err: unknown) => err instanceof MandateVerificationError && err.message.includes("exceeds single transaction limit")
      );
    });

    it("should reject expired mandate (execution timestamp > validUntilTimestamp)", () => {
      const expiredExec = createSignedExecutionMandate(
        { intentMandate: baseIntent, cartMandate: baseCart, settlementAmountPaise: 236000, upiCircleToken: baseIntent.upiCircleDelegationToken, timestamp: baseIntent.validUntilTimestamp + 100 },
        buyerAgentKeyManager
      );

      assert.throws(
        () => verifyMandateChain(baseIntent, baseCart, expiredExec),
        (err: unknown) => err instanceof MandateVerificationError && err.message.includes("Intent mandate expired")
      );
    });
  });

  describe("Zero Float Drift (INV-01) & Integer Paise Enforcement", () => {
    it("should reject all non-integer inputs in JCS canonicalization and mandate building", () => {
      assert.throws(
        () =>
          createSignedIntentMandate(
            {
              delegatedAgentDid: buyerAgentKeyManager.getAgentDid(),
              maxBudgetPaise: 1000.5,
              singleTransactionLimitPaise: 500,
              upiCircleDelegationToken: "upi_tok"
            },
            userKeyManager
          ),
        (err: unknown) => err instanceof ArithmeticDriftException
      );

      assert.throws(
        () => canonicalizeJsonString({ invalidPaise: 123.456 }),
        (err: unknown) => err instanceof ArithmeticDriftException
      );
    });
  });
});
