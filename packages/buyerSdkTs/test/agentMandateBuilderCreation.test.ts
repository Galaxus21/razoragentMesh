import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { AgentKeyManager } from "../src/agentKeyManager.js";
import {
  computeMandateHash,
  createSignedIntentMandate,
  createSignedCartMandate,
  createSignedExecutionMandate,
  createSignedAmendmentMandate
} from "../src/agentMandateBuilder.js";
import { ArithmeticDriftException } from "../src/types.js";

function buildSampleCart(merchantKeyManager: AgentKeyManager, unitPrice = 420000) {
  return createSignedCartMandate(
    {
      merchantGstin: "29AABCU9603R1ZJ",
      merchantStateCode: "29",
      buyerDeliveryPincode: "560001",
      buyerDeliveryStateCode: "29",
      items: [{ skuId: "SKU-001", quantity: 1, unitPricePaise: unitPrice, hsnCode: "8504", gstRatePercent: 18, lineTotalPaise: unitPrice }],
      taxableSubtotalPaise: unitPrice,
      taxBreakdown: {
        cgstPaise: Math.floor(unitPrice * 0.09),
        sgstPaise: Math.floor(unitPrice * 0.09),
        igstPaise: 0,
        totalTaxPaise: Math.floor(unitPrice * 0.18)
      },
      shippingPaise: 0,
      discountPaise: 0,
      totalPaise: Math.floor(unitPrice * 1.18),
      inventoryLockToken: "lock_tok_001",
      inventoryLockExpiresAt: 2000000000
    },
    merchantKeyManager
  );
}

describe("AgentMandateBuilder — Mandate Creation", () => {
  const userKeyManager = AgentKeyManager.generate();
  const agentKeyManager = AgentKeyManager.generate();
  const merchantKeyManager = AgentKeyManager.generate();

  it("should create and sign an IntentMandate with valid constraints", () => {
    const intentMandate = createSignedIntentMandate(
      {
        delegatedAgentDid: agentKeyManager.getAgentDid(),
        maxBudgetPaise: 500000,
        singleTransactionLimitPaise: 500000,
        upiCircleDelegationToken: "upi_tok_delegate_001",
        authorizedCategories: ["industrial_electronics"]
      },
      userKeyManager
    );

    assert.equal(intentMandate.userDid, userKeyManager.getAgentDid());
    assert.equal(intentMandate.delegatedAgentDid, agentKeyManager.getAgentDid());
    assert.equal(intentMandate.currency, "INR");
    assert.equal(intentMandate.maxBudgetPaise, 500000);
    assert.equal(intentMandate.userSignature.length, 128);
    assert.deepEqual(intentMandate.authorizedCategories, ["industrial_electronics"]);
  });

  it("should reject IntentMandate with non-positive budget or limit", () => {
    assert.throws(
      () =>
        createSignedIntentMandate(
          {
            delegatedAgentDid: agentKeyManager.getAgentDid(),
            maxBudgetPaise: 0,
            singleTransactionLimitPaise: 500000,
            upiCircleDelegationToken: "upi_tok_001"
          },
          userKeyManager
        ),
      (err: unknown) => err instanceof ArithmeticDriftException
    );
  });

  it("should create and sign a CartMandate with itemized taxes", () => {
    const cartMandate = buildSampleCart(merchantKeyManager, 420000);

    assert.equal(cartMandate.merchantDid, merchantKeyManager.getAgentDid());
    assert.equal(cartMandate.totalPaise, 495600);
    assert.equal(cartMandate.merchantSignature.length, 128);
  });

  it("should create an ExecutionMandate binding Intent and Cart mandate hashes", () => {
    const intentMandate = createSignedIntentMandate(
      { delegatedAgentDid: agentKeyManager.getAgentDid(), maxBudgetPaise: 500000, singleTransactionLimitPaise: 500000, upiCircleDelegationToken: "upi_tok_delegate_001" },
      userKeyManager
    );
    const cartMandate = buildSampleCart(merchantKeyManager, 420000);

    const executionMandate = createSignedExecutionMandate(
      { intentMandate, cartMandate, settlementAmountPaise: cartMandate.totalPaise, upiCircleToken: intentMandate.upiCircleDelegationToken },
      agentKeyManager
    );

    assert.equal(executionMandate.buyerAgentDid, agentKeyManager.getAgentDid());
    assert.equal(executionMandate.intentMandateHash, computeMandateHash(intentMandate as unknown as Record<string, unknown>));
    assert.equal(executionMandate.cartMandateHash, computeMandateHash(cartMandate as unknown as Record<string, unknown>));
    assert.equal(executionMandate.agentSignature.length, 128);
  });

  it("should create and dual-sign an AmendmentMandate", () => {
    const previousCart = buildSampleCart(merchantKeyManager, 420000);
    const newCart = buildSampleCart(merchantKeyManager, 350000);

    const amendment = createSignedAmendmentMandate(
      {
        previousCartMandate: previousCart,
        newCartMandate: newCart,
        substitutedSkuMapping: { "SKU-001": "SKU-001" },
        priceDeltaPaise: 82600,
        amendmentReason: "Price drop applied"
      },
      agentKeyManager,
      merchantKeyManager
    );

    assert.equal(amendment.priceDeltaPaise, 82600);
    assert.equal(amendment.agentSignature.length, 128);
    assert.equal(amendment.merchantSignature.length, 128);
    assert.equal(amendment.previousCartMandateHash, computeMandateHash(previousCart as unknown as Record<string, unknown>));
    assert.equal(amendment.newCartMandateHash, computeMandateHash(newCart as unknown as Record<string, unknown>));
  });
});
