"use client";

import React, { useMemo, useState } from "react";
import { marked, type Tokens, type TokensList } from "marked";
import { DocCodeGroup, CodeTabItem } from "./docCodeGroup";
import { Code2 } from "lucide-react";

export interface MarkdownViewerProps {
  readonly markdown: string;
  readonly showLanguageToggle?: boolean;
}

interface ParsedSection {
  readonly id: string;
  readonly type: "html" | "code_group";
  readonly htmlContent?: string;
  readonly codeItems?: readonly CodeTabItem[];
}

function parseMarkdownTokens(markdown: string): readonly ParsedSection[] {
  const tokens = marked.lexer(markdown);
  const sections: ParsedSection[] = [];
  let currentHtmlTokens: Tokens.Generic[] = [];
  let sectionCounter = 0;

  const flushHtmlTokens = () => {
    if (currentHtmlTokens.length === 0) return;
    const html = marked.parser(currentHtmlTokens as unknown as TokensList);
    if (html.trim()) {
      sections.push({
        id: `html-${sectionCounter++}`,
        type: "html",
        htmlContent: html,
      });
    }
    currentHtmlTokens = [];
  };

  let i = 0;
  while (i < tokens.length) {
    const token = tokens[i];

    if (token && token.type === "code") {
      flushHtmlTokens();
      const codeToken = token as Tokens.Code;
      const codeItems: CodeTabItem[] = [
        {
          language: codeToken.lang || "text",
          code: codeToken.text || "",
        },
      ];

      let nextIndex = i + 1;
      while (nextIndex < tokens.length) {
        const nextToken = tokens[nextIndex];
        if (nextToken && nextToken.type === "space") {
          nextIndex++;
          continue;
        }
        if (nextToken && nextToken.type === "code") {
          const nextCodeToken = nextToken as Tokens.Code;
          codeItems.push({
            language: nextCodeToken.lang || "text",
            code: nextCodeToken.text || "",
          });
          nextIndex++;
        } else {
          break;
        }
      }

      sections.push({
        id: `code-${sectionCounter++}`,
        type: "code_group",
        codeItems,
      });

      i = nextIndex;
    } else if (token) {
      currentHtmlTokens.push(token as Tokens.Generic);
      i++;
    }
  }

  flushHtmlTokens();
  return sections;
}

export function MarkdownViewer({
  markdown,
  showLanguageToggle = true,
}: MarkdownViewerProps): React.JSX.Element {
  const [globalLanguage, setGlobalLanguage] = useState<string>("TypeScript");
  const sections = useMemo(() => parseMarkdownTokens(markdown), [markdown]);

  const hasMultiLanguageSnippets = useMemo(() => {
    return sections.some(
      (s) => s.type === "code_group" && s.codeItems && s.codeItems.length > 1
    );
  }, [sections]);

  return (
    <div className="rounded-xl border border-borderSubtle bg-bgSurface p-8 shadow-sm">
      {showLanguageToggle && hasMultiLanguageSnippets && (
        <div className="flex items-center justify-between pb-4 mb-6 border-b border-borderSubtle">
          <div className="flex items-center gap-2 text-xs font-medium text-textMuted">
            <Code2 className="h-4 w-4 text-accentPrimary" />
            <span>SDK Language:</span>
          </div>
          <div className="flex items-center gap-1.5 p-1 bg-surfaceContainer rounded-lg border border-borderSubtle">
            <button
              type="button"
              onClick={() => setGlobalLanguage("TypeScript")}
              className={`px-3 py-1 text-xs font-mono rounded-md transition-all cursor-pointer ${
                globalLanguage === "TypeScript"
                  ? "bg-bgSurface text-accentPrimary font-semibold shadow-xs border border-borderSubtle"
                  : "text-textMuted hover:text-textPrimary font-medium"
              }`}
            >
              TypeScript
            </button>
            <button
              type="button"
              onClick={() => setGlobalLanguage("Python")}
              className={`px-3 py-1 text-xs font-mono rounded-md transition-all cursor-pointer ${
                globalLanguage === "Python"
                  ? "bg-bgSurface text-accentPrimary font-semibold shadow-xs border border-borderSubtle"
                  : "text-textMuted hover:text-textPrimary font-medium"
              }`}
            >
              Python
            </button>
          </div>
        </div>
      )}

      <div className="markdown-content space-y-4">
        {sections.map((section) => {
          if (section.type === "code_group" && section.codeItems) {
            return (
              <DocCodeGroup
                key={section.id}
                items={section.codeItems}
                globalLanguage={globalLanguage}
              />
            );
          }
          return (
            <div
              key={section.id}
              dangerouslySetInnerHTML={{ __html: section.htmlContent || "" }}
            />
          );
        })}
      </div>
    </div>
  );
}
