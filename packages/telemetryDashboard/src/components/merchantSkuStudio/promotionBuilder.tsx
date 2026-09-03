"use client";

// Authors the scheduled flash sales that get_live_sku_quote reports as `upcoming_promotions`.
//
// Why this exists: the backend has supported scheduled promotions from the start, and a buyer
// agent that reads upcoming_promotions can tell its buyer to wait rather than spend -- the most
// persuasive thing the mesh does. But the Studio could not author one, so it could only ever be
// shown by posting raw JSON to the merchant API, which is not a demo.
//
// Mirrors volumeTierBuilder.tsx, its sibling, with one deliberate difference: the tier handlers
// clear no validation errors, so a stale `volumeTier_N_*` message stays on screen after the
// merchant has fixed the field. These handlers clear their own keys as they go.

import React from "react";
import { CalendarClock, Plus, Trash2 } from "lucide-react";
import {
  maxPromotionDiscountBps,
  minPromotionDiscountBps,
} from "@/constants/merchantCatalogConstants";
import {
  FormValidationErrors,
  PromotionDiscountKind,
  ScheduledPromotionInput,
} from "@/types/merchantCatalogTypes";

export interface PromotionBuilderProps {
  readonly promotions: ReadonlyArray<ScheduledPromotionInput>;
  readonly errors: FormValidationErrors;
  readonly onAddPromotion: () => void;
  readonly onRemovePromotion: (index: number) => void;
  readonly onUpdatePromotion: (index: number, updated: ScheduledPromotionInput) => void;
}

const discountKindLabels: ReadonlyArray<{ value: PromotionDiscountKind; label: string }> = [
  { value: "PERCENT", label: "% off" },
  { value: "FLAT_OFF", label: "₹ off" },
  { value: "FIXED_PRICE", label: "Fixed ₹" },
];

/**
 * datetime-local speaks local wall-clock with no zone; the schema wants unix seconds. Both
 * conversions go through these two so the round trip is lossless to the minute -- a promotion
 * that displays one hour off the time it was typed reads as a broken form.
 */
export function unixToDateTimeLocal(unixSeconds: number): string {
  if (!Number.isFinite(unixSeconds) || unixSeconds <= 0) {
    return "";
  }
  const date = new Date(unixSeconds * 1000);
  const offsetMs = date.getTimezoneOffset() * 60 * 1000;
  return new Date(date.getTime() - offsetMs).toISOString().slice(0, 16);
}

export function dateTimeLocalToUnix(value: string): number {
  if (!value) {
    return 0;
  }
  const parsed = Date.parse(value);
  return Number.isNaN(parsed) ? 0 : Math.floor(parsed / 1000);
}

export function PromotionBuilder({
  promotions,
  errors,
  onAddPromotion,
  onRemovePromotion,
  onUpdatePromotion,
}: PromotionBuilderProps): React.JSX.Element {
  return (
    <div className="rounded-lg border border-borderSubtle bg-bgSurface p-5 space-y-4">
      <div className="flex items-center justify-between border-b border-borderSubtle pb-3">
        <div className="flex items-center gap-2">
          <CalendarClock className="h-4 w-4 text-accentPrimary" />
          <h2 className="text-sm font-semibold text-textPrimary">Scheduled Promotions</h2>
        </div>
        <button
          type="button"
          onClick={onAddPromotion}
          className="flex items-center gap-1.5 rounded-md border border-accentPrimary/30 bg-accentSubtle px-3 py-1 text-xs font-medium text-accentPrimary transition hover:bg-accentPrimary hover:text-white"
        >
          <Plus className="h-3.5 w-3.5" />
          <span>Add Promotion</span>
        </button>
      </div>

      {promotions.length === 0 ? (
        <div className="rounded-lg border border-dashed border-borderSubtle p-6 text-center text-xs text-textMuted">
          <p>
            No promotions scheduled. A buyer agent quoting this SKU is told nothing about a future
            sale, so it will advise buying now.
          </p>
          <button
            type="button"
            onClick={onAddPromotion}
            className="mt-2 text-xs text-accentPrimary hover:underline"
          >
            Schedule a sale, and quotes will carry it as upcoming_promotions
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {promotions.map((promotion, index) => (
            <PromotionRow
              key={index}
              index={index}
              promotion={promotion}
              errors={errors}
              onRemovePromotion={onRemovePromotion}
              onUpdatePromotion={onUpdatePromotion}
            />
          ))}
        </div>
      )}
    </div>
  );
}

interface PromotionRowProps {
  readonly index: number;
  readonly promotion: ScheduledPromotionInput;
  readonly errors: FormValidationErrors;
  readonly onRemovePromotion: (index: number) => void;
  readonly onUpdatePromotion: (index: number, updated: ScheduledPromotionInput) => void;
}

function PromotionRow({
  index,
  promotion,
  errors,
  onRemovePromotion,
  onUpdatePromotion,
}: PromotionRowProps): React.JSX.Element {
  const update = (patch: Partial<ScheduledPromotionInput>): void =>
    onUpdatePromotion(index, { ...promotion, ...patch });

  const fieldError = (suffix: string): string | undefined => errors[`promotion_${index}_${suffix}`];

  return (
    <div className="space-y-2 rounded-md border border-borderSubtle bg-surfaceContainer px-3 py-3 text-xs">
      <div className="flex items-center justify-between">
        <span className="font-mono text-textSecondary">Campaign #{index + 1}</span>
        <button
          type="button"
          onClick={() => onRemovePromotion(index)}
          title="Remove Promotion"
          className="rounded p-1 text-textMuted transition hover:bg-statusError/10 hover:text-statusError"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>

      <div className="grid grid-cols-12 gap-3">
        <div className="col-span-4">
          <label className="mb-1 block font-mono uppercase tracking-wider text-textSecondary">
            Campaign ID
          </label>
          <input
            type="text"
            value={promotion.campaignId}
            onChange={(e) => update({ campaignId: e.target.value })}
            placeholder="DIWALI_2026"
            className="w-full rounded border border-borderSubtle bg-bgSurface px-2 py-1 font-mono text-xs text-textPrimary focus:border-accentPrimary focus:outline-none focus:ring-1 focus:ring-accentPrimary"
          />
          {fieldError("campaignId") && (
            <p className="mt-0.5 text-xs text-statusError">{fieldError("campaignId")}</p>
          )}
        </div>

        <div className="col-span-8">
          <label className="mb-1 block font-mono uppercase tracking-wider text-textSecondary">
            Display Name
          </label>
          <input
            type="text"
            value={promotion.name}
            onChange={(e) => update({ name: e.target.value })}
            placeholder="Diwali Flash Sale"
            className="w-full rounded border border-borderSubtle bg-bgSurface px-2 py-1 text-xs text-textPrimary focus:border-accentPrimary focus:outline-none focus:ring-1 focus:ring-accentPrimary"
          />
          {fieldError("name") && (
            <p className="mt-0.5 text-xs text-statusError">{fieldError("name")}</p>
          )}
        </div>

        <div className="col-span-6">
          <label className="mb-1 block font-mono uppercase tracking-wider text-textSecondary">
            Starts
          </label>
          <input
            type="datetime-local"
            value={unixToDateTimeLocal(promotion.startsAtUnix)}
            onChange={(e) => update({ startsAtUnix: dateTimeLocalToUnix(e.target.value) })}
            className="w-full rounded border border-borderSubtle bg-bgSurface px-2 py-1 font-mono text-xs text-textPrimary focus:border-accentPrimary focus:outline-none focus:ring-1 focus:ring-accentPrimary"
          />
          {fieldError("startsAt") && (
            <p className="mt-0.5 text-xs text-statusError">{fieldError("startsAt")}</p>
          )}
        </div>

        <div className="col-span-6">
          <label className="mb-1 block font-mono uppercase tracking-wider text-textSecondary">
            Ends
          </label>
          <input
            type="datetime-local"
            value={unixToDateTimeLocal(promotion.endsAtUnix)}
            onChange={(e) => update({ endsAtUnix: dateTimeLocalToUnix(e.target.value) })}
            className="w-full rounded border border-borderSubtle bg-bgSurface px-2 py-1 font-mono text-xs text-textPrimary focus:border-accentPrimary focus:outline-none focus:ring-1 focus:ring-accentPrimary"
          />
          {fieldError("endsAt") && (
            <p className="mt-0.5 text-xs text-statusError">{fieldError("endsAt")}</p>
          )}
        </div>

        <div className="col-span-4">
          <label className="mb-1 block font-mono uppercase tracking-wider text-textSecondary">
            Discount Type
          </label>
          <select
            value={promotion.discountKind}
            onChange={(e) => update({ discountKind: e.target.value as PromotionDiscountKind })}
            className="w-full rounded border border-borderSubtle bg-bgSurface px-2 py-1 text-xs text-textPrimary focus:border-accentPrimary focus:outline-none focus:ring-1 focus:ring-accentPrimary"
          >
            {discountKindLabels.map((kind) => (
              <option key={kind.value} value={kind.value}>
                {kind.label}
              </option>
            ))}
          </select>
        </div>

        <div className="col-span-4">
          <label className="mb-1 block font-mono uppercase tracking-wider text-textSecondary">
            {promotion.discountKind === "PERCENT" ? "Discount (BPS)" : "Amount (₹)"}
          </label>
          {promotion.discountKind === "PERCENT" ? (
            <input
              type="number"
              min={minPromotionDiscountBps}
              max={maxPromotionDiscountBps}
              value={promotion.discountBps}
              onChange={(e) =>
                update({ discountBps: Math.max(0, parseInt(e.target.value || "0", 10)) })
              }
              className="w-full rounded border border-borderSubtle bg-bgSurface px-2 py-1 font-mono text-xs text-textPrimary focus:border-accentPrimary focus:outline-none focus:ring-1 focus:ring-accentPrimary"
            />
          ) : (
            <input
              type="text"
              inputMode="decimal"
              value={
                promotion.discountKind === "FLAT_OFF"
                  ? promotion.discountInr
                  : promotion.fixedPriceInr
              }
              onChange={(e) =>
                update(
                  promotion.discountKind === "FLAT_OFF"
                    ? { discountInr: e.target.value }
                    : { fixedPriceInr: e.target.value }
                )
              }
              placeholder="0.00"
              className="w-full rounded border border-borderSubtle bg-bgSurface px-2 py-1 font-mono text-xs text-textPrimary focus:border-accentPrimary focus:outline-none focus:ring-1 focus:ring-accentPrimary"
            />
          )}
          {fieldError("discount") && (
            <p className="mt-0.5 text-xs text-statusError">{fieldError("discount")}</p>
          )}
        </div>

        <div className="col-span-4">
          <label className="mb-1 block font-mono uppercase tracking-wider text-textSecondary">
            Limited Stock
          </label>
          <input
            type="number"
            min={0}
            value={promotion.limitedStockAllocated}
            onChange={(e) =>
              update({ limitedStockAllocated: Math.max(0, parseInt(e.target.value || "0", 10)) })
            }
            className="w-full rounded border border-borderSubtle bg-bgSurface px-2 py-1 font-mono text-xs text-textPrimary focus:border-accentPrimary focus:outline-none focus:ring-1 focus:ring-accentPrimary"
          />
          <p className="mt-0.5 text-[10px] text-textMuted">0 = unlimited</p>
        </div>
      </div>

      {promotion.discountKind === "PERCENT" && promotion.discountBps > 0 && (
        <p className="font-mono text-[10px] text-statusSuccess">
          {(promotion.discountBps / 100).toFixed(2)}% off during the window
        </p>
      )}
    </div>
  );
}
