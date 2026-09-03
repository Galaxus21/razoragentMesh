// Steps that exist only to be refused.
//
// Each one takes a run that is valid up to that point and breaks exactly one thing, so the refusal
// a visitor sees is produced by the same verifier the happy path runs through -- not by a branch
// written to make the demo look good. None of them fabricates a rejection: the step succeeds at
// doing the damage, and the next step is where the mesh says no.
//
// Three of the four are pure cryptography and need no running service. The replay attack is the
// exception: only the settlement engine holds the nonce ledger, so that one wants the mesh up.

import { demoMerchantAccount, demoPaymentId } from "./driverConfig";
import {
  ExecutableStep,
  currentUnixSeconds,
  layerMandates,
  layerSettlement,
  packageMandateEngine,
  packageSdkMandates,
  requireState
} from "./stepContext";

// Enough to be unmistakable in the UI without looking like a rounding error.
const settlementInflationPaise = 250_000;

// HTTP 409 is what the engine's nonce ledger returns for an already-consumed nonce. Any other
// status from a replay is a genuine fault, not the defence firing.
const replayRejectedStatusCode = 409;

export const stepInflateSettlementAmount: ExecutableStep = {
  definition: {
    stepId: "inflateSettlementAmount",
    title: "The agent settles for more than the cart it was given",
    narrative:
      "The cart is signed and honest. Here the buyer agent rewrites only its own Execution Mandate, asking the settlement engine for more than the cart totals -- the case where the compromised party is the agent itself rather than the network.",
    protocolLayer: layerMandates,
    implementedBy: packageSdkMandates,
    invariant: "INV-02",
    sdkCall: {
      methodName: "(no SDK call - execution mandate mutated after signing)",
      argumentSummary: {},
      isPureCrypto: true
    }
  },
  execute: async (context) => {
    const executionMandate = requireState(context.state.executionMandate, "inflateSettlementAmount");
    const cartMandate = requireState(context.state.cartMandate, "inflateSettlementAmount");
    const inflatedAmountPaise = executionMandate.settlementAmountPaise + settlementInflationPaise;
    context.state.executionMandate = {
      ...executionMandate,
      settlementAmountPaise: inflatedAmountPaise
    };

    return {
      status: "SUCCEEDED",
      resultSummary: {
        fieldAltered: "settlementAmountPaise",
        cartTotalPaise: cartMandate.totalPaise,
        requestedAmountPaise: inflatedAmountPaise,
        agentSignatureUnchanged: true
      }
    };
  }
};

export const stepReplaySettlement: ExecutableStep = {
  definition: {
    stepId: "replaySettlement",
    title: "The same settlement is submitted a second time",
    narrative:
      "The first settlement succeeded and the money moved. This replays the identical mandate bundle, nonce and all -- what a network attacker gets for free by capturing one valid request. The engine's Redis nonce ledger is the only thing standing between a replay and a double charge.",
    protocolLayer: layerSettlement,
    implementedBy: `${packageMandateEngine}nonceLedger.py`,
    invariant: "INV-05",
    sdkCall: { methodName: "executeSettlement", argumentSummary: {}, isPureCrypto: false }
  },
  execute: async (context) => {
    const intentMandate = requireState(context.state.intentMandate, "replaySettlement");
    const cartMandate = requireState(context.state.cartMandate, "replaySettlement");
    const executionMandate = requireState(context.state.executionMandate, "replaySettlement");

    try {
      const settlement = await context.client.executeSettlement({
        intentMandate,
        cartMandate,
        executionMandate,
        merchantAccount: demoMerchantAccount,
        paymentId: demoPaymentId,
        serverTime: currentUnixSeconds()
      });

      // Reaching here means the ledger accepted a nonce it had already spent. The run summary
      // treats an unrefused adversarial scenario as UNEXPECTED, which is exactly what this is.
      return {
        status: "SUCCEEDED",
        resultSummary: {
          replayAccepted: true,
          settlement: settlement as unknown as Record<string, unknown>
        }
      };
    } catch (error) {
      // The nonce ledger lives in the engine, not in this process, so unlike the three pure-crypto
      // attacks this refusal arrives as an HTTP error rather than a thrown verifier result. Without
      // this branch the SDK's throw reaches the driver's generic catch and is recorded as FAILED --
      // which renders the one attack the ledger actually stopped as a red failure captioned "a real
      // failure, not a protocol refusal", the precise opposite of what happened. Only the ledger's
      // own 409 is a refusal; anything else really is a broken run and is rethrown.
      const failure = error as Error & { statusCode?: number };
      if (failure.statusCode !== replayRejectedStatusCode) {
        throw error;
      }
      return {
        status: "REFUSED",
        refusal: {
          errorName: failure.name,
          message: failure.message,
          invariantViolated: "INV-05",
          statusCode: failure.statusCode
        }
      };
    }
  }
};
