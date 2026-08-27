import React from "react";
import { Loader2, Send } from "lucide-react";

export interface FormActionBarProps {
  readonly isSubmitting: boolean;
  readonly onPublish: () => void;
  readonly apiEndpointDescription?: string;
}

export function FormActionBar({
  isSubmitting,
  onPublish,
  apiEndpointDescription = "POST /api/v1/merchant/:merchantDid/catalog",
}: FormActionBarProps): React.JSX.Element {
  return (
    <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-2">
      <div className="text-xs text-textMuted">
        Publishes to <code className="font-mono text-statusInfo">{apiEndpointDescription}</code>
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
  );
}
