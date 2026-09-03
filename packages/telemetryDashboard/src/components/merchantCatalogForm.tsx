"use client";

import React from "react";
import { useMerchantCatalogForm } from "@/hooks/useMerchantCatalogForm";
import { FormHeader } from "./merchantCatalog/formHeader";
import { BullionPricingSection } from "./merchantSkuStudio/bullionPricingSection";
import { CatalogJsonPreview } from "./merchantSkuStudio/catalogJsonPreview";
import { DomainFacetSection } from "./merchantSkuStudio/domainFacetSection";
import { SkuBasicDetailsSection } from "./merchantSkuStudio/skuBasicDetailsSection";
import { VolumeTierBuilder } from "./merchantSkuStudio/volumeTierBuilder";
import { PromotionBuilder } from "./merchantSkuStudio/promotionBuilder";
import { MerchantOffersBuilder } from "./merchantSkuStudio/merchantOffersBuilder";
import { NegotiationPolicyPanel } from "./merchantSkuStudio/negotiationPolicyPanel";
import { useNegotiationPolicy } from "@/hooks/useNegotiationPolicy";
import { convertInrToPaise } from "@/lib/merchantCatalogValidator";

export function MerchantCatalogForm(): React.JSX.Element {
  const form = useMerchantCatalogForm();
  // The policy belongs to the merchant, not to this listing, so it saves on its own button. The
  // listing's DID and price are passed only so the panel can prefill and show what the merchant's
  // margin floor works out to in rupees on the SKU in front of them.
  const policy = useNegotiationPolicy(form.formData.merchantDid);

  return (
    <div className="space-y-6 px-6 max-w-7xl mx-auto">
      <FormHeader />
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-7 space-y-6">
          <SkuBasicDetailsSection formData={form.formData} errors={form.errors} onChangeField={form.handleChangeField} onHsnPresetSelect={form.handleHsnPresetSelect} />
          <VolumeTierBuilder volumeTiers={form.formData.volumeTiers} errors={form.errors} onAddTier={form.handleAddVolumeTier} onRemoveTier={form.handleRemoveVolumeTier} onUpdateTier={form.handleUpdateVolumeTier} />
          <PromotionBuilder promotions={form.formData.promotions} errors={form.errors} onAddPromotion={form.handleAddPromotion} onRemovePromotion={form.handleRemovePromotion} onUpdatePromotion={form.handleUpdatePromotion} />
          <MerchantOffersBuilder offers={form.formData.offers} errors={form.errors} onUpdateOffers={form.handleUpdateOffers} />
          <NegotiationPolicyPanel policy={policy.policy} errors={policy.errors} isSaving={policy.isSaving} saveResult={policy.saveResult} previewListPricePaise={convertInrToPaise(form.formData.basePriceInr)} onUpdatePolicy={policy.handleUpdatePolicy} onSavePolicy={() => void policy.handleSavePolicy()} />
          <BullionPricingSection bullionPricing={form.formData.bullionPricing} errors={form.errors} onUpdateBullion={form.handleUpdateBullion} />
          <DomainFacetSection selectedFacet={form.formData.selectedFacet} jewelryFacet={form.formData.jewelryFacet} apparelFacet={form.formData.apparelFacet} pharmaFacet={form.formData.pharmaFacet} fmcgFacet={form.formData.fmcgFacet} errors={form.errors} onSelectFacet={form.handleSelectFacet} onUpdateJewelry={form.handleUpdateJewelry} onUpdateApparel={form.handleUpdateApparel} onUpdatePharma={form.handleUpdatePharma} onUpdateFmcg={form.handleUpdateFmcg} />
        </div>
        <div className="lg:col-span-5 space-y-6">
          <div className="sticky top-6">
            <CatalogJsonPreview payload={form.payload} isSubmitting={form.isSubmitting} submissionResult={form.submissionResult} onPublish={form.handlePublishToMesh} onReset={form.handleResetForm} />
          </div>
        </div>
      </div>
    </div>
  );
}
