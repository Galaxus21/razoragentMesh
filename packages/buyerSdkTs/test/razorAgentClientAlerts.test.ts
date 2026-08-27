import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { AgentKeyManager } from "../src/agentKeyManager.js";
import {
  createSignedCartMandate,
  computeMandateHash
} from "../src/agentMandateBuilder.js";
import { RazorAgentClient } from "../src/razorAgentClient.js";
import type { AmendmentMandate, CartMandate } from "../src/types.js";

function createSampleAlertCartMandate(merchantKeyManager: AgentKeyManager): CartMandate {
  return createSignedCartMandate(
    {
      merchantGstin: "29AABCU9603R1ZJ",
      merchantStateCode: "29",
      buyerDeliveryPincode: "560001",
      buyerDeliveryStateCode: "29",
      items: [
        {
          skuId: "SKU-DROP-001",
          quantity: 1,
          unitPricePaise: 420000,
          hsnCode: "8504",
          gstRatePercent: 18,
          lineTotalPaise: 420000
        }
      ],
      taxableSubtotalPaise: 420000,
      taxBreakdown: { cgstPaise: 37800, sgstPaise: 37800, igstPaise: 0, totalTaxPaise: 75600 },
      totalPaise: 495600,
      inventoryLockToken: "lock_drop_001",
      inventoryLockExpiresAt: 2000000000
    },
    merchantKeyManager
  );
}

function buildUnsignedAmendmentPayload(amendment: AmendmentMandate) {
  return {
    amendmentId: amendment.amendmentId,
    amendmentReason: amendment.amendmentReason,
    newCartMandateHash: amendment.newCartMandateHash,
    nonce: amendment.nonce,
    previousCartMandateHash: amendment.previousCartMandateHash,
    priceDeltaPaise: amendment.priceDeltaPaise,
    substitutedSkuMapping: amendment.substitutedSkuMapping,
    timestamp: amendment.timestamp
  };
}

describe("RazorAgentClientAlerts — Price Drop Alerts & Amendment Mandates", () => {
  const merchantKeyManager = AgentKeyManager.generate();
  const buyerKeyManager = AgentKeyManager.generate();

  it("should handle price drop alerts and generate valid AmendmentMandate structure", () => {
    const cartMandate = createSampleAlertCartMandate(merchantKeyManager);
    const client = new RazorAgentClient({ buyerKeyManager });
    const amendment = client.handlePriceDropAlert(
      {
        skuId: "SKU-DROP-001",
        targetPricePaise: 350000,
        activePricePaise: 350000,
        concessionPaise: 70000
      },
      cartMandate,
      merchantKeyManager
    );

    assert.equal(amendment.priceDeltaPaise, 70000);
    assert.equal(amendment.previousCartMandateHash, computeMandateHash(cartMandate as unknown as Record<string, unknown>));
    assert.equal(amendment.newCartMandateHash.length, 64);
    assert.equal(amendment.agentSignature.length, 128);
    assert.equal(amendment.merchantSignature.length, 128);
  });

  it("should generate cryptographically verifiable dual Ed25519 signatures on AmendmentMandate", () => {
    const cartMandate = createSampleAlertCartMandate(merchantKeyManager);
    const client = new RazorAgentClient({ buyerKeyManager });
    const amendment = client.handlePriceDropAlert(
      {
        skuId: "SKU-DROP-001",
        targetPricePaise: 350000,
        activePricePaise: 350000,
        concessionPaise: 70000
      },
      cartMandate,
      merchantKeyManager
    );

    const unsignedAmendment = buildUnsignedAmendmentPayload(amendment);
    assert.equal(buyerKeyManager.verifyPayloadSignature(unsignedAmendment, amendment.agentSignature), true);
    assert.equal(merchantKeyManager.verifyPayloadSignature(unsignedAmendment, amendment.merchantSignature), true);
  });
});
