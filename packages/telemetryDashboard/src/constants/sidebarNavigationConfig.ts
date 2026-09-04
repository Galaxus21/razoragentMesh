import React from "react";
import { Activity, BookOpen, LayoutDashboard, Store } from "lucide-react";
import { docsManifest } from "@/generated/docsManifest";

export interface NavChildItemConfig {
  readonly route: string;
  readonly label: string;
  readonly description?: string;
  readonly icon?: React.ComponentType<{ className?: string }>;
  /** Sidebar group heading. Only the documentation category sets it. */
  readonly section?: string;
}

export interface NavCategoryConfig {
  readonly id: string;
  readonly label: string;
  readonly icon: React.ComponentType<{ className?: string }>;
  readonly children: ReadonlyArray<NavChildItemConfig>;
}

/**
 * The documentation landing page, above the grouped guides.
 *
 * It carries no section, which is what floats it above the first heading -- see
 * documentationSectionOrder. It is written here rather than derived from the manifest
 * because it is a route, not a guide: there is no .mdx file behind it.
 */
const documentationIndexChild: NavChildItemConfig = {
  route: "/docs",
  label: "All docs",
  description: "Every Guide & Reference",
};

const documentationNavChildren: ReadonlyArray<NavChildItemConfig> = [
  documentationIndexChild,
  ...docsManifest.map((entry) => ({
    route: entry.route,
    label: entry.navLabel,
    description: entry.navDescription,
    section: entry.section,
  })),
];

/**
 * The order documentation groups appear in, which is the order a reader needs them.
 *
 * Listed explicitly rather than discovered from the manifest, because discovery would order
 * the groups by whichever file happened to sort first -- so adding a guide could silently put
 * Reference above Get started. A section named in frontmatter but missing here renders after
 * these, in encounter order, rather than disappearing.
 */
export const documentationSectionOrder: ReadonlyArray<string> = [
  // An item with no section renders first, above every heading. That is the docs landing
  // page's slot: it introduces the groups rather than belonging to one of them.
  "",
  "Get started",
  "Guides",
  "Reference",
];

export interface NavChildGroup {
  readonly section: string;
  readonly items: ReadonlyArray<NavChildItemConfig>;
}

/** Groups a category's children by section, preserving each section's internal order. */
export function groupChildrenBySection(
  children: ReadonlyArray<NavChildItemConfig>
): ReadonlyArray<NavChildGroup> {
  const bySection = new Map<string, NavChildItemConfig[]>();
  for (const child of children) {
    const section = child.section ?? "";
    const bucket = bySection.get(section) ?? [];
    bucket.push(child);
    bySection.set(section, bucket);
  }

  const ranked = [...bySection.keys()].sort((left, right) => {
    const leftRank = documentationSectionOrder.indexOf(left);
    const rightRank = documentationSectionOrder.indexOf(right);
    // Unknown sections sort after known ones rather than jumping to the top.
    return (
      (leftRank === -1 ? Number.MAX_SAFE_INTEGER : leftRank) -
      (rightRank === -1 ? Number.MAX_SAFE_INTEGER : rightRank)
    );
  });

  return ranked.map((section) => ({ section, items: bySection.get(section) ?? [] }));
}

// Four sections, down from six categories over fourteen routes.
//
// The old shape gave every telemetry panel its own route -- Agent Observability, Negotiation Hub,
// Security & Audit, Self-Healing and Infrastructure were each a page containing exactly one panel
// fed by the same SSE event array. Watching a purchase therefore meant opening five pages that
// were all reacting to the same stream, and no single screen ever showed the run happening. Those
// five panels now sit together under Visualise, which is the screen a reader watches while an
// agent buys something.
//
// Sub-pages inside Merchant and Visualise are reached by a tab strip in each section's layout
// rather than by their own sidebar rows, so the sidebar states what the dashboard is for -- see
// the mesh, sell into it, watch it run, read about it -- instead of enumerating its panels.
export const navigationCategories: ReadonlyArray<NavCategoryConfig> = [
  {
    id: "overview",
    label: "Overview",
    icon: LayoutDashboard,
    children: [
      { route: "/overview", label: "Overview", description: "The Stack & Its Health" },
    ],
  },
  {
    id: "merchant",
    label: "Merchant",
    icon: Store,
    children: [
      { route: "/merchant-studio", label: "Merchant", description: "Products, Offers & Pricing" },
    ],
  },
  {
    id: "visualise",
    label: "Visualise",
    icon: Activity,
    children: [
      { route: "/visualise", label: "Visualise", description: "Watch The Protocol Run" },
    ],
  },
  {
    id: "documentation",
    label: "Docs",
    icon: BookOpen,
    // Derived from the frontmatter of docs/**/*.mdx via src/generated/docsManifest.ts, so a new
    // guide appears in the sidebar by existing.
    children: documentationNavChildren,
  },
];

export const navigationItems: ReadonlyArray<NavChildItemConfig> =
  navigationCategories.flatMap((category) => category.children);

// The tab strips. Kept here beside the sidebar routes because these are the rest of the
// dashboard's navigable surface: a route that appears in neither list is unreachable.
export interface SectionTabConfig {
  readonly route: string;
  readonly label: string;
}

// Merchant has no tab strip: it is one screen for one job, publishing inventory. It used to
// carry a second tab, "Human Checkout", which let a person shop the catalog and pay for a SKU.
// That is a storefront, not merchant tooling -- and because it could create a Razorpay order, it
// was also the one screen able to settle money against an order no mandate pointed at. The
// order-completion half of it now lives at /visualise/settle, where an agent run actually ends.
export const visualiseSectionTabs: ReadonlyArray<SectionTabConfig> = [
  { route: "/visualise", label: "Live Agent" },
  { route: "/visualise/settle", label: "Settle" },
  { route: "/visualise/run", label: "Run It Here" },
  { route: "/visualise/adversarial", label: "Adversarial" },
  { route: "/visualise/vectors", label: "Vector Index" },
];

export const sectionTabs: ReadonlyArray<SectionTabConfig> = [...visualiseSectionTabs];

/**
 * Where the reader currently is, for the header.
 *
 * The header used to print a fixed "Autonomous Settlement Enclave / Razorpay Route Rails" above
 * every screen. It was a slogan rather than a label: it said the same thing on the merchant
 * console, the docs and the live run, so it could not tell you which of them you were looking at,
 * and it restated the brand the sidebar already shows two inches to its left. A header's job is
 * orientation, so it now names the page.
 *
 * Resolution is longest-prefix over every registered route, tabs included, which is what makes
 * /visualise/settle resolve to "Settle" rather than to "/visualise" -- the same rule
 * isRouteMatching uses to light exactly one sidebar row.
 */
export interface PageLocation {
  readonly title: string;
  readonly section: string | null;
}

export function resolvePageLocation(activeRoute: string): PageLocation {
  // Tabs first, and ties keep the earlier entry: /visualise is registered BOTH as the
  // Visualise sidebar row and as its "Live Agent" tab, at identical length. The tab is the
  // more specific answer -- it names the screen, while the sidebar row names the section the
  // screen belongs to, which is what the section field then carries.
  const candidates: ReadonlyArray<NavChildItemConfig> = [...sectionTabs, ...navigationItems];

  let best: NavChildItemConfig | null = null;
  for (const candidate of candidates) {
    if (!isRoutePrefixOf(activeRoute, candidate.route)) {
      continue;
    }
    if (!best || candidate.route.length > best.route.length) {
      best = candidate;
    }
  }

  if (!best) {
    return { title: brandTitle, section: null };
  }

  const owningCategory = navigationCategories.find((category) =>
    isCategoryActive(category, activeRoute)
  );

  // A category whose only child IS this page would print its own name twice ("Merchant /
  // Merchant"), so the section is dropped when it adds nothing.
  const section =
    owningCategory && owningCategory.label !== best.label ? owningCategory.label : null;

  return { title: best.label, section };
}

export const brandTitle = "RazorAgent Mesh";
export const expandLabel = "Expand sidebar";
export const collapseLabel = "Collapse sidebar";

export const defaultExpandedCategories: Record<string, boolean> = {
  overview: true,
  merchant: true,
  visualise: true,
  documentation: true,
};

// Prefix matching alone is ambiguous once routes nest: "/visualise/run" is a prefix match
// for BOTH "/visualise" and itself, which would light up two rows at once. A row is active only
// when it is the LONGEST registered route that matches. Tab routes are included in the candidate
// set so that standing on /visualise/settle still resolves to the Visualise sidebar row rather
// than lighting nothing, while the tab strip highlights the exact page.
const routeMatchCandidates: ReadonlyArray<string> = [
  ...navigationItems.map((item) => item.route),
  ...sectionTabs.map((tab) => tab.route),
];

export function isRouteMatching(activeRoute: string, targetRoute: string): boolean {
  if (!isRoutePrefixOf(activeRoute, targetRoute)) {
    return false;
  }
  const longestMatch = routeMatchCandidates.reduce<string>((longest, candidate) => {
    if (isRoutePrefixOf(activeRoute, candidate) && candidate.length > longest.length) {
      return candidate;
    }
    return longest;
  }, "");
  return targetRoute === longestMatch;
}

function isRoutePrefixOf(activeRoute: string, targetRoute: string): boolean {
  return activeRoute === targetRoute || activeRoute.startsWith(`${targetRoute}/`);
}

// A sidebar row stays lit while the reader is on any of that section's tabs, which prefix
// matching gives for free: /visualise/run starts with /visualise.
export function isCategoryActive(category: NavCategoryConfig, activeRoute: string): boolean {
  return category.children.some((child) => isRoutePrefixOf(activeRoute, child.route));
}

export function isTabActive(activeRoute: string, tabRoute: string): boolean {
  return isRouteMatching(activeRoute, tabRoute);
}
