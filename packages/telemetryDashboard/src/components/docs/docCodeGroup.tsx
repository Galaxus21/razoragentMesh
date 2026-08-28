"use client";

import React, { useState, useEffect } from "react";
import hljs from "highlight.js";
import { Check, Copy } from "lucide-react";

export interface CodeTabItem {
  readonly language: string;
  readonly code: string;
}

export interface DocCodeGroupProps {
  readonly items: readonly CodeTabItem[];
  readonly globalLanguage?: string;
}

const copyFeedbackTimeoutMs = 2000;

function formatTabLabel(lang: string): string {
  const normalized = lang.toLowerCase();
  if (normalized === "curl" || normalized === "bash" || normalized === "sh" || normalized === "shell") return "cURL";
  if (normalized === "fetch" || normalized === "javascript" || normalized === "js") return "Fetch API";
  if (normalized === "ts" || normalized === "typescript") return "TypeScript";
  if (normalized === "py" || normalized === "python") return "Python";
  if (normalized === "json") return "JSON";
  if (normalized === "env") return "ENV";
  return lang.toUpperCase();
}

function highlightCode(code: string, lang: string): string {
  const normalized = lang.toLowerCase();
  const targetLang =
    normalized === "curl" ? "bash" : normalized === "fetch" ? "javascript" : normalized;
  const validLang = targetLang && hljs.getLanguage(targetLang) ? targetLang : undefined;
  if (validLang) {
    return hljs.highlight(code, { language: validLang }).value;
  }
  return hljs.highlightAuto(code).value;
}

export function DocCodeGroup({
  items,
  globalLanguage,
}: DocCodeGroupProps): React.JSX.Element {
  const [activeIndex, setActiveIndex] = useState<number>(0);
  const [isCopied, setIsCopied] = useState<boolean>(false);

  useEffect(() => {
    if (!globalLanguage) return;
    const matchIndex = items.findIndex(
      (item) => formatTabLabel(item.language).toLowerCase() === globalLanguage.toLowerCase()
    );
    if (matchIndex >= 0) {
      setActiveIndex(matchIndex);
    }
  }, [globalLanguage, items]);

  const currentItem = items[activeIndex] || items[0];
  if (!currentItem) return <React.Fragment />;

  const isMultiTab = items.length > 1;
  const currentLangName = formatTabLabel(currentItem.language);
  const highlightedHtml = highlightCode(currentItem.code, currentItem.language);

  const handleCopy = () => {
    navigator.clipboard
      .writeText(currentItem.code)
      .then(() => {
        setIsCopied(true);
        setTimeout(() => setIsCopied(false), copyFeedbackTimeoutMs);
      })
      .catch(() => {});
  };

  return (
    <div className="relative my-5 rounded-lg border border-borderSubtle bg-bgBase overflow-hidden shadow-xs">
      <div className="flex items-center justify-between px-3 py-2 bg-surfaceContainer border-b border-borderSubtle select-none">
        {isMultiTab ? (
          <div className="flex items-center gap-1">
            {items.map((item, index) => {
              const label = formatTabLabel(item.language);
              const isActive = index === activeIndex;
              return (
                <button
                  key={`${item.language}-${index}`}
                  type="button"
                  onClick={() => setActiveIndex(index)}
                  className={`px-3 py-1 rounded-md text-xs font-mono transition-all cursor-pointer ${
                    isActive
                      ? "bg-bgSurface text-accentPrimary font-semibold shadow-xs border border-borderSubtle"
                      : "text-textMuted hover:text-textPrimary font-medium"
                  }`}
                >
                  {label}
                </button>
              );
            })}
          </div>
        ) : (
          <span className="text-[11px] font-mono font-semibold text-accentPrimary tracking-wider px-1">
            {currentLangName}
          </span>
        )}

        <button
          type="button"
          onClick={handleCopy}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded text-[11px] text-textSecondary hover:text-textPrimary hover:bg-bgSurface transition-colors cursor-pointer"
        >
          {isCopied ? (
            <>
              <Check className="h-3 w-3 text-statusSuccess" />
              <span className="text-statusSuccess font-sans">Copied!</span>
            </>
          ) : (
            <>
              <Copy className="h-3 w-3" />
              <span className="font-sans">Copy</span>
            </>
          )}
        </button>
      </div>

      <pre className="p-4 overflow-x-auto custom-scrollbar text-xs font-mono leading-relaxed bg-transparent m-0 border-none">
        <code
          className={`hljs language-${currentItem.language || "text"}`}
          dangerouslySetInnerHTML={{ __html: highlightedHtml }}
        />
      </pre>
    </div>
  );
}
