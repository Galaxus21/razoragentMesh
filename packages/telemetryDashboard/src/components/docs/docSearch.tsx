"use client";

// Search across every guide, matched in the browser against the generated index.
//
// There is no server round trip and no search service: the whole index is built at build time
// and scanned as an array on each keystroke. That also means results stay correct on a
// statically exported build, where there is no server to ask.

import React, { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Search } from "lucide-react";
import { docsSearchIndex } from "@/generated/docsSearchIndex";
import { searchDocs, type DocSearchResult } from "@/lib/docsSearchMatcher";

const placeholderText = "Search the guides";
const focusShortcutKey = "/";
const emptyResultsText = "No section matches that.";

function useSlashToFocus(inputRef: React.RefObject<HTMLInputElement | null>): void {
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent): void => {
      const target = event.target as HTMLElement | null;
      const isTypingElsewhere =
        target?.tagName === "INPUT" ||
        target?.tagName === "TEXTAREA" ||
        target?.isContentEditable === true;
      if (event.key !== focusShortcutKey || isTypingElsewhere) {
        return;
      }
      event.preventDefault();
      inputRef.current?.focus();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [inputRef]);
}

function ResultRow({
  result,
  isActive,
  onSelect,
}: {
  readonly result: DocSearchResult;
  readonly isActive: boolean;
  readonly onSelect: () => void;
}): React.JSX.Element {
  return (
    <li>
      <button
        type="button"
        onMouseDown={onSelect}
        className={`block w-full rounded px-2 py-1.5 text-left transition-colors ${
          isActive ? "bg-bgSurfaceHover" : "hover:bg-bgSurfaceHover"
        }`}
      >
        <span className="block text-body-sm font-medium text-textPrimary">
          {result.entry.headingText || result.entry.docTitle}
        </span>
        <span className="block text-[11px] text-textMuted">{result.entry.docTitle}</span>
        {result.entry.snippet ? (
          <span className="mt-0.5 block line-clamp-2 text-[11px] leading-snug text-textSecondary">
            {result.entry.snippet}
          </span>
        ) : null}
      </button>
    </li>
  );
}

export function DocSearch(): React.JSX.Element {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState<string>("");
  const [activeIndex, setActiveIndex] = useState<number>(0);
  const [isOpen, setIsOpen] = useState<boolean>(false);

  useSlashToFocus(inputRef);

  const results = useMemo(() => searchDocs(docsSearchIndex, query), [query]);

  // A shrinking result list must not leave the highlight pointing past its end.
  useEffect(() => {
    setActiveIndex(0);
  }, [query]);

  const goToResult = (result: DocSearchResult | undefined): void => {
    if (!result) {
      return;
    }
    setIsOpen(false);
    setQuery("");
    router.push(result.entry.route);
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>): void => {
    if (event.key === "Escape") {
      setIsOpen(false);
      inputRef.current?.blur();
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((current) => Math.min(current + 1, results.length - 1));
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((current) => Math.max(current - 1, 0));
      return;
    }
    if (event.key === "Enter") {
      event.preventDefault();
      goToResult(results[activeIndex]);
    }
  };

  const hasQuery = query.trim().length > 0;

  return (
    <div className="relative mb-4">
      <div className="flex items-center gap-1.5 rounded-md border border-borderSubtle bg-bgSurface px-2 py-1.5 focus-within:border-accentPrimary">
        <Search className="h-3.5 w-3.5 shrink-0 text-textMuted" />
        <input
          ref={inputRef}
          type="search"
          role="searchbox"
          aria-label={placeholderText}
          value={query}
          placeholder={placeholderText}
          onChange={(event) => {
            setQuery(event.target.value);
            setIsOpen(true);
          }}
          onFocus={() => setIsOpen(true)}
          onBlur={() => setIsOpen(false)}
          onKeyDown={handleKeyDown}
          className="w-full bg-transparent text-body-sm text-textPrimary outline-none placeholder:text-textMuted"
        />
      </div>

      {isOpen && hasQuery ? (
        <div className="absolute z-20 mt-1 max-h-96 w-full overflow-y-auto custom-scrollbar rounded-md border border-borderSubtle bg-bgSurface p-1 shadow-lg">
          {results.length === 0 ? (
            <p className="px-2 py-1.5 text-[11px] text-textMuted">{emptyResultsText}</p>
          ) : (
            <ul>
              {results.map((result, index) => (
                <ResultRow
                  key={result.entry.route}
                  result={result}
                  isActive={index === activeIndex}
                  onSelect={() => goToResult(result)}
                />
              ))}
            </ul>
          )}
        </div>
      ) : null}
    </div>
  );
}
