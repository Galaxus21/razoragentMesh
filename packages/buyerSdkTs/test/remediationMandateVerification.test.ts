import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { AgentKeyManager } from "../src/agentKeyManager.js";
import {
  createSignedCartMandate,
  computeMandateHash
} from "../src/agentMandateBuilder.js";
import { RazorAgentClient } from "../src/razorAgentClient.js";
import {
  type CartMandate,
  type PriceDropAlert
} from "../src/types.js";

function buildInitialCartForAlert(merchantKeyManager: AgentKeyManager): CartMandate {
  return createSignedCartMandate(
    {
      merchantGstin: "29AABCU9603R1ZJ",
      merchantStateCode: "29",
      buyerDeliveryPincode: "560001",
      buyerDeliveryStateCode: "29",
      items: [
        {
          skuId: "SKU-ALERT-001",
          quantity: 1,
          unitPricePaise: 20000,
          hsnCode: "8504",
          gstRatePercent: 18,
          lineTotalPaise: 20000
        }
      ],
      taxableSubtotalPaise: 20000,
      taxBreakdown: { cgstPaise: 1800, sgstPaise: 1800, igstPaise: 0, totalTaxPaise: 3600 },
      totalPaise: 23600,
      inventoryLockToken: "lock_alert_001",
      inventoryLockExpiresAt: 1700000000
    },
    merchantKeyManager
  );
}

function buildExpectedAmendedCart(initialCart: CartMandate, priceDeltaPaise: number, merchantKm: AgentKeyManager): CartMandate {
  const amendedCartId = `cart_amended_${initialCart.cartId.replace(/^cart_/, "").slice(0, 16)}`;
  const unsigned = {
    buyerDeliveryPincode: initialCart.buyerDeliveryPincode,
    buyerDeliveryStateCode: initialCart.buyerDeliveryStateCode,
    cartId: amendedCartId,
    discountPaise: initialCart.discountPaise + priceDeltaPaise,
    inventoryLockExpiresAt: initialCart.inventoryLockExpiresAt,
    inventoryLockToken: initialCart.inventoryLockToken,
    items: initialCart.items,
    merchantDid: merchantKm.getAgentDid(),
    merchantGstin: initialCart.merchantGstin,
    merchantStateCode: initialCart.merchantStateCode,
    nonce: initialCart.nonce,
    shippingPaise: initialCart.shippingPaise,
    taxBreakdown: initialCart.taxBreakdown,
    taxableSubtotalPaise: initialCart.taxableSubtotalPaise,
    timestamp: initialCart.timestamp,
    totalPaise: initialCart.totalPaise - priceDeltaPaise
  };
  return {
    ...unsigned,
    merchantSignature: merchantKm.signPayload(unsigned)
  };
}

describe("Remediation Adversarial Verification — Mandate Signing", () => {
  const buyerKeyManager = AgentKeyManager.generate();
  const merchantKeyManager = AgentKeyManager.generate();

  describe("Defect 4: handlePriceDropAlert amended cart signing", () => {
    it("should build and cryptographically sign amended cart mandate correctly", () => {
      const initialCart = buildInitialCartForAlert(merchantKeyManager);
      const client = new RazorAgentClient({ buyerKeyManager });
      const alert: PriceDropAlert = {
        skuId: "SKU-ALERT-001",
        targetPricePaise: 18000,
        activePricePaise: 18000,
        concessionPaise: 2000
      };

      const amendment = client.handlePriceDropAlert(alert, initialCart, merchantKeyManager);

      // Invariant: priceDeltaPaise matches concession
      assert.equal(amendment.priceDeltaPaise, 2000);
      assert.equal(amendment.previousCartMandateHash, computeMandateHash(initialCart));

      // Reconstruct expected amended cart and verify hash matches
      const expectedAmendedCart = buildExpectedAmendedCart(initialCart, 2000, merchantKeyManager);
      assert.equal(amendment.newCartMandateHash, computeMandateHash(expectedAmendedCart));

      // Verify dual signatures on amendment payload
      const unsignedAmendment = {
        amendmentId: amendment.amendmentId,
        amendmentReason: amendment.amendmentReason,
        newCartMandateHash: amendment.newCartMandateHash,
        nonce: amendment.nonce,
        previousCartMandateHash: amendment.previousCartMandateHash,
        priceDeltaPaise: amendment.priceDeltaPaise,
        substitutedSkuMapping: amendment.substitutedSkuMapping,
        timestamp: amendment.timestamp
      };

      assert.equal(buyerKeyManager.verifyPayloadSignature(unsignedAmendment, amendment.agentSignature), true);
      assert.equal(merchantKeyManager.verifyPayloadSignature(unsignedAmendment, amendment.merchantSignature), true);
    });
  });
});
