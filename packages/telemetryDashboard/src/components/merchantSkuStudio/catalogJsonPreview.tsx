"use client";

import React, { useState } from "react";
import {
  AlertCircle,
  Check,
  CheckCircle2,
  Code2,
  Copy,
  Loader2,
  RotateCcw,
  Send,
} from "lucide-react";
import {
  CatalogSubmissionResult,
  UniversalProductListingPayload,
} from "@/types/merchantCatalogTypes";

export interface CatalogJsonPreviewProps {
  readonly payload: UniversalProductListingPayload;
  readonly isSubmitting: boolean;
  readonly submissionResult: CatalogSubmissionResult | null;
  readonly onPublish: () => void;
  readonly onReset: () => void;
}

export function CatalogJsonPreview({
  payload,
  isSubmitting,
  submissionResult,
  onPublish,
  onReset,
}: CatalogJsonPreviewProps): React.JSX.Element {
  const [copied, setCopied] = useState(false);
  const jsonString = JSON.stringify(payload, null, 2);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(jsonString);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="rounded-lg border border-borderSubtle bg-bgSurface p-5 space-y-4">
      <div className="flex items-center justify-between border-b border-borderSubtle pb-3">
        <div className="flex items-center gap-2">
          <Code2 className="h-4 w-4 text-statusInfo" />
          <h2 className="text-sm font-semibold text-textPrimary">Universal Catalog Payload Preview</h2>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleCopy}
            className="flex items-center gap-1.5 rounded-md border border-borderSubtle bg-bgSurface px-3 py-1 text-xs text-textSecondary transition hover:bg-bgSurfaceHover hover:text-textPrimary"
          >
            {copied ? (
              <>
                <Check className="h-3.5 w-3.5 text-statusSuccess" />
                <span className="text-statusSuccess">Copied</span>
              </>
            ) : (
              <>
                <Copy className="h-3.5 w-3.5" />
                <span>Copy JSON</span>
              </>
            )}
          </button>

          <button
            type="button"
            onClick={onReset}
            title="Reset Form"
            className="flex items-center gap-1.5 rounded-md border border-borderSubtle bg-bgSurface px-3 py-1 text-xs text-textMuted transition hover:bg-bgSurfaceHover hover:text-textSecondary"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            <span>Reset</span>
          </button>
        </div>
      </div>

      {/* Real-time formatted code block */}
      <div className="relative rounded-md border border-borderSubtle bg-bgBase p-4">
        <pre className="max-h-72 overflow-y-auto font-mono text-xs leading-relaxed text-textPrimary custom-scrollbar">
          <code>{jsonString}</code>
        </pre>
      </div>

      {/* Submission Status Alert */}
      {submissionResult && (
        <div
          className={`flex items-start gap-2.5 rounded-lg border p-3 text-xs ${
            submissionResult.status === "success"
              ? "border-statusSuccess/30 bg-statusSuccess/10 text-statusSuccess"
              : "border-statusError/30 bg-statusError/10 text-statusError"
          }`}
        >
          {submissionResult.status === "success" && (
            <CheckCircle2 className="h-4 w-4 shrink-0 text-statusSuccess mt-0.5" />
          )}
          {submissionResult.status === "error" && (
            <AlertCircle className="h-4 w-4 shrink-0 text-statusError mt-0.5" />
          )}
          <div className="flex-1">
            <p className="font-semibold">{submissionResult.message}</p>
            {submissionResult.skuId && (
              <p className="font-mono text-xs opacity-80">SKU: {submissionResult.skuId}</p>
            )}
          </div>
        </div>
      )}

      {/* Action Footer */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-2">
        <div className="text-xs text-textMuted">
          Publishes to <code className="font-mono text-statusInfo">POST /api/mesh/catalog</code>
        </div>

        <button
          type="button"
          onClick={onPublish}
          disabled={isSubmitting}
          className="flex w-full sm:w-auto items-center justify-center gap-2 rounded-lg bg-accentPrimary hover:bg-accentPrimary/90 px-6 py-2.5 text-xs font-semibold text-white transition disabled:opacity-50"
        >
          {isSubmitting ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>Publishing to Mesh...</span>
            </>
          ) : (
            <>
              <Send className="h-4 w-4" />
              <span>Publish SKU to Mesh</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
}
