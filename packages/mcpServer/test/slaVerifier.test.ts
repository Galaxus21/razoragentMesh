import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { verifyShippingSla } from "../src/tools/slaVerifier.js";

describe("SlaVerifier (Tool 3: verify_shipping_sla)", () => {
  it("should calculate Zone A intra-city standard SLA and cost", () => {
    const result = verifyShippingSla({
      origin_pincode: "560001",
      delivery_pincode: "560034", // Intra-Bangalore (Zone A)
      package_weight_grams: 400,
      required_delivery_tier: "standard"
    });

    assert.equal(result.zone_code, "ZONE_A");
    assert.equal(result.guaranteed_sla_hours, 24);
    assert.equal(result.shipping_cost_paise, 4000);
    assert.equal(result.courier_partner, "Delhivery");
    assert.equal(result.serviceable, true);
  });

  it("should calculate Zone A intra-city same-day SLA and cost", () => {
    const result = verifyShippingSla({
      origin_pincode: "560001",
      delivery_pincode: "560034",
      package_weight_grams: 500,
      required_delivery_tier: "sameDay"
    });

    assert.equal(result.zone_code, "ZONE_A");
    assert.equal(result.guaranteed_sla_hours, 6);
    assert.equal(result.shipping_cost_paise, 15000);
    assert.equal(result.courier_partner, "BlueDart");
  });

  it("should calculate Zone B intra-state express SLA and cost", () => {
    const result = verifyShippingSla({
      origin_pincode: "560001", // Bangalore, KA
      delivery_pincode: "570001", // Mysore, KA (Zone B)
      package_weight_grams: 450,
      required_delivery_tier: "express"
    });

    assert.equal(result.zone_code, "ZONE_B");
    assert.equal(result.guaranteed_sla_hours, 24);
    assert.equal(result.shipping_cost_paise, 12000);
    assert.equal(result.courier_partner, "BlueDart");
  });

  it("should calculate Zone C national inter-state SLA with weight surcharge", () => {
    // 1400g package: base 500g + 2 extra chunks of 500g (+2000 paise surcharge)
    // Base standard national cost: 12000 paise -> Total: 14000 paise
    const result = verifyShippingSla({
      origin_pincode: "560001", // Bangalore, KA
      delivery_pincode: "110001", // Delhi (Zone C)
      package_weight_grams: 1400,
      required_delivery_tier: "standard"
    });

    assert.equal(result.zone_code, "ZONE_C");
    assert.equal(result.guaranteed_sla_hours, 72);
    assert.equal(result.shipping_cost_paise, 14000);
    assert.equal(result.courier_partner, "Delhivery");
  });
});
