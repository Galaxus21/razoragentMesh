import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { AgentKeyManager } from "../src/agentKeyManager.js";
import {
  computeMandateHash,
  createSignedCartMandate
} from "../src/agentMandateBuilder.js";
import { RazorAgentClient } from "../src/razorAgentClient.js";
import {
  PriceDropAlert,
  CartMandate,
  AmendmentMandate
} from "../src/types.js";

function buildAlertCart(baseTime: number, merchantKeyManager: AgentKeyManager): CartMandate {
  return createSignedCartMandate(
    {
      merchantGstin: "29AABCU9603R1ZJ",
      merchantStateCode: "29",
      buyerDeliveryPincode: "560001",
      buyerDeliveryStateCode: "29",
      items: [{ skuId: "SKU-ALERT-001", quantity: 1, unitPricePaise: 50000, hsnCode: "8504", gstRatePercent: 18, lineTotalPaise: 50000 }],
      taxableSubtotalPaise: 50000,
      taxBreakdown: { cgstPaise: 4500, sgstPaise: 4500, igstPaise: 0, totalTaxPaise: 9000 },
      totalPaise: 59000,
      inventoryLockToken: "lock_alert_001",
      inventoryLockExpiresAt: baseTime + 300,
      timestamp: baseTime
    },
    merchantKeyManager
  );
}

function verifyDualSignatures(amendment: AmendmentMandate, buyerKm: AgentKeyManager, merchantKm: AgentKeyManager): void {
  const unsignedPayload = {
    amendmentId: amendment.amendmentId,
    amendmentReason: amendment.amendmentReason,
    newCartMandateHash: amendment.newCartMandateHash,
    nonce: amendment.nonce,
    previousCartMandateHash: amendment.previousCartMandateHash,
    priceDeltaPaise: amendment.priceDeltaPaise,
    substitutedSkuMapping: amendment.substitutedSkuMapping,
    timestamp: amendment.timestamp
  };

  assert.equal(buyerKm.verifyPayloadSignature(unsignedPayload, amendment.agentSignature), true, "Buyer agent signature must verify");
  assert.equal(merchantKm.verifyPayloadSignature(unsignedPayload, amendment.merchantSignature), true, "Merchant signature must verify");
}

describe("Challenger 1 — Phase 4 Client Price Drop Verification (buyerSdkTs)", () => {
  const buyerAgentKeyManager = AgentKeyManager.generate();
  const merchantKeyManager = AgentKeyManager.generate();
  const baseTime = 1720000000;

  describe("Price Drop Alert Handling & Dual Signature Generation", () => {
    it("should process valid price drop alert and produce cryptographically dual-signed AmendmentMandate", () => {
      const client = new RazorAgentClient({ buyerKeyManager: buyerAgentKeyManager });
      const previousCart = buildAlertCart(baseTime, merchantKeyManager);

      const alert: PriceDropAlert = {
        skuId: "SKU-ALERT-001",
        previousPricePaise: 50000,
        newPricePaise: 45000,
        concessionPaise: 5000,
        validUntilTimestamp: baseTime + 600
      };

      const amendmentMandate = client.handlePriceDropAlert(alert, previousCart, merchantKeyManager);

      assert.equal(amendmentMandate.priceDeltaPaise, 5000);
      assert.ok(amendmentMandate.amendmentId.startsWith("mandate_amend_"));
      assert.ok(amendmentMandate.amendmentReason.includes("5000"));

      verifyDualSignatures(amendmentMandate, buyerAgentKeyManager, merchantKeyManager);

      const expectedPrevHash = computeMandateHash(previousCart as unknown as Record<string, unknown>);
      assert.equal(amendmentMandate.previousCartMandateHash, expectedPrevHash);
    });

    it("should defensively clamp negative concession to 0 without corrupting totals", () => {
      const client = new RazorAgentClient({ buyerKeyManager: buyerAgentKeyManager });
      const previousCart = buildAlertCart(baseTime, merchantKeyManager);

      const negativeAlert: PriceDropAlert = {
        skuId: "SKU-ALERT-001",
        previousPricePaise: 10000,
        newPricePaise: 15000,
        concessionPaise: -5000,
        validUntilTimestamp: baseTime + 600
      };

      const amendment = client.handlePriceDropAlert(negativeAlert, previousCart, merchantKeyManager);
      assert.equal(amendment.priceDeltaPaise, 0);
    });
  });
});
