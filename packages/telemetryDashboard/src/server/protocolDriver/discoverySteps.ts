// Layer 1 steps: everything the buyer agent does over HTTP against the MCP tool layer before
// any signature exists. These are the calls that had nothing to connect to until the REST
// adapter in packages/mcpServer/src/http/ was added.

import {
  ExecutableStep,
  layerDiscovery,
  packageMcpTools,
  requireState
} from "./stepContext";

export const stepFetchQuote: ExecutableStep = {
  definition: {
    stepId: "fetchQuote",
    title: "Fetch a live SKU quote",
    narrative:
      "The buyer agent asks the merchant's tool layer what this SKU costs at this quantity, delivered to this pincode. The price returns with volume-tier and promotion discounts already stacked, the HSN-derived GST split, and a signed quote hash that pins the offer so it cannot be renegotiated silently later.",
    protocolLayer: layerDiscovery,
    implementedBy: `${packageMcpTools}skuQuoter.ts`,
    sdkCall: { methodName: "getLiveSkuQuote", argumentSummary: {}, isPureCrypto: false }
  },
  execute: async (context) => {
    const { skuId, quantity, deliveryPincode, promoCode } = context.parameters;
    const quote = await context.client.getLiveSkuQuote(skuId, quantity, {
      deliveryPincode,
      ...(promoCode ? { promoCode } : {})
    });
    context.state.quote = quote;
    return {
      status: "SUCCEEDED",
      resultSummary: {
        finalUnitPricePaise: quote.finalUnitPricePaise,
        totalSavingsPaise: quote.totalSavingsPaise,
        totalTaxPaise: quote.taxBreakdown.totalTaxPaise,
        quoteHash: quote.quoteHash
      }
    };
  }
};

export const stepVerifySla: ExecutableStep = {
  definition: {
    stepId: "verifySla",
    title: "Verify the shipping SLA",
    narrative:
      "Before committing, the agent checks whether the destination is serviceable and what delivery will cost. The courier zone is derived from the origin and destination pincodes, so the shipping figure entering the cart is the one the merchant would actually charge.",
    protocolLayer: layerDiscovery,
    implementedBy: `${packageMcpTools}slaVerifier.ts`,
    sdkCall: { methodName: "verifyShippingSla", argumentSummary: {}, isPureCrypto: false }
  },
  execute: async (context) => {
    const { deliveryPincode, packageWeightGrams } = context.parameters;
    const sla = await context.client.verifyShippingSla(deliveryPincode, packageWeightGrams);
    context.state.sla = sla;
    return {
      status: "SUCCEEDED",
      resultSummary: {
        zone: sla.zone,
        slaHours: sla.slaHours,
        shippingFeePaise: sla.shippingFeePaise
      }
    };
  }
};

export const stepReserveLock: ExecutableStep = {
  definition: {
    stepId: "reserveLock",
    title: "Reserve the stock atomically",
    narrative:
      "The agent takes a short-lived reservation so the price it just quoted cannot be sold out from under it mid-flow. The lock carries a monotonic fencing token, which is what stops a delayed retry from resurrecting an already-expired reservation.",
    protocolLayer: layerDiscovery,
    implementedBy: `${packageMcpTools}inventoryLocker.ts`,
    invariant: "Atomic inventory fencing",
    sdkCall: { methodName: "reserveInventoryLock", argumentSummary: {}, isPureCrypto: false }
  },
  execute: async (context) => {
    const quote = requireState(context.state.quote, "reserveLock");
    const { skuId, quantity, lockTtlSeconds } = context.parameters;
    const lock = await context.client.reserveInventoryLock(skuId, quantity, {
      quoteHash: quote.quoteHash,
      lockTtlSeconds
    });
    context.state.lock = lock;
    return {
      status: "SUCCEEDED",
      resultSummary: {
        lockToken: lock.lockToken,
        fencingToken: lock.fencingToken,
        expiresAtUnixMs: lock.expiresAtUnixMs
      }
    };
  }
};
