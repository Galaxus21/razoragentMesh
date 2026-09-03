// Pins F-01: a merchant's scheduled sale must reach the price, not just the classifier.
//
// `pricingEnginePromotions.test.ts` has nine tests and every one asserts what
// `evaluateScheduledPromotions` RETURNS -- window boundaries, expected price, expected savings.
// None asserted what a buyer is charged. `activePromotions` was consumed by no production code,
// so a sale was advertised while upcoming (`expectedUnitPricePaise: 1800000`) and then never
// applied once its window opened (charged 2397850, thirty minutes in).
//
// The invariant these tests hold: the price promised while a sale is upcoming is the price
// charged once it is open.

import assert from "node:assert/strict";
import test from "node:test";
import {
  computeAutoDiscountStack,
  evaluateScheduledPromotions,
  type ScheduledPromotion
} from "../src/catalog/pricingEngine.js";

const monitorBasePaise = 2400000;
const flashSaleBps = 2500;
const saleWindowSeconds = 86400;
const nowUnix = 1788450000;
const beforeWindowUnix = nowUnix - 1200;
const noVolumeTiers = [] as const;

// The offers a Studio-authored SKU carries: campaign off, no cashback, no codes. Keeps these
// assertions about the promotion rather than about the demo-wide default discounts.
const noMerchantOffers = { campaign: undefined, paymentRailCashbackPaise: 0, promoCodes: [] };

function buildFlashSale(startsAtUnix: number): ScheduledPromotion {
  return {
    campaignId: "MESH_FLASH_SALE",
    name: "Mesh Flash Sale - 25% off 4K monitors",
    startsAtUnix,
    endsAtUnix: startsAtUnix + saleWindowSeconds,
    discountBps: flashSaleBps
  } as ScheduledPromotion;
}

test("the price promised while a sale is upcoming is the price charged once it opens", () => {
  const sale = buildFlashSale(nowUnix);

  // What the mesh advertises to an agent before the window opens.
  const promised = evaluateScheduledPromotions(monitorBasePaise, [sale], beforeWindowUnix)
    .upcomingPromotions[0];
  assert.equal(promised.expected_unit_price_paise, 1800000, "25% off Rs 24,000 is Rs 18,000");

  // What the same agent is quoted a moment after it opens.
  const charged = computeAutoDiscountStack(
    monitorBasePaise, 1, noVolumeTiers, undefined, noMerchantOffers, [sale], nowUnix
  );

  assert.equal(
    charged.offeredUnitPricePaise,
    promised.expected_unit_price_paise,
    "the sale must be applied, not merely advertised"
  );
});

test("a sale that has not started yet does not discount", () => {
  const sale = buildFlashSale(nowUnix);
  const result = computeAutoDiscountStack(
    monitorBasePaise, 1, noVolumeTiers, undefined, noMerchantOffers, [sale], beforeWindowUnix
  );

  assert.equal(result.offeredUnitPricePaise, monitorBasePaise);
  assert.equal(result.appliedDiscounts.length, 0);
});

test("a sale that has ended does not discount", () => {
  const sale = buildFlashSale(nowUnix);
  const afterWindowUnix = sale.endsAtUnix + 1;
  const result = computeAutoDiscountStack(
    monitorBasePaise, 1, noVolumeTiers, undefined, noMerchantOffers, [sale], afterWindowUnix
  );

  assert.equal(result.offeredUnitPricePaise, monitorBasePaise);
});

test("an applied sale is named in appliedDiscounts so an agent can report it", () => {
  const result = computeAutoDiscountStack(
    monitorBasePaise, 1, noVolumeTiers, undefined, noMerchantOffers, [buildFlashSale(nowUnix)], nowUnix
  );

  const promotionLine = result.appliedDiscounts.find((item) => item.type === "SCHEDULED_PROMOTION");
  assert.ok(promotionLine, "the buyer must be able to see which sale gave the discount");
  assert.equal(promotionLine.discountPaise, 600000);
  assert.match(promotionLine.label, /Mesh Flash Sale/);
});

test("a sale composes with a volume tier without float drift", () => {
  const tiers = [{ minQuantity: 10, discountBps: 1000 }];
  const quantity = 12;
  const result = computeAutoDiscountStack(
    monitorBasePaise, quantity, tiers, undefined, noMerchantOffers, [buildFlashSale(nowUnix)], nowUnix
  );

  // Sale first on the base price, then the tier on the promoted price: 1800000 - 10% = 1620000.
  assert.equal(result.offeredUnitPricePaise, 1620000);
  assert.equal(Number.isInteger(result.offeredUnitPricePaise), true);
  assert.equal(result.totalSavingsPaise, (monitorBasePaise - 1620000) * quantity);
});

test("overlapping sales take the deepest rather than stacking to zero", () => {
  const shallow = buildFlashSale(nowUnix);
  const deep = { ...buildFlashSale(nowUnix), campaignId: "MESH_DEEPER", discountBps: 4000 };

  const result = computeAutoDiscountStack(
    monitorBasePaise, 1, noVolumeTiers, undefined, noMerchantOffers, [shallow, deep], nowUnix
  );

  assert.equal(result.offeredUnitPricePaise, 1440000, "40% off, not 65% off");
  assert.equal(
    result.appliedDiscounts.filter((item) => item.type === "SCHEDULED_PROMOTION").length,
    1
  );
});
