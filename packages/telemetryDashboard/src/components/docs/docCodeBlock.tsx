"use client";

import React, { useState } from "react";
import { Check, Copy } from "lucide-react";

export interface DocCodeBlockProps {
  readonly code: string;
  readonly language?: string;
}

const copySuccessTimeoutMs = 2000;
const copyButtonTitle = "Copy snippet";
const copiedLabel = "Copied";
const copyLabel = "Copy";
const defaultLanguage = "text";

export function DocCodeBlock({
  code,
  language = defaultLanguage,
}: DocCodeBlockProps): React.JSX.Element {
  const [isCopied, setIsCopied] = useState<boolean>(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), copySuccessTimeoutMs);
    } catch {
      setIsCopied(false);
    }
  };

  return (
    <div className="relative my-4 rounded-md border border-borderSubtle bg-bgBase p-3.5 font-mono text-xs text-textPrimary">
      <div className="flex items-center justify-between pb-2 mb-2 border-b border-borderSubtle text-[11px] text-textMuted">
        <span className="font-semibold uppercase tracking-wider">{language}</span>
        <button
          type="button"
          onClick={handleCopy}
          className="flex items-center gap-1 hover:text-textPrimary transition-colors"
          title={copyButtonTitle}
        >
          {isCopied ? (
            <Check className="h-3 w-3 text-statusSuccess" />
          ) : (
            <Copy className="h-3 w-3" />
          )}
          <span className={isCopied ? "text-statusSuccess" : ""}>
            {isCopied ? copiedLabel : copyLabel}
          </span>
        </button>
      </div>
      <pre className="overflow-x-auto custom-scrollbar leading-relaxed whitespace-pre-wrap">
        {code}
      </pre>
    </div>
  );
}
