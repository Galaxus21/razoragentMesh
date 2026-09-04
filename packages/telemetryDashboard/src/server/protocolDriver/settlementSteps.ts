// Layer 4: hand the verified bundle to the settlement coordinator, which re-verifies every
// signature server-side before splitting funds. The buyer agent's word is never taken on trust.

import { demoMerchantAccount, demoPaymentId } from "./driverConfig";
import {
  ExecutableStep,
  currentUnixSeconds,
  layerSettlement,
  packageMandateEngine,
  requireState
} from "./stepContext";

export const stepSettle: ExecutableStep = {
  definition: {
    stepId: "settle",
    title: "Execute the settlement saga",
    narrative:
      "The verified mandate bundle goes to the settlement coordinator, which re-checks every signature, splits the payment across the merchant, logistics, and protocol-fee accounts under two-phase commit, and issues the statutory invoice.",
    protocolLayer: layerSettlement,
    implementedBy: `${packageMandateEngine}settlementOrchestrator.py`,
    invariant: "Two-phase commit across Route recipients",
    sdkCall: { methodName: "executeSettlement", argumentSummary: {}, isPureCrypto: false }
  },
  execute: async (context) => {
    const intentMandate = requireState(context.state.intentMandate, "settle");
    const cartMandate = requireState(context.state.cartMandate, "settle");
    const executionMandate = requireState(context.state.executionMandate, "settle");

    const settlement = await context.client.executeSettlement({
      intentMandate,
      cartMandate,
      executionMandate,
      merchantAccount: demoMerchantAccount,
      paymentId: demoPaymentId,
      serverTime: currentUnixSeconds()
    });

    return {
      status: "SUCCEEDED",
      resultSummary: settlement as unknown as Record<string, unknown>
    };
  }
};
