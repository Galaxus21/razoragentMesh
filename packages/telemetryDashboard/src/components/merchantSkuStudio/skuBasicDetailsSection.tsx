"use client";

import React from "react";
import { Package } from "lucide-react";
import { categoryOptions, HsnPresetOption } from "@/constants/merchantCatalogConstants";
import { FormValidationErrors, MerchantCatalogFormData } from "@/types/merchantCatalogTypes";
import { InventoryFieldGroup } from "../skuBasicDetails/inventoryFieldGroup";
import { PricingFieldGroup } from "../skuBasicDetails/pricingFieldGroup";
import { TaxConfigFieldGroup } from "../skuBasicDetails/taxConfigFieldGroup";

export interface SkuBasicDetailsSectionProps {
  readonly formData: MerchantCatalogFormData;
  readonly errors: FormValidationErrors;
  readonly onChangeField: <K extends keyof MerchantCatalogFormData>(
    field: K,
    value: MerchantCatalogFormData[K]
  ) => void;
  readonly onHsnPresetSelect: (preset: HsnPresetOption) => void;
}

interface ProductInfoFieldsProps {
  readonly title: string;
  readonly description: string;
  readonly errors: FormValidationErrors;
  readonly onChangeField: <K extends keyof MerchantCatalogFormData>(
    field: K,
    value: MerchantCatalogFormData[K]
  ) => void;
}

export function SkuBasicDetailsSection(props: SkuBasicDetailsSectionProps): React.JSX.Element {
  const { formData, errors, onChangeField, onHsnPresetSelect } = props;
  return (
    <div className="rounded-lg border border-borderSubtle bg-bgSurface p-5 space-y-4">
      <SkuHeader />
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div>
          <label htmlFor="skuId" className="block text-xs font-medium text-textSecondary mb-1">SKU Identifier <span className="text-statusError">*</span></label>
          <input id="skuId" type="text" value={formData.skuId} onChange={(e) => onChangeField("skuId", e.target.value)} placeholder="e.g. SKU-JEWELRY-001" className={`w-full rounded-md border px-3 py-2 text-xs font-mono text-textPrimary bg-surfaceContainer focus:outline-none focus:ring-1 focus:ring-accentPrimary ${errors.skuId ? "border-statusError" : "border-borderSubtle focus:border-accentPrimary"}`} />
          {errors.skuId && <p className="mt-1 text-xs text-statusError">{errors.skuId}</p>}
        </div>
        <div>
          <label htmlFor="category" className="block text-xs font-medium text-textSecondary mb-1">Category <span className="text-statusError">*</span></label>
          <select id="category" value={formData.category} onChange={(e) => onChangeField("category", e.target.value)} className="w-full rounded-md border border-borderSubtle bg-surfaceContainer px-3 py-2 text-xs text-textPrimary focus:border-accentPrimary focus:outline-none focus:ring-1 focus:ring-accentPrimary">
            {categoryOptions.map((opt) => (<option key={opt} value={opt}>{opt}</option>))}
          </select>
        </div>
        <div>
          <label htmlFor="merchantDid" className="block text-xs font-medium text-textSecondary mb-1">Merchant DID</label>
          <input id="merchantDid" type="text" value={formData.merchantDid} onChange={(e) => onChangeField("merchantDid", e.target.value)} className="w-full rounded-md border border-borderSubtle bg-surfaceContainer/50 px-3 py-2 font-mono text-xs text-textMuted focus:outline-none" />
        </div>
      </div>
      <ProductInfoFields title={formData.title} description={formData.description} errors={errors} onChangeField={onChangeField} />
      <TaxConfigFieldGroup hsnCode={formData.hsnCode} gstRatePercent={formData.gstRatePercent} errors={errors} onChangeField={onChangeField} onHsnPresetSelect={onHsnPresetSelect} />
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 pt-2">
        <PricingFieldGroup basePriceInr={formData.basePriceInr} errors={errors} onChangeField={onChangeField} />
        <div className="md:col-span-3">
          <InventoryFieldGroup availableStock={formData.availableStock} originPincode={formData.originPincode} minimumOrderQuantity={formData.minimumOrderQuantity} errors={errors} onChangeField={onChangeField} />
        </div>
      </div>
    </div>
  );
}

function SkuHeader(): React.JSX.Element {
  return (
    <div className="flex items-center justify-between border-b border-borderSubtle pb-3">
      <div className="flex items-center gap-2">
        <Package className="h-4 w-4 text-statusInfo" />
        <h2 className="text-sm font-semibold text-textPrimary">SKU Specifications & Inventory</h2>
      </div>
      <span className="rounded bg-accentSubtle border border-accentPrimary/30 px-2 py-0.5 font-mono text-xs text-accentPrimary">Core Metadata</span>
    </div>
  );
}

function ProductInfoFields({ title, description, errors, onChangeField }: ProductInfoFieldsProps): React.JSX.Element {
  return (
    <>
      <div>
        <label htmlFor="title" className="block text-xs font-medium text-textSecondary mb-1">Product Title <span className="text-statusError">*</span></label>
        <input id="title" type="text" value={title} onChange={(e) => onChangeField("title", e.target.value)} placeholder="e.g. Handcrafted 22K Gold Filigree Ring" maxLength={150} className={`w-full rounded-md border px-3 py-2 text-xs text-textPrimary bg-surfaceContainer focus:outline-none focus:ring-1 focus:ring-accentPrimary ${errors.title ? "border-statusError" : "border-borderSubtle focus:border-accentPrimary"}`} />
        {errors.title && <p className="mt-1 text-xs text-statusError">{errors.title}</p>}
      </div>
      <div>
        <label htmlFor="description" className="block text-xs font-medium text-textSecondary mb-1">Product Description <span className="text-statusError">*</span></label>
        <textarea id="description" rows={2} value={description} onChange={(e) => onChangeField("description", e.target.value)} placeholder="Comprehensive description for autonomous agent discovery..." maxLength={500} className={`w-full rounded-md border px-3 py-2 text-xs text-textPrimary bg-surfaceContainer focus:outline-none focus:ring-1 focus:ring-accentPrimary ${errors.description ? "border-statusError" : "border-borderSubtle focus:border-accentPrimary"}`} />
        {errors.description && <p className="mt-1 text-xs text-statusError">{errors.description}</p>}
      </div>
    </>
  );
}
