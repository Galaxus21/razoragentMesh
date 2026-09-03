// Covers merchant-authored offers in the Merchant SKU Studio.
//
// A quote stacks four discount types and only ONE of them was the merchant's. Volume tiers came
// from their listing; the campaign percentage, the UPI cashback and the promo code were global
// constants in the MCP server — the same 10% festive discount, the same ₹1.50 cashback and the
// same CORP_5PCT code on every SKU in the mesh, with no way for a merchant to change or disable
// any of them.
//
// The rule under test is that presence is a complete statement. Sending `merchantOffers` at all
// replaces the mesh's defaults for that SKU, so the Studio must NOT send the key unless the
// merchant opted into authoring — otherwise ticking nothing would silently strip the campaign
// from every listing republished after this shipped.

import { describe, it } from "node:test";
import assert from "node:assert/strict";

import {
  defaultCatalogFormState,
  maxOfferDiscountBps,
  maxPromoCodesPerSku,
} from "../src/constants/merchantCatalogConstants.js";
import {
  buildMerchantOffersPayload,
  buildUniversalProductPayload,
  validateMerchantCatalogForm,
} from "../src/lib/merchantCatalogValidator.js";
import {
  MerchantCatalogFormData,
  MerchantOffersFormData,
} from "../src/types/merchantCatalogTypes.js";

function buildOffers(overrides: Partial<MerchantOffersFormData> = {}): MerchantOffersFormData {
  return {
    authorOffers: true,
    campaignEnabled: true,
    campaignLabel: "Monsoon Clearance",
    campaignDiscountBps: 2000,
    campaignCapInr: "150.00",
    paymentRailCashbackInr: "2.50",
    promoCodes: [{ code: "MONSOON15", discountBps: 1500, label: "Monsoon Code" }],
    ...overrides,
  };
}

/** A form that passes every other validator, so a failure names the offers and nothing else. */
function buildValidForm(offers: MerchantOffersFormData): MerchantCatalogFormData {
  return {
    ...defaultCatalogFormState,
    skuId: "SKU-OFFERS-001",
    merchantDid: "did:agent:merchant_offers_01",
    title: "Discounted Ergonomic Chair",
    description: "A chair with the merchant's own offers on it.",
    category: "General",
    hsnCode: "9401",
    basePriceInr: "1000.00",
    availableStock: 25,
    originPincode: "560001",
    offers,
  };
}

describe("Merchant SKU Studio — authoring offers is opt-in per listing", () => {
  it("starts with authoring off, so the mesh's default offers still apply", () => {
    assert.equal(defaultCatalogFormState.offers.authorOffers, false);
  });

  it("omits merchantOffers entirely when the merchant did not opt in", () => {
    // The compatibility guarantee. Presence of the key replaces the mesh's defaults, so sending
    // an empty object here would strip the campaign and cashback from every republished listing.
    const payload = buildUniversalProductPayload(
      buildValidForm(buildOffers({ authorOffers: false }))
    );
    assert.equal("merchantOffers" in payload, false);
  });

  it("sends merchantOffers once the merchant opts in", () => {
    const payload = buildUniversalProductPayload(buildValidForm(buildOffers()));
    assert.equal(payload.merchantOffers?.campaign?.discountBps, 2000);
    assert.equal(payload.merchantOffers?.promoCodes.length, 1);
  });

  it("lets a merchant run no offers at all, which is not the same as not authoring", () => {
    const payload = buildUniversalProductPayload(
      buildValidForm(
        buildOffers({
          campaignEnabled: false,
          paymentRailCashbackInr: "",
          promoCodes: [],
        })
      )
    );
    // The key is present and empty: this SKU has a campaign of none and a cashback of none.
    assert.deepEqual(payload.merchantOffers, { promoCodes: [] });
  });
});

describe("Merchant SKU Studio — offer payload shape", () => {
  it("converts the cap and cashback from rupees to integer paise", () => {
    const payload = buildMerchantOffersPayload(buildOffers());
    assert.equal(payload.campaign?.capPaise, 15_000);
    assert.equal(payload.paymentRailCashbackPaise, 250);
  });

  it("drops the cap key when blank, because uncapped is not a cap of zero", () => {
    const uncapped = buildMerchantOffersPayload(buildOffers({ campaignCapInr: "  " }));
    assert.equal("capPaise" in (uncapped.campaign ?? {}), false);

    // Zero is a real instruction — it caps the campaign at nothing — and must survive.
    const cappedAtZero = buildMerchantOffersPayload(buildOffers({ campaignCapInr: "0" }));
    assert.equal(cappedAtZero.campaign?.capPaise, 0);
  });

  it("drops the cashback key when blank rather than sending zero", () => {
    const payload = buildMerchantOffersPayload(buildOffers({ paymentRailCashbackInr: "" }));
    assert.equal("paymentRailCashbackPaise" in payload, false);
  });

  it("drops the campaign entirely when the merchant switched it off", () => {
    const payload = buildMerchantOffersPayload(buildOffers({ campaignEnabled: false }));
    assert.equal("campaign" in payload, false);
  });

  it("normalises promo codes to upper case and trims them", () => {
    // The pricing engine matches on the trimmed upper-cased code, so a code stored with a stray
    // space or in lower case would simply never match and the merchant would see no discount.
    const payload = buildMerchantOffersPayload(
      buildOffers({ promoCodes: [{ code: "  monsoon15 ", discountBps: 1500, label: "  " }] })
    );
    assert.equal(payload.promoCodes[0].code, "MONSOON15");
    assert.equal("label" in payload.promoCodes[0], false);
  });
});

describe("Merchant SKU Studio — offer validation mirrors the backend schema", () => {
  it("accepts well-formed offers", () => {
    const result = validateMerchantCatalogForm(buildValidForm(buildOffers()));
    assert.equal(result.isValid, true, JSON.stringify(result.errors));
  });

  it("skips offer validation entirely when authoring is off", () => {
    // Otherwise leftover text in a collapsed section would block a publish the merchant cannot
    // see a reason for.
    const result = validateMerchantCatalogForm(
      buildValidForm(
        buildOffers({ authorOffers: false, campaignDiscountBps: 99_999, campaignCapInr: "abc" })
      )
    );
    assert.equal(result.isValid, true, JSON.stringify(result.errors));
  });

  it("holds the campaign discount inside the model's basis-point bounds", () => {
    const tooHigh = validateMerchantCatalogForm(
      buildValidForm(buildOffers({ campaignDiscountBps: maxOfferDiscountBps + 1 }))
    );
    assert.equal(tooHigh.isValid, false);
    assert.ok(tooHigh.errors.offer_campaign_discount);
  });

  it("refuses a cap or cashback that is not a rupee amount", () => {
    for (const amount of ["abc", "-5", "1.999"]) {
      const cap = validateMerchantCatalogForm(
        buildValidForm(buildOffers({ campaignCapInr: amount }))
      );
      assert.equal(cap.isValid, false, `cap "${amount}" should be refused`);
      assert.ok(cap.errors.offer_campaign_cap);

      const cashback = validateMerchantCatalogForm(
        buildValidForm(buildOffers({ paymentRailCashbackInr: amount }))
      );
      assert.equal(cashback.isValid, false, `cashback "${amount}" should be refused`);
      assert.ok(cashback.errors.offer_cashback);
    }
  });

  it("treats a blank cap and cashback as unset, not as invalid", () => {
    const result = validateMerchantCatalogForm(
      buildValidForm(buildOffers({ campaignCapInr: "", paymentRailCashbackInr: "" }))
    );
    assert.equal(result.isValid, true, JSON.stringify(result.errors));
  });

  it("names the duplicate row rather than letting the backend refuse the whole object", () => {
    // MerchantAuthoredOffers rejects duplicate codes outright, and its 422 names the object, not
    // the row — which a merchant reads as an opaque publish failure.
    const result = validateMerchantCatalogForm(
      buildValidForm(
        buildOffers({
          promoCodes: [
            { code: "SAVE10", discountBps: 1000, label: "" },
            { code: "  save10  ", discountBps: 1200, label: "" },
          ],
        })
      )
    );
    assert.equal(result.isValid, false);
    assert.equal(result.errors.offer_promo_0_code, undefined);
    assert.match(result.errors.offer_promo_1_code ?? "", /already listed/);
  });

  it("refuses a promo code that is too short or too long", () => {
    const tooShort = validateMerchantCatalogForm(
      buildValidForm(buildOffers({ promoCodes: [{ code: "AB", discountBps: 500, label: "" }] }))
    );
    assert.equal(tooShort.isValid, false);
    assert.ok(tooShort.errors.offer_promo_0_code);

    const tooLong = validateMerchantCatalogForm(
      buildValidForm(
        buildOffers({ promoCodes: [{ code: "A".repeat(33), discountBps: 500, label: "" }] })
      )
    );
    assert.equal(tooLong.isValid, false);
    assert.ok(tooLong.errors.offer_promo_0_code);
  });

  it("refuses more promo codes than the backend accepts", () => {
    const promoCodes = Array.from({ length: maxPromoCodesPerSku + 1 }, (_, idx) => ({
      code: `CODE${idx}`,
      discountBps: 500,
      label: "",
    }));
    const result = validateMerchantCatalogForm(buildValidForm(buildOffers({ promoCodes })));
    assert.equal(result.isValid, false);
    assert.ok(result.errors.offer_promo_codes);
  });

  it("numbers each promo code's errors by its own index", () => {
    const result = validateMerchantCatalogForm(
      buildValidForm(
        buildOffers({
          promoCodes: [
            { code: "GOOD10", discountBps: 1000, label: "" },
            { code: "BAD20", discountBps: maxOfferDiscountBps + 1, label: "" },
          ],
        })
      )
    );
    assert.equal(result.errors.offer_promo_0_discount, undefined);
    assert.ok(result.errors.offer_promo_1_discount);
  });
});
