import { describe, it } from "node:test";
import assert from "node:assert/strict";

import {
  AgentKeyManager,
  createSignedCartMandate,
  createSignedExecutionMandate,
  createSignedIntentMandate,
  verifyMandateChain,
  type CartMandate,
  type IntentMandate,
} from "@razorpay/agent-buyer-sdk";
import { scenarioSummaries } from "../src/constants/scenarioCatalog.js";
import { describeScenarioSteps } from "../src/server/protocolDriver/runScenario.js";

// The adversarial grid is only worth showing if each attack is actually refused, and refused for
// the stated reason. Running the driver end to end needs the mesh up, so this asserts the half
// that is pure cryptography: build the chain each scenario builds, break the one thing it breaks,
// and check the verifier the driver calls says no -- and says why.
//
// A scenario whose premise is real but whose verifier happens not to check it would otherwise sit
// in the catalog looking convincing.

const cartTotalPaise = 320544;
const oneHourSeconds = 3600;

function buildChain(options: {
  readonly maxBudgetPaise?: number;
  readonly singleTransactionLimitPaise?: number;
  readonly validitySecondsOffset?: number;
  readonly settlementAmountPaise?: number;
}) {
  const userSigner = AgentKeyManager.generate();
  const merchantSigner = AgentKeyManager.generate();
  const buyerSigner = AgentKeyManager.generate();
  const nowSeconds = Math.floor(Date.now() / 1000);

  const intentMandate: IntentMandate = createSignedIntentMandate(
    {
      delegatedAgentDid: buyerSigner.getAgentDid(),
      maxBudgetPaise: options.maxBudgetPaise ?? 5_000_000,
      singleTransactionLimitPaise: options.singleTransactionLimitPaise ?? 800_000,
      upiCircleDelegationToken: "upi_circle_delegation_a41c",
      authorizedCategories: ["apparel"],
      validUntilTimestamp: nowSeconds + (options.validitySecondsOffset ?? 86_400),
    },
    userSigner
  );

  const cartMandate: CartMandate = createSignedCartMandate(
    {
      cartId: "cart_adversarial",
      merchantGstin: "29AABCU9603R1ZM",
      merchantStateCode: "29",
      buyerDeliveryPincode: "560001",
      buyerDeliveryStateCode: "29",
      items: [
        {
          skuId: "sku_cotton_oxford_shirt",
          hsnCode: "6205",
          quantity: 2,
          unitPricePaise: 159000,
          lineTotalPaise: 318000,
          gstRatePercent: 12,
        },
      ],
      taxableSubtotalPaise: 286200,
      taxBreakdown: { cgstPaise: 17172, sgstPaise: 17172, igstPaise: 0, totalTaxPaise: 34344 },
      shippingPaise: 0,
      discountPaise: 31800,
      totalPaise: cartTotalPaise,
      inventoryLockToken: "lock_adversarial",
      inventoryLockExpiresAt: Date.now() + 60_000,
    },
    merchantSigner
  );

  const executionMandate = createSignedExecutionMandate(
    {
      executionId: "exec_adversarial",
      intentMandate,
      cartMandate,
      settlementAmountPaise: options.settlementAmountPaise ?? cartMandate.totalPaise,
      upiCircleToken: intentMandate.upiCircleDelegationToken,
    },
    buyerSigner
  );

  return { intentMandate, cartMandate, executionMandate };
}

function refusalReason(chain: ReturnType<typeof buildChain>): string {
  try {
    verifyMandateChain(chain.intentMandate, chain.cartMandate, chain.executionMandate);
    return "";
  } catch (error) {
    return (error as Error).message;
  }
}

describe("Every adversarial scenario is actually refused", () => {
  it("accepts the chain when nothing is wrong, so the refusals below mean something", () => {
    assert.equal(refusalReason(buildChain({})), "");
  });

  it("refuses a delegation whose validity window has closed", () => {
    const reason = refusalReason(buildChain({ validitySecondsOffset: -oneHourSeconds }));
    assert.match(reason, /expired/i, `staleDelegation was not refused (got: ${reason || "accepted"})`);
  });

  it("refuses a cart over the per-transaction ceiling even when the budget is ample", () => {
    // The distinction the scenario exists to show: the overall budget is untouched.
    const reason = refusalReason(
      buildChain({ maxBudgetPaise: 50_000_000, singleTransactionLimitPaise: 1_000 })
    );
    assert.match(reason, /single transaction limit/i, `oversizedTransaction: ${reason || "accepted"}`);
  });

  it("refuses a settlement amount that does not match the signed cart", () => {
    const reason = refusalReason(buildChain({ settlementAmountPaise: cartTotalPaise + 250_000 }));
    assert.match(reason, /does not match cart total/i, `amountMismatch: ${reason || "accepted"}`);
  });

  it("refuses a cart total above the delegated budget", () => {
    const reason = refusalReason(buildChain({ maxBudgetPaise: 50_000 }));
    assert.match(reason, /budget|limit/i, `budgetBlocked: ${reason || "accepted"}`);
  });

  it("refuses a cart edited after signing", () => {
    const chain = buildChain({});
    const tampered = {
      ...chain,
      cartMandate: { ...chain.cartMandate, totalPaise: chain.cartMandate.totalPaise - 100_000 },
    };
    assert.match(refusalReason(tampered), /hash mismatch/i);
  });
});

describe("The catalog and the driver agree on the grid", () => {
  it("gives every catalogued scenario a runnable step list", () => {
    for (const summary of scenarioSummaries) {
      const steps = describeScenarioSteps(summary.scenarioId);
      assert.ok(steps.length > 0, `${summary.scenarioId} has no steps`);
    }
  });

  it("carries the six attacks the grid was designed for, plus the happy path", () => {
    const adversarial = scenarioSummaries.filter((summary) => summary.kind === "ADVERSARIAL");
    assert.equal(adversarial.length, 6, "the adversarial grid should carry six attacks");
    assert.ok(scenarioSummaries.some((summary) => summary.kind === "HAPPY_PATH"));
  });

  it("ends every adversarial run on a step that can refuse", () => {
    // A scenario whose last step merely mutates state would end green no matter what the mesh
    // thinks -- the break has to be followed by a check.
    const refusingSteps = new Set(["verifyChain", "settle", "replaySettlement"]);
    for (const summary of scenarioSummaries.filter((entry) => entry.kind === "ADVERSARIAL")) {
      const steps = describeScenarioSteps(summary.scenarioId);
      const lastStep = steps[steps.length - 1];
      assert.ok(
        refusingSteps.has(lastStep.stepId),
        `${summary.scenarioId} ends on '${lastStep.stepId}', which cannot refuse anything`
      );
    }
  });
});
