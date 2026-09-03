// Layer 4 steps: the AP2 mandate chain. These are pure cryptography -- no network call -- which
// is why the playground can re-verify each one in the visitor's own browser.

import {
  createSignedCartMandate,
  createSignedExecutionMandate,
  createSignedIntentMandate,
  verifyMandateChain
} from "@razorpay/agent-buyer-sdk";
import {
  authorizedCategories,
  merchantGstin,
  merchantStateCode,
  millisPerSecond,
  upiCircleDelegationToken
} from "./driverConfig";
import { describeMandateArtifact } from "./stepRecorder";
import {
  ExecutableStep,
  currentUnixSeconds,
  intentValiditySeconds,
  layerMandates,
  packageSdkMandates,
  requireState,
  tamperReductionPaise
} from "./stepContext";

export interface IntentStepOptions {
  readonly budgetOverridePaise?: number;
  // Negative values put the delegation's expiry in the past, which is how the stale-delegation
  // scenario produces a mandate that is validly signed and no longer valid.
  readonly validitySecondsOverride?: number;
  // Set below the cart total to trip the per-transaction ceiling rather than the overall budget.
  readonly singleTransactionLimitOverridePaise?: number;
}

export function buildIntentStep(options: IntentStepOptions = {}): ExecutableStep {
  return {
    definition: {
      stepId: "signIntent",
      title: "User signs the spending delegation",
      narrative:
        "The human -- or a CFO agent acting for them -- signs an Intent Mandate: a ceiling on what the buyer agent may spend, which categories it may spend on, and for how long. This is the only step a person is involved in; everything after it is autonomous.",
      protocolLayer: layerMandates,
      implementedBy: packageSdkMandates,
      invariant: "INV-03",
      sdkCall: { methodName: "createSignedIntentMandate", argumentSummary: {}, isPureCrypto: true }
    },
    execute: async (context) => {
      const maxBudgetPaise = options.budgetOverridePaise ?? context.parameters.maxBudgetPaise;
      const intentMandate = createSignedIntentMandate(
        {
          delegatedAgentDid: context.client.getAgentDid(),
          maxBudgetPaise,
          singleTransactionLimitPaise:
            options.singleTransactionLimitOverridePaise ??
            Math.min(context.parameters.singleTransactionLimitPaise, maxBudgetPaise),
          upiCircleDelegationToken,
          authorizedCategories,
          validUntilTimestamp:
            currentUnixSeconds() + (options.validitySecondsOverride ?? intentValiditySeconds)
        },
        context.userSigner
      );
      context.state.intentMandate = intentMandate;

      return {
        status: "SUCCEEDED",
        artifacts: [
          describeMandateArtifact({
            artifactId: "intentMandate",
            label: "Intent Mandate (M_I)",
            signerRole: "User / CFO key",
            signerDid: intentMandate.userDid,
            signatureFieldName: "userSignature",
            mandate: intentMandate as unknown as Record<string, unknown>
          })
        ],
        resultSummary: {
          mandateId: intentMandate.mandateId,
          maxBudgetPaise: intentMandate.maxBudgetPaise
        }
      };
    }
  };
}

export const stepSignCart: ExecutableStep = {
  definition: {
    stepId: "signCart",
    title: "Merchant signs the cart",
    narrative:
      "The merchant assembles the itemised cart from the live quote, the live shipping fee, and the live lock token, then signs it. Every number in the cart traces back to a value the mesh produced -- none of it is asserted by the buyer.",
    protocolLayer: layerMandates,
    implementedBy: packageSdkMandates,
    invariant: "INV-01",
    sdkCall: { methodName: "createSignedCartMandate", argumentSummary: {}, isPureCrypto: true }
  },
  execute: async (context) => {
    const quote = requireState(context.state.quote, "signCart");
    const sla = requireState(context.state.sla, "signCart");
    const lock = requireState(context.state.lock, "signCart");
    const { quantity, deliveryPincode, deliveryStateCode, skuId } = context.parameters;

    const lineTotalPaise = quote.finalUnitPricePaise * quantity;
    const totalPaise = lineTotalPaise + quote.taxBreakdown.totalTaxPaise + sla.shippingFeePaise;

    const cartMandate = createSignedCartMandate(
      {
        merchantGstin,
        merchantStateCode,
        buyerDeliveryPincode: deliveryPincode,
        buyerDeliveryStateCode: deliveryStateCode,
        items: [
          {
            skuId,
            quantity,
            unitPricePaise: quote.finalUnitPricePaise,
            hsnCode: quote.hsnCode,
            gstRatePercent: quote.gstRatePercent,
            lineTotalPaise
          }
        ],
        taxableSubtotalPaise: lineTotalPaise,
        taxBreakdown: quote.taxBreakdown,
        shippingPaise: sla.shippingFeePaise,
        // Zero, deliberately. The settlement enclave recomputes the subtotal from
        // unitPricePaise x quantity and then SUBTRACTS discountPaise
        // (mandateEngine/verification/budgetGate.py::_recomputeEnclaveTotal). Since the line
        // item already carries the post-discount unit price -- which is also the price GST was
        // levied on -- passing the savings here would deduct them twice and the enclave would
        // reject the cart. The savings figure is reported on the quote step instead.
        discountPaise: 0,
        totalPaise,
        inventoryLockToken: lock.lockToken,
        // SECONDS. The lock tool reports milliseconds, but the settlement enclave compares this
        // against int(time.time()) in _verifyInventoryLockActive
        // (mandateEngine/settlement/twoPhaseCommitSaga.py:318). Passing milliseconds made
        // `evaluatedAt > inventoryLockExpiresAt` always false, so the guard could never fire --
        // and its own docstring names the cost: "an expired reservation still settles, so stock
        // released back to other buyers can be sold twice". Converting here makes it enforce.
        // The MCP server's create_cart_mandate converts identically; the two must not diverge.
        inventoryLockExpiresAt: Math.floor(lock.expiresAtUnixMs / millisPerSecond)
      },
      context.merchantSigner
    );
    context.state.cartMandate = cartMandate;

    return {
      status: "SUCCEEDED",
      artifacts: [
        describeMandateArtifact({
          artifactId: "cartMandate",
          label: "Cart Mandate (M_C)",
          signerRole: "Merchant key",
          signerDid: cartMandate.merchantDid,
          signatureFieldName: "merchantSignature",
          mandate: cartMandate as unknown as Record<string, unknown>
        })
      ],
      resultSummary: { cartId: cartMandate.cartId, totalPaise: cartMandate.totalPaise }
    };
  }
};

// Rewrites one field of an ALREADY-SIGNED cart, leaving the merchant signature untouched --
// exactly what an intermediary altering the payload in transit would produce.
export const stepTamperCart: ExecutableStep = {
  definition: {
    stepId: "tamperCart",
    title: "An attacker edits the signed cart in transit",
    narrative:
      "The cart is already signed. Here a single field is rewritten -- the total quietly reduced -- while the merchant signature is left exactly as it was. Nothing about the payload looks malformed.",
    protocolLayer: layerMandates,
    implementedBy: packageSdkMandates,
    invariant: "INV-02",
    sdkCall: {
      methodName: "(no SDK call - payload mutated in transit)",
      argumentSummary: {},
      isPureCrypto: true
    }
  },
  execute: async (context) => {
    const cartMandate = requireState(context.state.cartMandate, "tamperCart");
    const originalTotalPaise = cartMandate.totalPaise;
    const tamperedTotalPaise = originalTotalPaise - tamperReductionPaise;
    context.state.cartMandate = { ...cartMandate, totalPaise: tamperedTotalPaise };

    return {
      status: "SUCCEEDED",
      resultSummary: {
        fieldAltered: "totalPaise",
        originalTotalPaise,
        tamperedTotalPaise,
        merchantSignatureUnchanged: true
      }
    };
  }
};

export const stepSignExecution: ExecutableStep = {
  definition: {
    stepId: "signExecution",
    title: "Buyer agent signs the execution authorisation",
    narrative:
      "The agent binds the two upstream mandates together: it hashes each one and signs the pair alongside the settlement amount. This hash-chain link is what makes any later edit to either mandate detectable.",
    protocolLayer: layerMandates,
    implementedBy: packageSdkMandates,
    invariant: "INV-02",
    sdkCall: { methodName: "createSignedExecutionMandate", argumentSummary: {}, isPureCrypto: true }
  },
  execute: async (context) => {
    const intentMandate = requireState(context.state.intentMandate, "signExecution");
    const cartMandate = requireState(context.state.cartMandate, "signExecution");

    const executionMandate = createSignedExecutionMandate(
      {
        intentMandate,
        cartMandate,
        settlementAmountPaise: cartMandate.totalPaise,
        upiCircleToken: intentMandate.upiCircleDelegationToken
      },
      context.client.getBuyerKeyManager()
    );
    context.state.executionMandate = executionMandate;

    return {
      status: "SUCCEEDED",
      artifacts: [
        describeMandateArtifact({
          artifactId: "executionMandate",
          label: "Execution Mandate (M_E)",
          signerRole: "Buyer agent key",
          signerDid: executionMandate.buyerAgentDid,
          signatureFieldName: "agentSignature",
          mandate: executionMandate as unknown as Record<string, unknown>,
          linkedHashes: {
            intentMandateHash: executionMandate.intentMandateHash,
            cartMandateHash: executionMandate.cartMandateHash
          }
        })
      ],
      resultSummary: {
        executionId: executionMandate.executionId,
        settlementAmountPaise: executionMandate.settlementAmountPaise
      }
    };
  }
};

const budgetRefusalMarker = "budget";

export const stepVerifyChain: ExecutableStep = {
  definition: {
    stepId: "verifyChain",
    title: "Verify the mandate chain",
    narrative:
      "The same check the settlement coordinator runs, executed locally first: recompute both upstream hashes, confirm they match what the Execution Mandate recorded, and confirm the settlement amount sits inside the delegated budget. If any of that fails the run stops here, before money moves.",
    protocolLayer: layerMandates,
    implementedBy: packageSdkMandates,
    invariant: "INV-02, INV-03",
    sdkCall: { methodName: "verifyMandateChain", argumentSummary: {}, isPureCrypto: true }
  },
  execute: async (context) => {
    const intentMandate = requireState(context.state.intentMandate, "verifyChain");
    const cartMandate = requireState(context.state.cartMandate, "verifyChain");
    const executionMandate = requireState(context.state.executionMandate, "verifyChain");

    try {
      verifyMandateChain(intentMandate, cartMandate, executionMandate);
      return { status: "SUCCEEDED", resultSummary: { chainVerified: true } };
    } catch (error) {
      const failure = error as Error;
      return {
        status: "REFUSED",
        refusal: {
          errorName: failure.name,
          message: failure.message,
          invariantViolated: failure.message.includes(budgetRefusalMarker) ? "INV-03" : "INV-02"
        }
      };
    }
  }
};
