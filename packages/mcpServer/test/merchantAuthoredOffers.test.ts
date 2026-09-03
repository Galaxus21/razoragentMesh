// Covers per-SKU merchant-authored offers in the discount stack.
//
// Four discount types can apply to a quote, and until now only ONE of them was the merchant's:
// volume tiers. The other three were global constants in protocolConstants.ts -- a single
// festive campaign percentage, a single UPI cashback amount, and a single corporate promo code --
// identical for every SKU in the mesh, and unwritable from the Studio or the merchant API. A
// merchant could not run their own sale, could not offer their own code, and could not switch the
// built-in ones off.
//
// The rule these tests pin is that `merchantOffers` is a COMPLETE statement. A SKU that carries it
// gets exactly what it declares; a SKU without it keeps the original demo constants, so every
// existing fixture and every previously published listing prices exactly as it did before.

import assert from "node:assert/strict";
import test from "node:test";
import {
  computeAutoDiscountStack,
  resolveSkuOffers
} from "../src/catalog/pricingEngine.js";
import {
  corporatePromoBps,
  corporatePromoCode,
  festiveCampaignBps,
  festiveCampaignCapPaise,
  upiCashbackPaise
} from "../src/constants/protocolConstants.js";
import { catalogSkuItemSchema } from "../src/types/mcpToolTypes.js";
import type { MerchantAuthoredOffers } from "../src/types/mcpToolTypes.js";

const baseUnitPricePaise = 100_000;

function discountOfType(
  result: ReturnType<typeof computeAutoDiscountStack>,
  type: string
): { readonly label: string; readonly discountPaise: number } | undefined {
  return result.appliedDiscounts.find((entry) => entry.type === type);
}

test("a SKU with no authored offers prices exactly as it did before", () => {
  // The compatibility guarantee. Every compiled fixture and every listing published before this
  // field existed lands here, so a change in this result is a silent repricing of the catalog.
  const result = computeAutoDiscountStack(baseUnitPricePaise, 1, []);

  const campaign = discountOfType(result, "CAMPAIGN");
  assert.equal(
    campaign?.discountPaise,
    Math.min(festiveCampaignCapPaise, Math.floor((baseUnitPricePaise * festiveCampaignBps) / 10_000))
  );
  assert.equal(discountOfType(result, "PAYMENT_RAIL")?.discountPaise, upiCashbackPaise);
});

test("the merchant's own campaign percentage and cap are what apply", () => {
  const offers: MerchantAuthoredOffers = {
    campaign: { label: "Monsoon Clearance", discountBps: 2000, capPaise: 15_000 }
  };
  const result = computeAutoDiscountStack(baseUnitPricePaise, 1, [], undefined, offers);

  const campaign = discountOfType(result, "CAMPAIGN");
  // 20% of 100000 is 20000, over the merchant's own 15000 cap.
  assert.equal(campaign?.discountPaise, 15_000);
  assert.match(campaign?.label ?? "", /Monsoon Clearance/);
  assert.match(campaign?.label ?? "", /20% off capped at ₹150/);
});

test("an uncapped campaign is not the same as a cap of zero", () => {
  const uncapped = computeAutoDiscountStack(baseUnitPricePaise, 1, [], undefined, {
    campaign: { discountBps: 2000 }
  });
  assert.equal(discountOfType(uncapped, "CAMPAIGN")?.discountPaise, 20_000);

  // A cap of zero is a real instruction -- it discounts nothing -- and must not be read as
  // "no cap set", which would give away the full 20%.
  const cappedAtZero = computeAutoDiscountStack(baseUnitPricePaise, 1, [], undefined, {
    campaign: { discountBps: 2000, capPaise: 0 }
  });
  assert.equal(discountOfType(cappedAtZero, "CAMPAIGN"), undefined);
});

test("a merchant can switch the built-in campaign and cashback off", () => {
  // The point of authoring offers. Declaring merchantOffers with no campaign and no cashback is
  // how a merchant says "my price is my price" -- if the globals still applied there would be no
  // way to express that.
  const result = computeAutoDiscountStack(baseUnitPricePaise, 1, [], undefined, {
    promoCodes: []
  });

  assert.equal(discountOfType(result, "CAMPAIGN"), undefined);
  assert.equal(discountOfType(result, "PAYMENT_RAIL"), undefined);
  assert.equal(result.offeredUnitPricePaise, baseUnitPricePaise);
  assert.equal(result.totalSavingsPaise, 0);
});

test("the merchant's own promo code is honoured and the demo one is not", () => {
  const offers: MerchantAuthoredOffers = {
    promoCodes: [{ code: "MONSOON15", discountBps: 1500, label: "Monsoon Code" }]
  };

  const matched = computeAutoDiscountStack(baseUnitPricePaise, 1, [], "monsoon15", offers);
  const applied = discountOfType(matched, "PROMO_CODE");
  assert.equal(applied?.discountPaise, 15_000);
  assert.match(applied?.label ?? "", /MONSOON15/);

  // The global CORP_5PCT is not this merchant's code, so it buys nothing here.
  const globalCode = computeAutoDiscountStack(baseUnitPricePaise, 1, [], corporatePromoCode, offers);
  assert.equal(discountOfType(globalCode, "PROMO_CODE"), undefined);
});

test("a SKU may honour several codes, and an unknown one changes nothing", () => {
  const offers: MerchantAuthoredOffers = {
    promoCodes: [
      { code: "WELCOME5", discountBps: 500 },
      { code: "BULK12", discountBps: 1200 }
    ]
  };

  assert.equal(
    discountOfType(computeAutoDiscountStack(baseUnitPricePaise, 1, [], "BULK12", offers), "PROMO_CODE")
      ?.discountPaise,
    12_000
  );
  assert.equal(
    discountOfType(
      computeAutoDiscountStack(baseUnitPricePaise, 1, [], "NOT_A_CODE", offers),
      "PROMO_CODE"
    ),
    undefined
  );
});

test("cashback never takes the price below zero", () => {
  const result = computeAutoDiscountStack(100, 1, [], undefined, {
    paymentRailCashbackPaise: 900_000
  });
  assert.equal(result.offeredUnitPricePaise, 0);
  assert.equal(discountOfType(result, "PAYMENT_RAIL")?.discountPaise, 100);
});

test("authored offers stack under the merchant's own volume tiers, in the same order", () => {
  const offers: MerchantAuthoredOffers = {
    campaign: { discountBps: 1000 },
    paymentRailCashbackPaise: 500,
    promoCodes: [{ code: "EXTRA5", discountBps: 500 }]
  };
  const result = computeAutoDiscountStack(
    baseUnitPricePaise,
    10,
    [{ minQuantity: 5, discountBps: 1000 }],
    "EXTRA5",
    offers
  );

  // 100000 -10% tier-> 90000 -10% campaign-> 81000 -500 cashback-> 80500 -5% code-> 76475.
  assert.deepEqual(
    result.appliedDiscounts.map((entry) => entry.type),
    ["VOLUME_TIER", "CAMPAIGN", "PAYMENT_RAIL", "PROMO_CODE"]
  );
  assert.equal(result.offeredUnitPricePaise, 76_475);
  assert.equal(result.totalSavingsPaise, (baseUnitPricePaise - 76_475) * 10);
});

test("resolveSkuOffers falls back to the demo constants only when nothing is authored", () => {
  const fallback = resolveSkuOffers(undefined);
  assert.equal(fallback.campaignBps, festiveCampaignBps);
  assert.equal(fallback.cashbackPaise, upiCashbackPaise);
  assert.deepEqual(fallback.promoCodes, [
    { code: corporatePromoCode, discountBps: corporatePromoBps }
  ]);

  const authored = resolveSkuOffers({ campaign: { discountBps: 300 } });
  assert.equal(authored.campaignBps, 300);
  assert.equal(authored.cashbackPaise, 0);
  assert.deepEqual(authored.promoCodes, []);
});

test("a SKU broadcast with null offer fields still parses", () => {
  // Python's model_dump() emits null for an unset Optional, so the Redis broadcast carries
  // `"capPaise": null` where a compiled fixture carries no key at all. An optional Zod field
  // rejects null -- which would make every Studio-published SKU fail to parse and drop out of the
  // live catalog without an error anyone would see.
  const parsed = catalogSkuItemSchema.parse({
    skuId: "SKU-BROADCAST-001",
    title: "Broadcast Chair",
    category: "furniture",
    description: "Arrived over mesh:catalog:updates.",
    hsnCode: "9401",
    gstRatePercent: 18,
    baseUnitPricePaise,
    availableStock: 5,
    volumeTiers: [],
    promotions: [],
    merchantOffers: {
      campaign: { label: null, discountBps: 800, capPaise: null },
      paymentRailCashbackPaise: null,
      promoCodes: [{ code: "SAVE8", discountBps: 800, label: null }]
    }
  });

  assert.equal(parsed.merchantOffers?.campaign?.discountBps, 800);
  assert.equal(parsed.merchantOffers?.campaign?.capPaise, undefined);
  assert.equal(parsed.merchantOffers?.paymentRailCashbackPaise, undefined);
  assert.equal(parsed.merchantOffers?.promoCodes?.[0].code, "SAVE8");
});

test("a SKU broadcast with merchantOffers null keeps the demo defaults", () => {
  // The shape the merchant API sends for a SKU with no authored offers.
  const parsed = catalogSkuItemSchema.parse({
    skuId: "SKU-BROADCAST-002",
    title: "Plain Chair",
    category: "furniture",
    description: "No authored offers.",
    hsnCode: "9401",
    gstRatePercent: 18,
    baseUnitPricePaise,
    availableStock: 5,
    volumeTiers: [],
    promotions: [],
    merchantOffers: null
  });

  assert.equal(parsed.merchantOffers, undefined);
  assert.equal(resolveSkuOffers(parsed.merchantOffers).campaignBps, festiveCampaignBps);
});
