import React from "react";
import Link from "next/link";
import { ArrowLeft, ArrowRight } from "lucide-react";
import type { DocNavEntry } from "@/types/docsTypes";

export interface DocPaginationProps {
  readonly previous: DocNavEntry | null;
  readonly next: DocNavEntry | null;
}

const previousLabel = "Previous";
const nextLabel = "Next";
const linkClass =
  "flex min-w-0 flex-1 flex-col gap-0.5 rounded-lg border border-borderSubtle bg-bgSurface p-3 transition-colors hover:bg-bgSurfaceHover";

export function DocPagination({ previous, next }: DocPaginationProps): React.JSX.Element | null {
  if (!previous && !next) {
    return null;
  }

  return (
    <nav className="mt-8 flex flex-col gap-2 border-t border-borderSubtle pt-6 sm:flex-row">
      {previous ? (
        <Link href={previous.route} className={linkClass}>
          <span className="inline-flex items-center gap-1 text-[11px] uppercase tracking-wide text-textMuted">
            <ArrowLeft className="h-3 w-3" />
            {previousLabel}
          </span>
          <span className="truncate text-body-sm font-semibold text-textPrimary">
            {previous.navLabel}
          </span>
        </Link>
      ) : (
        // Keeps "Next" right-aligned on the first page instead of letting it slide left.
        <span className="hidden flex-1 sm:block" />
      )}

      {next && (
        <Link href={next.route} className={`${linkClass} sm:text-right`}>
          <span className="inline-flex items-center gap-1 text-[11px] uppercase tracking-wide text-textMuted sm:justify-end">
            {nextLabel}
            <ArrowRight className="h-3 w-3" />
          </span>
          <span className="truncate text-body-sm font-semibold text-textPrimary">
            {next.navLabel}
          </span>
        </Link>
      )}
    </nav>
  );
}
