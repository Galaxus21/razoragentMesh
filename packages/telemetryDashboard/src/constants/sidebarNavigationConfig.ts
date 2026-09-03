import React from "react";
import {
  BookOpen,
  Bot,
  Briefcase,
  FlaskConical,
  Server,
  Store,
} from "lucide-react";
import { docsManifest } from "@/generated/docsManifest";

export interface NavChildItemConfig {
  readonly route: string;
  readonly label: string;
  readonly description?: string;
  readonly icon?: React.ComponentType<{ className?: string }>;
}

export interface NavCategoryConfig {
  readonly id: string;
  readonly label: string;
  readonly icon: React.ComponentType<{ className?: string }>;
  readonly children: ReadonlyArray<NavChildItemConfig>;
}

const documentationNavChildren: ReadonlyArray<NavChildItemConfig> = docsManifest.map((entry) => ({
  route: entry.route,
  label: entry.navLabel,
  description: entry.navDescription,
}));

export const navigationCategories: ReadonlyArray<NavCategoryConfig> = [
  {
    id: "platformOps",
    label: "Platform Ops",
    icon: Server,
    children: [
      { route: "/overview", label: "Overview", description: "Mesh Command Center" },
      { route: "/self-healing", label: "Self-Healing", description: "Vector Healer & SLA Watch" },
      { route: "/infrastructure", label: "Infrastructure", description: "2PC Splits & Webhooks" },
    ],
  },
  // The protocol surfaces a reviewer needs -- read the layer, then exercise it -- used to be
  // split across Platform Ops (the map) and AI Buyer Agents (the two playgrounds and the SDK
  // console), so evaluating one layer end to end meant hopping between two categories. They are
  // one section now, ordered map-then-run so a reader meets the protocol before driving it.
  {
    id: "protocolPlayground",
    label: "Protocol Playground",
    icon: FlaskConical,
    children: [
      { route: "/protocol", label: "Protocol Map", description: "Six Layers, Probed Live" },
      { route: "/playground/layers", label: "Layer Explorer", description: "Packages At Each Stage" },
      { route: "/playground", label: "Run The Protocol", description: "Scenarios End To End" },
      { route: "/playground/adversarial", label: "Adversarial Playground", description: "Break It On Purpose" },
      // Sits beside the two playgrounds because it is the same protocol view driven from
      // outside: an external agent's MCP calls, grouped by session, rather than a run this
      // dashboard started.
      { route: "/playground/live-agent", label: "Live Agent", description: "Watch An External Agent" },
      { route: "/sdk-console", label: "SDK Console", description: "Call The SDK Yourself" },
    ],
  },
  {
    id: "aiBuyerAgents",
    label: "AI Buyer Agents",
    icon: Bot,
    children: [
      { route: "/agent-observability", label: "Agent Observability", description: "MCP Reasoning Traces" },
      { route: "/negotiation-hub", label: "Negotiation Hub", description: "B2B Dynamic Concessions" },
    ],
  },
  {
    id: "cfosAuditors",
    label: "CFOs & Auditors",
    icon: Briefcase,
    children: [
      { route: "/security-audit", label: "Security & Audit", description: "AP2 Mandate Verification" },
    ],
  },
  {
    id: "merchants",
    label: "Merchants",
    icon: Store,
    children: [
      { route: "/merchant-studio", label: "Merchant Studio", description: "SKU Catalog & Pricing" },
    ],
  },
  {
    id: "documentation",
    label: "Documentation",
    icon: BookOpen,
    // Derived from the frontmatter of docs/**/*.mdx via src/generated/docsManifest.ts, so a new
    // guide appears in the sidebar by existing. This list used to be maintained by hand next to
    // two more hand-maintained maps in docsLoader, giving three places to forget.
    children: documentationNavChildren,
  },
];

export const navigationItems: ReadonlyArray<NavChildItemConfig> =
  navigationCategories.flatMap((category) => category.children);

export const brandTitle = "RazorAgent Mesh";
export const brandSubtitle = "v2.0 AP2 Enclave";
export const expandLabel = "Expand sidebar";
export const collapseLabel = "Collapse sidebar";

export const defaultExpandedCategories: Record<string, boolean> = {
  platformOps: true,
  protocolPlayground: true,
  aiBuyerAgents: true,
  cfosAuditors: true,
  merchants: true,
  documentation: true,
};

// Prefix matching alone is ambiguous once routes nest: "/playground/adversarial" is a prefix
// match for BOTH "/playground" and itself, which would light up two sidebar rows at once. An
// item is active only when it is the LONGEST registered route that matches, so the most
// specific page wins and exactly one row highlights.
export function isRouteMatching(activeRoute: string, targetRoute: string): boolean {
  if (!isRoutePrefixOf(activeRoute, targetRoute)) {
    return false;
  }
  const longestMatch = navigationItems.reduce<string>((longest, item) => {
    if (isRoutePrefixOf(activeRoute, item.route) && item.route.length > longest.length) {
      return item.route;
    }
    return longest;
  }, "");
  return targetRoute === longestMatch;
}

function isRoutePrefixOf(activeRoute: string, targetRoute: string): boolean {
  return activeRoute === targetRoute || activeRoute.startsWith(`${targetRoute}/`);
}

export function isCategoryActive(category: NavCategoryConfig, activeRoute: string): boolean {
  return category.children.some((child) => isRouteMatching(activeRoute, child.route));
}
