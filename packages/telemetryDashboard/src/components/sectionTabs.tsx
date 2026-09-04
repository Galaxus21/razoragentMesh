"use client";

// The tab strip that replaced ten sidebar rows.
//
// Merchant and Visualise each own several pages. Giving every one of them its own sidebar entry
// is what made the old navigation hard to read, so a section's pages are reached from here and
// the sidebar carries only the four sections.

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { SectionTabConfig } from "@/constants/sidebarNavigationConfig";
import { isTabActive } from "@/constants/sidebarNavigationConfig";

interface SectionTabsProps {
  readonly tabs: ReadonlyArray<SectionTabConfig>;
}

export function SectionTabs({ tabs }: SectionTabsProps): React.JSX.Element {
  const pathname = usePathname();

  return (
    <nav
      aria-label="Section pages"
      className="flex flex-wrap items-center gap-1 border-b border-borderSubtle pb-2"
    >
      {tabs.map((tab) => {
        const isActive = isTabActive(pathname, tab.route);
        return (
          <Link
            key={tab.route}
            href={tab.route}
            aria-current={isActive ? "page" : undefined}
            className={`rounded-md px-3 py-1.5 text-label-sm font-semibold transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accentPrimary ${
              isActive
                ? "bg-accentPrimary/10 text-accentPrimary"
                : "text-textSecondary hover:bg-bgSurfaceHover hover:text-textPrimary"
            }`}
          >
            {tab.label}
          </Link>
        );
      })}
    </nav>
  );
}
