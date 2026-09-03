import { useCallback, useMemo, useState } from "react";
import {
  defaultCatalogFormState,
  defaultPromotionDiscountBps,
  defaultPromotionLeadSeconds,
  defaultPromotionWindowSeconds,
  HsnPresetOption,
  meshCatalogProxyEndpoint,
  millisecondsPerSecond,
} from "@/constants/merchantCatalogConstants";
import {
  buildUniversalProductPayload,
  resolveGstFromHsn,
  validateMerchantCatalogForm,
} from "@/lib/merchantCatalogValidator";
import {
  ApparelFacetFormData,
  BullionPricingFormData,
  CatalogSubmissionResult,
  DomainFacetType,
  FmcgFacetFormData,
  FormValidationErrors,
  JewelryFacetFormData,
  MerchantCatalogFormData,
  MerchantOffersFormData,
  PharmaFacetFormData,
  ScheduledPromotionInput,
  UniversalProductListingPayload,
  VolumeTierInput,
} from "@/types/merchantCatalogTypes";

/**
 * Drops every validation message belonging to one promotion row.
 *
 * Keys are positional (`promotion_2_name`), so a removal would otherwise leave the deleted row's
 * errors pointing at whichever row slid into its index. Rebuilding the map is cheap and keeps
 * the numbering honest.
 */
function _withoutPromotionErrors(
  errors: FormValidationErrors,
  index: number
): FormValidationErrors {
  const prefix = `promotion_${index}_`;
  const remaining: FormValidationErrors = {};
  for (const [key, message] of Object.entries(errors)) {
    if (!key.startsWith(prefix)) {
      remaining[key] = message;
    }
  }
  return remaining;
}

export interface UseMerchantCatalogFormReturn {
  readonly formData: MerchantCatalogFormData;
  readonly errors: FormValidationErrors;
  readonly isSubmitting: boolean;
  readonly submissionResult: CatalogSubmissionResult | null;
  readonly payload: UniversalProductListingPayload;
  readonly handleChangeField: <K extends keyof MerchantCatalogFormData>(
    field: K,
    value: MerchantCatalogFormData[K]
  ) => void;
  readonly handleHsnPresetSelect: (preset: HsnPresetOption) => void;
  readonly handleAddVolumeTier: () => void;
  readonly handleRemoveVolumeTier: (index: number) => void;
  readonly handleUpdateVolumeTier: (index: number, updated: VolumeTierInput) => void;
  readonly handleAddPromotion: () => void;
  readonly handleRemovePromotion: (index: number) => void;
  readonly handleUpdatePromotion: (index: number, updated: ScheduledPromotionInput) => void;
  readonly handleUpdateOffers: (patch: Partial<MerchantOffersFormData>) => void;
  readonly handleUpdateBullion: <K extends keyof BullionPricingFormData>(
    field: K,
    value: BullionPricingFormData[K]
  ) => void;
  readonly handleSelectFacet: (facet: DomainFacetType) => void;
  readonly handleUpdateJewelry: <K extends keyof JewelryFacetFormData>(
    field: K,
    value: JewelryFacetFormData[K]
  ) => void;
  readonly handleUpdateApparel: <K extends keyof ApparelFacetFormData>(
    field: K,
    value: ApparelFacetFormData[K]
  ) => void;
  readonly handleUpdatePharma: <K extends keyof PharmaFacetFormData>(
    field: K,
    value: PharmaFacetFormData[K]
  ) => void;
  readonly handleUpdateFmcg: <K extends keyof FmcgFacetFormData>(
    field: K,
    value: FmcgFacetFormData[K]
  ) => void;
  readonly handleResetForm: () => void;
  readonly handlePublishToMesh: () => Promise<void>;
}

export function useMerchantCatalogForm(): UseMerchantCatalogFormReturn {
  const [formData, setFormData] = useState<MerchantCatalogFormData>(defaultCatalogFormState);
  const [errors, setErrors] = useState<FormValidationErrors>({});
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [submissionResult, setSubmissionResult] = useState<CatalogSubmissionResult | null>(null);

  const handleChangeField = useCallback(
    <K extends keyof MerchantCatalogFormData>(field: K, value: MerchantCatalogFormData[K]) => {
      setFormData((prev) => {
        const next = { ...prev, [field]: value };
        if (field === "hsnCode" && typeof value === "string") {
          next.gstRatePercent = resolveGstFromHsn(value);
        }
        return next;
      });
      setErrors((prev) => {
        if (!prev[field]) return prev;
        const updated = { ...prev };
        delete updated[field];
        return updated;
      });
    },
    []
  );

  const handleHsnPresetSelect = useCallback((preset: HsnPresetOption) => {
    setFormData((prev) => {
      const lower = preset.category.toLowerCase();
      const facet: DomainFacetType =
        lower === "jewelry" || lower === "apparel" || lower === "pharma" || lower === "fmcg"
          ? lower
          : prev.selectedFacet;
      return {
        ...prev,
        hsnCode: preset.hsn,
        gstRatePercent: preset.gstRate,
        category: preset.category,
        selectedFacet: facet,
      };
    });
  }, []);

  const handleAddVolumeTier = useCallback(() => {
    setFormData((prev) => {
      const last = prev.volumeTiers[prev.volumeTiers.length - 1];
      const nextMinQty = last ? last.minQuantity + 5 : 5;
      const nextBps = last ? Math.min(10000, last.discountBps + 250) : 250;
      return {
        ...prev,
        volumeTiers: [...prev.volumeTiers, { minQuantity: nextMinQty, discountBps: nextBps }],
      };
    });
  }, []);

  const handleRemoveVolumeTier = useCallback((index: number) => {
    setFormData((prev) => ({
      ...prev,
      volumeTiers: prev.volumeTiers.filter((_, idx) => idx !== index),
    }));
  }, []);

  const handleUpdateVolumeTier = useCallback((index: number, updated: VolumeTierInput) => {
    setFormData((prev) => ({
      ...prev,
      volumeTiers: prev.volumeTiers.map((tier, idx) => (idx === index ? updated : tier)),
    }));
  }, []);

  const handleAddPromotion = useCallback(() => {
    setFormData((prev) => {
      // Seeded relative to now rather than left blank, so the window is already valid and a
      // merchant demonstrating the feature does not have to type two timestamps to see it work.
      // Computed in the handler, not at module scope: a Date.now() evaluated during render would
      // differ between the server and the client and break hydration.
      const startsAtUnix =
        Math.floor(Date.now() / millisecondsPerSecond) + defaultPromotionLeadSeconds;
      return {
        ...prev,
        promotions: [
          ...prev.promotions,
          {
            campaignId: `CAMPAIGN_${prev.promotions.length + 1}`,
            name: "",
            startsAtUnix,
            endsAtUnix: startsAtUnix + defaultPromotionWindowSeconds,
            discountKind: "PERCENT",
            discountBps: defaultPromotionDiscountBps,
            discountInr: "",
            fixedPriceInr: "",
            limitedStockAllocated: 0,
          },
        ],
      };
    });
  }, []);

  const handleRemovePromotion = useCallback((index: number) => {
    setFormData((prev) => ({
      ...prev,
      promotions: prev.promotions.filter((_, idx) => idx !== index),
    }));
    // Cleared, unlike the volume tier handlers above: a stale promotion_N_* message left on a
    // field the merchant has already fixed -- or on a row they have deleted -- reads as a form
    // that will not let them publish.
    setErrors((prev) => _withoutPromotionErrors(prev, index));
  }, []);

  const handleUpdatePromotion = useCallback((index: number, updated: ScheduledPromotionInput) => {
    setFormData((prev) => ({
      ...prev,
      promotions: prev.promotions.map((promotion, idx) => (idx === index ? updated : promotion)),
    }));
    setErrors((prev) => _withoutPromotionErrors(prev, index));
  }, []);

  /**
   * Patch-shaped rather than field-and-value: the promo-code list is edited as a whole array by
   * the builder, and a per-field setter would force it to read current state to append a row.
   *
   * Clears every offer error rather than only the patched key, because the offer errors are
   * positional (`offer_promo_2_code`) and a removal slides the rows underneath it -- leaving a
   * message pointing at whichever row moved into that index.
   */
  const handleUpdateOffers = useCallback((patch: Partial<MerchantOffersFormData>) => {
    setFormData((prev) => ({ ...prev, offers: { ...prev.offers, ...patch } }));
    setErrors((prev) => {
      const remaining: FormValidationErrors = {};
      for (const [key, message] of Object.entries(prev)) {
        if (!key.startsWith("offer_")) {
          remaining[key] = message;
        }
      }
      return remaining;
    });
  }, []);

  const handleUpdateBullion = useCallback(
    <K extends keyof BullionPricingFormData>(field: K, value: BullionPricingFormData[K]) => {
      setFormData((prev) => ({
        ...prev,
        bullionPricing: { ...prev.bullionPricing, [field]: value },
      }));
    },
    []
  );

  const handleSelectFacet = useCallback((facet: DomainFacetType) => {
    setFormData((prev) => ({ ...prev, selectedFacet: facet }));
  }, []);

  const handleUpdateJewelry = useCallback(
    <K extends keyof JewelryFacetFormData>(field: K, value: JewelryFacetFormData[K]) => {
      setFormData((prev) => ({
        ...prev,
        jewelryFacet: { ...prev.jewelryFacet, [field]: value },
      }));
    },
    []
  );

  const handleUpdateApparel = useCallback(
    <K extends keyof ApparelFacetFormData>(field: K, value: ApparelFacetFormData[K]) => {
      setFormData((prev) => ({
        ...prev,
        apparelFacet: { ...prev.apparelFacet, [field]: value },
      }));
    },
    []
  );

  const handleUpdatePharma = useCallback(
    <K extends keyof PharmaFacetFormData>(field: K, value: PharmaFacetFormData[K]) => {
      setFormData((prev) => ({
        ...prev,
        pharmaFacet: { ...prev.pharmaFacet, [field]: value },
      }));
    },
    []
  );

  const handleUpdateFmcg = useCallback(
    <K extends keyof FmcgFacetFormData>(field: K, value: FmcgFacetFormData[K]) => {
      setFormData((prev) => ({
        ...prev,
        fmcgFacet: { ...prev.fmcgFacet, [field]: value },
      }));
    },
    []
  );

  const handleResetForm = useCallback(() => {
    setFormData(defaultCatalogFormState);
    setErrors({});
    setSubmissionResult(null);
  }, []);

  const payload = useMemo(() => buildUniversalProductPayload(formData), [formData]);

  const handlePublishToMesh = useCallback(async () => {
    const validation = validateMerchantCatalogForm(formData);
    if (!validation.isValid) {
      setErrors(validation.errors);
      setSubmissionResult({
        status: "error",
        message: "Form validation failed. Please correct the highlighted errors.",
      });
      return;
    }
    setIsSubmitting(true);
    setSubmissionResult(null);
    try {
      // Server-side proxy, not the merchant API directly. The previous relative path resolved
      // against the dashboard origin, where nothing serves it, so every publish 404ed and no
      // listing ever reached the mesh. The browser cannot call port 4002 itself either: inside
      // Docker the merchant API is addressable only by compose service name.
      const response = await fetch(meshCatalogProxyEndpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (response.ok) {
        setSubmissionResult({
          status: "success",
          message: `SKU successfully published to Mesh catalog! (HTTP ${response.status})`,
          skuId: formData.skuId,
          merchantDid: formData.merchantDid,
          timestampMs: Date.now(),
        });
      } else {
        const errorText = await response.text().catch(() => "Unknown error");
        setSubmissionResult({
          status: "error",
          message: `Mesh catalog rejected listing: ${errorText} (HTTP ${response.status})`,
        });
      }
    } catch (error: unknown) {
      // A publish that did not happen is a failure, reported as one. This branch used to say
      // "Validated payload synthesized and ready for deployment", which reads like success --
      // so a merchant whose listing never reached the mesh was told it had.
      const detail = error instanceof Error ? error.message : String(error);
      setSubmissionResult({
        status: "error",
        message: `Publish failed -- the dashboard could not be reached: ${detail}`,
      });
    } finally {
      setIsSubmitting(false);
    }
  }, [formData, payload]);

  return {
    formData,
    errors,
    isSubmitting,
    submissionResult,
    payload,
    handleChangeField,
    handleHsnPresetSelect,
    handleAddVolumeTier,
    handleRemoveVolumeTier,
    handleUpdateVolumeTier,
    handleAddPromotion,
    handleRemovePromotion,
    handleUpdatePromotion,
    handleUpdateOffers,
    handleUpdateBullion,
    handleSelectFacet,
    handleUpdateJewelry,
    handleUpdateApparel,
    handleUpdatePharma,
    handleUpdateFmcg,
    handleResetForm,
    handlePublishToMesh,
  };
}
