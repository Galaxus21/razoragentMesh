import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { AgentKeyManager } from "../src/agentKeyManager.js";
import {
  computeMandateHash,
  createSignedIntentMandate,
  createSignedCartMandate,
  createSignedExecutionMandate,
  verifyMandateChain
} from "../src/agentMandateBuilder.js";
import { MandateVerificationError } from "../src/types.js";

function buildMandateTestFixtures(userKm: AgentKeyManager, agentKm: AgentKeyManager, merchantKm: AgentKeyManager) {
  const intentMandate = createSignedIntentMandate(
    { delegatedAgentDid: agentKm.getAgentDid(), maxBudgetPaise: 500000, singleTransactionLimitPaise: 500000, upiCircleDelegationToken: "upi_tok_001" },
    userKm
  );

  const cartMandate = createSignedCartMandate(
    {
      merchantGstin: "29AABCU9603R1ZJ",
      merchantStateCode: "29",
      buyerDeliveryPincode: "560001",
      buyerDeliveryStateCode: "29",
      items: [{ skuId: "SKU-001", quantity: 1, unitPricePaise: 100000, hsnCode: "8504", gstRatePercent: 18, lineTotalPaise: 100000 }],
      taxableSubtotalPaise: 100000,
      taxBreakdown: { cgstPaise: 9000, sgstPaise: 9000, igstPaise: 0, totalTaxPaise: 18000 },
      totalPaise: 118000,
      inventoryLockToken: "lock_001",
      inventoryLockExpiresAt: 2000000000
    },
    merchantKm
  );

  const executionMandate = createSignedExecutionMandate(
    { intentMandate, cartMandate, settlementAmountPaise: cartMandate.totalPaise, upiCircleToken: intentMandate.upiCircleDelegationToken },
    agentKm
  );

  return { intentMandate, cartMandate, executionMandate };
}

describe("AgentMandateBuilder — Mandate Verification & Hash Invariants", () => {
  const userKeyManager = AgentKeyManager.generate();
  const agentKeyManager = AgentKeyManager.generate();
  const merchantKeyManager = AgentKeyManager.generate();

  it("should strip signatures when computing mandate hash", () => {
    const intentA = createSignedIntentMandate(
      {
        mandateId: "M-SAME",
        delegatedAgentDid: agentKeyManager.getAgentDid(),
        maxBudgetPaise: 100000,
        singleTransactionLimitPaise: 100000,
        upiCircleDelegationToken: "tok_1",
        nonce: "nonce_fixed",
        timestamp: 1700000000
      },
      userKeyManager
    );

    const intentB = { ...intentA, userSignature: "f".repeat(128) };

    const hashA = computeMandateHash(intentA as unknown as Record<string, unknown>);
    const hashB = computeMandateHash(intentB as unknown as Record<string, unknown>);
    assert.equal(hashA, hashB);
  });

  it("should verify valid mandate chain successfully", () => {
    const { intentMandate, cartMandate, executionMandate } = buildMandateTestFixtures(
      userKeyManager,
      agentKeyManager,
      merchantKeyManager
    );

    assert.equal(verifyMandateChain(intentMandate, cartMandate, executionMandate), true);
  });

  it("should detect mandate tampering in verifyMandateChain", () => {
    const { intentMandate, cartMandate, executionMandate } = buildMandateTestFixtures(
      userKeyManager,
      agentKeyManager,
      merchantKeyManager
    );

    const tamperedCart = { ...cartMandate, totalPaise: 120000 };

    assert.throws(
      () => verifyMandateChain(intentMandate, tamperedCart, executionMandate),
      (err: unknown) => err instanceof MandateVerificationError
    );
  });
});
