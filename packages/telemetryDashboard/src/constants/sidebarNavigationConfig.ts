import React from "react";
import {
  BookOpen,
  Bot,
  Briefcase,
  Server,
  Store,
} from "lucide-react";

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
    children: [
      { route: "/docs/setup", label: "System Setup", description: "Environment & Architecture Setup" },
      { route: "/docs/onboarding", label: "Developer Onboarding", description: "End-to-End Integration Guide" },
      { route: "/docs/buyer-sdk", label: "Buyer SDK", description: "TypeScript & Python SDK Guide" },
      { route: "/docs/merchant-guide", label: "Merchant Guide", description: "Catalog Ingestion & Pricing" },
      { route: "/docs/telemetry", label: "Telemetry & SSE", description: "Observability Event Streams" },
      { route: "/docs/gstr1-invoice", label: "GSTR-1 Invoicing", description: "Statutory Tax Specification" },
    ],
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
  aiBuyerAgents: true,
  cfosAuditors: true,
  merchants: true,
  documentation: true,
};

export function isRouteMatching(activeRoute: string, targetRoute: string): boolean {
  return activeRoute === targetRoute || activeRoute.startsWith(`${targetRoute}/`);
}

export function isCategoryActive(category: NavCategoryConfig, activeRoute: string): boolean {
  return category.children.some((child) => isRouteMatching(activeRoute, child.route));
}
