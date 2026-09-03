// Covers scheduled-promotion authoring in the Merchant SKU Studio.
//
// The backend has supported scheduled promotions from the start, and a buyer agent reading
// `upcoming_promotions` on a quote is what produces the "wait for the sale" advice. The Studio
// could not author one, so a promotion could only be created by posting raw JSON to the merchant
// API. What these tests defend is the wire contract: ScheduledPromotionSchema is extra="forbid"
// and requires exactly the right key set, so a payload that over- or under-specifies a discount
// is a 422 the merchant sees as an opaque publish failure.

import { describe, it } from "node:test";
import assert from "node:assert/strict";

import {
  defaultCatalogFormState,
  maxPromotionDiscountBps,
  minPromotionWindowSeconds,
} from "../src/constants/merchantCatalogConstants.js";
import {
  buildScheduledPromotionPayload,
  buildUniversalProductPayload,
  validateMerchantCatalogForm,
} from "../src/lib/merchantCatalogValidator.js";
import {
  dateTimeLocalToUnix,
  unixToDateTimeLocal,
} from "../src/components/merchantSkuStudio/promotionBuilder.js";
import {
  MerchantCatalogFormData,
  ScheduledPromotionInput,
} from "../src/types/merchantCatalogTypes.js";

const startsAtUnix = 1_800_000_000;
const endsAtUnix = startsAtUnix + 86_400;

function buildPromotion(overrides: Partial<ScheduledPromotionInput> = {}): ScheduledPromotionInput {
  return {
    campaignId: "DIWALI_2026",
    name: "Diwali Flash Sale",
    startsAtUnix,
    endsAtUnix,
    discountKind: "PERCENT",
    discountBps: 1500,
    discountInr: "",
    fixedPriceInr: "",
    limitedStockAllocated: 0,
    ...overrides,
  };
}

/** A form that passes every other validator, so a failure names the promotion and nothing else. */
function buildValidForm(
  promotions: ReadonlyArray<ScheduledPromotionInput>
): MerchantCatalogFormData {
  return {
    ...defaultCatalogFormState,
    skuId: "SKU-PROMO-001",
    merchantDid: "did:agent:merchant_promo_01",
    title: "Promoted Ergonomic Chair",
    description: "A chair that goes on sale.",
    category: "General",
    hsnCode: "9401",
    basePriceInr: "1000.00",
    availableStock: 25,
    originPincode: "560001",
    promotions,
  };
}

describe("Merchant SKU Studio — scheduled promotion authoring", () => {
  it("starts with no promotions, so a quote advertises no sale until one is scheduled", () => {
    assert.equal(defaultCatalogFormState.promotions.length, 0);
  });

  it("omits the promotions key entirely when none are scheduled", () => {
    const payload = buildUniversalProductPayload(buildValidForm([]));
    // Not an empty array: the backend field is optional, and sending [] asserts the merchant
    // considered promotions and chose none rather than never opening the section.
    assert.equal("promotions" in payload, false);
  });

  it("carries a scheduled promotion through to the payload", () => {
    const payload = buildUniversalProductPayload(buildValidForm([buildPromotion()]));
    assert.equal(payload.promotions?.length, 1);
    assert.equal(payload.promotions?.[0].campaignId, "DIWALI_2026");
    assert.equal(payload.promotions?.[0].startsAtUnix, startsAtUnix);
    assert.equal(payload.promotions?.[0].endsAtUnix, endsAtUnix);
  });
});

describe("Merchant SKU Studio — promotion discount shapes", () => {
  it("emits discountBps alone for a percentage sale", () => {
    const payload = buildScheduledPromotionPayload(buildPromotion({ discountBps: 1500 }));
    assert.equal(payload.discountBps, 1500);
    // ScheduledPromotionSchema requires AT LEAST one of the three and forbids unknown keys. All
    // three present would over-specify the sale, and a zeroed discountBps fails its ge= bound.
    assert.equal("discountPaise" in payload, false);
    assert.equal("fixedPricePaise" in payload, false);
  });

  it("emits discountPaise alone for a flat rupee discount, converted from rupees", () => {
    const payload = buildScheduledPromotionPayload(
      buildPromotion({ discountKind: "FLAT_OFF", discountInr: "150.50" })
    );
    assert.equal(payload.discountPaise, 15_050);
    assert.equal("discountBps" in payload, false);
    assert.equal("fixedPricePaise" in payload, false);
  });

  it("emits fixedPricePaise alone for a fixed sale price", () => {
    const payload = buildScheduledPromotionPayload(
      buildPromotion({ discountKind: "FIXED_PRICE", fixedPriceInr: "799.00" })
    );
    assert.equal(payload.fixedPricePaise, 79_900);
    assert.equal("discountBps" in payload, false);
    assert.equal("discountPaise" in payload, false);
  });

  it("drops limitedStockAllocated at zero, which the form uses to mean unlimited", () => {
    const unlimited = buildScheduledPromotionPayload(buildPromotion({ limitedStockAllocated: 0 }));
    assert.equal("limitedStockAllocated" in unlimited, false);

    const capped = buildScheduledPromotionPayload(buildPromotion({ limitedStockAllocated: 40 }));
    assert.equal(capped.limitedStockAllocated, 40);
  });

  it("trims the identifiers, so a stray space cannot create a second campaign", () => {
    const payload = buildScheduledPromotionPayload(
      buildPromotion({ campaignId: "  DIWALI_2026  ", name: "  Diwali Flash Sale  " })
    );
    assert.equal(payload.campaignId, "DIWALI_2026");
    assert.equal(payload.name, "Diwali Flash Sale");
  });
});

describe("Merchant SKU Studio — promotion validation mirrors the backend schema", () => {
  it("accepts a well-formed promotion", () => {
    const result = validateMerchantCatalogForm(buildValidForm([buildPromotion()]));
    assert.equal(result.isValid, true, JSON.stringify(result.errors));
  });

  it("requires a campaign id and a display name", () => {
    const result = validateMerchantCatalogForm(
      buildValidForm([buildPromotion({ campaignId: "  ", name: "" })])
    );
    assert.equal(result.isValid, false);
    assert.ok(result.errors.promotion_0_campaignId);
    assert.ok(result.errors.promotion_0_name);
  });

  it("refuses a window that ends before it starts", () => {
    const result = validateMerchantCatalogForm(
      buildValidForm([buildPromotion({ endsAtUnix: startsAtUnix - 1 })])
    );
    assert.equal(result.isValid, false);
    assert.ok(result.errors.promotion_0_endsAt);
  });

  it("refuses a window too short for an agent to act on", () => {
    const result = validateMerchantCatalogForm(
      buildValidForm([
        buildPromotion({ endsAtUnix: startsAtUnix + minPromotionWindowSeconds - 1 }),
      ])
    );
    assert.equal(result.isValid, false);
    assert.ok(result.errors.promotion_0_endsAt);
  });

  it("refuses a percentage outside the schema's basis-point bounds", () => {
    const tooLow = validateMerchantCatalogForm(
      buildValidForm([buildPromotion({ discountBps: 0 })])
    );
    assert.equal(tooLow.isValid, false);
    assert.ok(tooLow.errors.promotion_0_discount);

    const tooHigh = validateMerchantCatalogForm(
      buildValidForm([buildPromotion({ discountBps: maxPromotionDiscountBps + 1 })])
    );
    assert.equal(tooHigh.isValid, false);
    assert.ok(tooHigh.errors.promotion_0_discount);
  });

  it("refuses a rupee amount that is blank, negative or unparseable", () => {
    for (const amount of ["", "-20", "abc", "0"]) {
      const result = validateMerchantCatalogForm(
        buildValidForm([buildPromotion({ discountKind: "FLAT_OFF", discountInr: amount })])
      );
      assert.equal(result.isValid, false, `"${amount}" should be refused`);
      assert.ok(result.errors.promotion_0_discount);
    }
  });

  it("numbers each promotion's errors by its own index", () => {
    const result = validateMerchantCatalogForm(
      buildValidForm([buildPromotion(), buildPromotion({ name: "" })])
    );
    // The first row is valid, so an error keyed to it would point the merchant at the wrong one.
    assert.equal(result.errors.promotion_0_name, undefined);
    assert.ok(result.errors.promotion_1_name);
  });
});

describe("Merchant SKU Studio — promotion datetime round trip", () => {
  it("round-trips a unix timestamp through the datetime-local field to the minute", () => {
    // A promotion that displays an hour away from the time it was typed reads as a broken form,
    // so the conversion has to survive the local-timezone hop in both directions.
    const rendered = unixToDateTimeLocal(startsAtUnix);
    assert.match(rendered, /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/);
    assert.equal(dateTimeLocalToUnix(rendered), startsAtUnix);
  });

  it("treats an empty or unparseable value as unset rather than as the epoch", () => {
    assert.equal(dateTimeLocalToUnix(""), 0);
    assert.equal(dateTimeLocalToUnix("not a date"), 0);
    assert.equal(unixToDateTimeLocal(0), "");
  });
});
