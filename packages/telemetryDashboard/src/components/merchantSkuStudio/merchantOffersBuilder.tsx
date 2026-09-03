"use client";

// Authors the campaign, UPI cashback and promo codes a quote applies to this SKU.
//
// Why this exists: a quote can stack four discount types, and only ONE of them was ever the
// merchant's. Volume tiers came from the listing; the campaign percentage, the cashback amount
// and the single promo code were global constants in the MCP server -- the same 10% festive
// discount, the same ₹1.50 cashback and the same CORP_5PCT code on every SKU in the mesh, with no
// way for a merchant to change any of them, and no way to switch them off.
//
// The master switch matters as much as the fields. Leaving it off publishes no merchantOffers
// key at all and the mesh applies its own defaults; turning it on makes this panel the complete
// statement of the SKU's offers, so an empty campaign here really does mean no campaign.

import React from "react";
import { BadgePercent, Plus, Trash2 } from "lucide-react";
import {
  defaultPromoCodeDiscountBps,
  maxOfferDiscountBps,
  maxPromoCodesPerSku,
  minOfferDiscountBps,
} from "@/constants/merchantCatalogConstants";
import {
  FormValidationErrors,
  MerchantOffersFormData,
  MerchantPromoCodeInput,
} from "@/types/merchantCatalogTypes";

export interface MerchantOffersBuilderProps {
  readonly offers: MerchantOffersFormData;
  readonly errors: FormValidationErrors;
  readonly onUpdateOffers: (patch: Partial<MerchantOffersFormData>) => void;
}

const emptyPromoCode: MerchantPromoCodeInput = {
  code: "",
  discountBps: defaultPromoCodeDiscountBps,
  label: "",
};

export function MerchantOffersBuilder({
  offers,
  errors,
  onUpdateOffers,
}: MerchantOffersBuilderProps): React.JSX.Element {
  const updatePromoCode = (index: number, patch: Partial<MerchantPromoCodeInput>): void => {
    onUpdateOffers({
      promoCodes: offers.promoCodes.map((entry, idx) =>
        idx === index ? { ...entry, ...patch } : entry
      ),
    });
  };

  return (
    <div className="rounded-lg border border-borderSubtle bg-bgSurface p-5 space-y-4">
      <div className="flex items-center justify-between border-b border-borderSubtle pb-3">
        <div className="flex items-center gap-2">
          <BadgePercent className="h-4 w-4 text-accentPrimary" />
          <h2 className="text-sm font-semibold text-textPrimary">Offers &amp; Promo Codes</h2>
        </div>
        <label className="flex cursor-pointer items-center gap-2 text-xs text-textSecondary">
          <input
            type="checkbox"
            checked={offers.authorOffers}
            onChange={(e) => onUpdateOffers({ authorOffers: e.target.checked })}
            className="h-3.5 w-3.5 accent-accentPrimary"
          />
          <span>Author my own</span>
        </label>
      </div>

      {!offers.authorOffers ? (
        <div className="rounded-lg border border-dashed border-borderSubtle p-6 text-center text-xs text-textMuted">
          <p>
            Using the mesh&apos;s default offers: a 10% festive campaign capped at ₹20, ₹1.50 UPI
            cashback, and the CORP_5PCT code. Tick &ldquo;Author my own&rdquo; to replace all three
            with yours — or to run none at all.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="space-y-2 rounded-md border border-borderSubtle bg-surfaceContainer px-3 py-3 text-xs">
            <label className="flex cursor-pointer items-center gap-2">
              <input
                type="checkbox"
                checked={offers.campaignEnabled}
                onChange={(e) => onUpdateOffers({ campaignEnabled: e.target.checked })}
                className="h-3.5 w-3.5 accent-accentPrimary"
              />
              <span className="font-semibold text-textPrimary">Run a campaign discount</span>
            </label>

            {offers.campaignEnabled && (
              <div className="grid grid-cols-12 gap-3 pt-1">
                <div className="col-span-5">
                  <label className="mb-1 block font-mono uppercase tracking-wider text-textSecondary">
                    Campaign Name
                  </label>
                  <input
                    type="text"
                    value={offers.campaignLabel}
                    onChange={(e) => onUpdateOffers({ campaignLabel: e.target.value })}
                    placeholder="Monsoon Clearance"
                    className="w-full rounded border border-borderSubtle bg-bgSurface px-2 py-1 text-xs text-textPrimary focus:border-accentPrimary focus:outline-none focus:ring-1 focus:ring-accentPrimary"
                  />
                </div>
                <div className="col-span-3">
                  <label className="mb-1 block font-mono uppercase tracking-wider text-textSecondary">
                    Discount (BPS)
                  </label>
                  <input
                    type="number"
                    min={minOfferDiscountBps}
                    max={maxOfferDiscountBps}
                    value={offers.campaignDiscountBps}
                    onChange={(e) =>
                      onUpdateOffers({
                        campaignDiscountBps: Math.max(0, parseInt(e.target.value || "0", 10)),
                      })
                    }
                    className="w-full rounded border border-borderSubtle bg-bgSurface px-2 py-1 font-mono text-xs text-textPrimary focus:border-accentPrimary focus:outline-none focus:ring-1 focus:ring-accentPrimary"
                  />
                  {errors.offer_campaign_discount && (
                    <p className="mt-0.5 text-xs text-statusError">
                      {errors.offer_campaign_discount}
                    </p>
                  )}
                </div>
                <div className="col-span-4">
                  <label className="mb-1 block font-mono uppercase tracking-wider text-textSecondary">
                    Cap (₹)
                  </label>
                  <input
                    type="text"
                    inputMode="decimal"
                    value={offers.campaignCapInr}
                    onChange={(e) => onUpdateOffers({ campaignCapInr: e.target.value })}
                    placeholder="blank = uncapped"
                    className="w-full rounded border border-borderSubtle bg-bgSurface px-2 py-1 font-mono text-xs text-textPrimary focus:border-accentPrimary focus:outline-none focus:ring-1 focus:ring-accentPrimary"
                  />
                  {errors.offer_campaign_cap && (
                    <p className="mt-0.5 text-xs text-statusError">{errors.offer_campaign_cap}</p>
                  )}
                </div>
                {offers.campaignDiscountBps > 0 && (
                  <p className="col-span-12 font-mono text-[10px] text-statusSuccess">
                    {(offers.campaignDiscountBps / 100).toFixed(2)}% off
                    {offers.campaignCapInr.trim().length > 0
                      ? `, never more than ₹${offers.campaignCapInr.trim()} per unit`
                      : ", uncapped"}
                  </p>
                )}
              </div>
            )}
          </div>

          <div className="rounded-md border border-borderSubtle bg-surfaceContainer px-3 py-3 text-xs">
            <label className="mb-1 block font-mono uppercase tracking-wider text-textSecondary">
              UPI Instant Cashback (₹)
            </label>
            <input
              type="text"
              inputMode="decimal"
              value={offers.paymentRailCashbackInr}
              onChange={(e) => onUpdateOffers({ paymentRailCashbackInr: e.target.value })}
              placeholder="blank = none"
              className="w-full max-w-[12rem] rounded border border-borderSubtle bg-bgSurface px-2 py-1 font-mono text-xs text-textPrimary focus:border-accentPrimary focus:outline-none focus:ring-1 focus:ring-accentPrimary"
            />
            {errors.offer_cashback && (
              <p className="mt-0.5 text-xs text-statusError">{errors.offer_cashback}</p>
            )}
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs uppercase tracking-wider text-textSecondary">
                Promo Codes
              </span>
              <button
                type="button"
                disabled={offers.promoCodes.length >= maxPromoCodesPerSku}
                onClick={() =>
                  onUpdateOffers({ promoCodes: [...offers.promoCodes, { ...emptyPromoCode }] })
                }
                className="flex items-center gap-1.5 rounded-md border border-accentPrimary/30 bg-accentSubtle px-3 py-1 text-xs font-medium text-accentPrimary transition hover:bg-accentPrimary hover:text-white disabled:opacity-40"
              >
                <Plus className="h-3.5 w-3.5" />
                <span>Add Code</span>
              </button>
            </div>

            {offers.promoCodes.length === 0 ? (
              <p className="rounded-lg border border-dashed border-borderSubtle p-4 text-center text-xs text-textMuted">
                No promo codes. An agent passing any code to get_live_sku_quote gets no discount.
              </p>
            ) : (
              offers.promoCodes.map((entry, index) => (
                <div
                  key={index}
                  className="grid grid-cols-12 items-start gap-3 rounded-md border border-borderSubtle bg-surfaceContainer px-3 py-2 text-xs"
                >
                  <div className="col-span-4">
                    <input
                      type="text"
                      value={entry.code}
                      onChange={(e) => updatePromoCode(index, { code: e.target.value })}
                      placeholder="MONSOON15"
                      className="w-full rounded border border-borderSubtle bg-bgSurface px-2 py-1 font-mono text-xs uppercase text-textPrimary focus:border-accentPrimary focus:outline-none focus:ring-1 focus:ring-accentPrimary"
                    />
                    {errors[`offer_promo_${index}_code`] && (
                      <p className="mt-0.5 text-xs text-statusError">
                        {errors[`offer_promo_${index}_code`]}
                      </p>
                    )}
                  </div>
                  <div className="col-span-3">
                    <input
                      type="number"
                      min={minOfferDiscountBps}
                      max={maxOfferDiscountBps}
                      value={entry.discountBps}
                      onChange={(e) =>
                        updatePromoCode(index, {
                          discountBps: Math.max(0, parseInt(e.target.value || "0", 10)),
                        })
                      }
                      className="w-full rounded border border-borderSubtle bg-bgSurface px-2 py-1 font-mono text-xs text-textPrimary focus:border-accentPrimary focus:outline-none focus:ring-1 focus:ring-accentPrimary"
                    />
                    {errors[`offer_promo_${index}_discount`] && (
                      <p className="mt-0.5 text-xs text-statusError">
                        {errors[`offer_promo_${index}_discount`]}
                      </p>
                    )}
                  </div>
                  <div className="col-span-4">
                    <input
                      type="text"
                      value={entry.label}
                      onChange={(e) => updatePromoCode(index, { label: e.target.value })}
                      placeholder="Label (optional)"
                      className="w-full rounded border border-borderSubtle bg-bgSurface px-2 py-1 text-xs text-textPrimary focus:border-accentPrimary focus:outline-none focus:ring-1 focus:ring-accentPrimary"
                    />
                  </div>
                  <div className="col-span-1 flex justify-end">
                    <button
                      type="button"
                      onClick={() =>
                        onUpdateOffers({
                          promoCodes: offers.promoCodes.filter((_, idx) => idx !== index),
                        })
                      }
                      title="Remove Code"
                      className="rounded p-1 text-textMuted transition hover:bg-statusError/10 hover:text-statusError"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              ))
            )}
            {errors.offer_promo_codes && (
              <p className="text-xs text-statusError">{errors.offer_promo_codes}</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
