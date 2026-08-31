import React from "react";
import { List } from "lucide-react";
import type { DocHeading } from "@/types/docsTypes";

export interface DocTableOfContentsProps {
  readonly headings: readonly DocHeading[];
}

const tocLabel = "On this page";
const subHeadingDepth = 3;

export function DocTableOfContents({
  headings,
}: DocTableOfContentsProps): React.JSX.Element | null {
  // A single-heading document does not need a contents list; showing one is noise.
  if (headings.length < 2) {
    return null;
  }

  return (
    <nav
      aria-label={tocLabel}
      // Stickiness lives on the aside wrapper in the docs route, which also holds the search
      // box; this element only has to cap its own height so a long contents list scrolls
      // inside the rail rather than past the bottom of the viewport.
      className="max-h-[calc(100vh-11rem)] overflow-y-auto custom-scrollbar"
    >
      <div className="mb-2 flex items-center gap-1.5">
        <List className="h-3.5 w-3.5 text-accentPrimary" />
        <span className="text-label-caps uppercase text-textMuted">{tocLabel}</span>
      </div>
      <ul className="space-y-1 border-l border-borderSubtle">
        {headings.map((heading) => (
          <li key={heading.id}>
            <a
              href={`#${heading.id}`}
              className={`block border-l-2 border-transparent py-0.5 text-body-sm leading-snug text-textMuted transition-colors hover:border-accentPrimary hover:text-textPrimary ${
                heading.depth === subHeadingDepth ? "pl-6" : "pl-3"
              }`}
            >
              {heading.text}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}
