"use client";

import React from "react";
import Link from "next/link";
import {
  ChevronLeft,
  ChevronRight,
  Layers,
  LayoutDashboard,
  Radio,
  ShieldCheck,
  Sparkles,
  Store,
  Terminal,
  Zap,
} from "lucide-react";

export interface NavItemConfig {
  readonly route: string;
  readonly label: string;
  readonly icon: React.ComponentType<{ className?: string }>;
  readonly description: string;
}

export interface AppSidebarProps {
  readonly isCollapsed: boolean;
  readonly onToggle: () => void;
  readonly activeRoute: string;
}

export const navigationItems: ReadonlyArray<NavItemConfig> = [
  {
    route: "/overview",
    label: "Overview",
    icon: LayoutDashboard,
    description: "Mesh Command Center",
  },
  {
    route: "/agent-observability",
    label: "Agent Observability",
    icon: Terminal,
    description: "MCP Reasoning Traces",
  },
  {
    route: "/negotiation-hub",
    label: "Negotiation Hub",
    icon: Layers,
    description: "B2B Dynamic Concessions",
  },
  {
    route: "/security-audit",
    label: "Security & Audit",
    icon: ShieldCheck,
    description: "AP2 Mandate Verification",
  },
  {
    route: "/self-healing",
    label: "Self-Healing",
    icon: Sparkles,
    description: "Vector Healer & SLA Watch",
  },
  {
    route: "/infrastructure",
    label: "Infrastructure",
    icon: Radio,
    description: "2PC Splits & Webhooks",
  },
  {
    route: "/merchant-studio",
    label: "Merchant Studio",
    icon: Store,
    description: "SKU Catalog & Pricing",
  },
];

const brandTitle = "RazorAgent Mesh";
const brandSubtitle = "v2.0 AP2 Enclave";
const expandLabel = "Expand sidebar";
const collapseLabel = "Collapse sidebar";

export function AppSidebar({
  isCollapsed,
  onToggle,
  activeRoute,
}: AppSidebarProps): React.JSX.Element {
  return (
    <aside
      className={`relative flex flex-col border-r border-borderSubtle bg-bgSurface transition-all duration-200 ease-in-out ${
        isCollapsed ? "w-16" : "w-60"
      }`}
    >
      <div className="flex h-14 items-center justify-between border-b border-borderSubtle px-3.5">
        <div className="flex items-center gap-2.5 overflow-hidden">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accentPrimary text-white">
            <Zap className="h-4 w-4" />
          </div>
          {!isCollapsed && (
            <div className="flex flex-col min-w-0">
              <span className="truncate text-xs font-semibold text-textPrimary">
                {brandTitle}
              </span>
              <span className="text-[10px] font-mono text-textMuted">{brandSubtitle}</span>
            </div>
          )}
        </div>
      </div>

      <nav className="flex-1 space-y-1 p-2 overflow-y-auto custom-scrollbar">
        {navigationItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeRoute === item.route || activeRoute.startsWith(`${item.route}/`);

          return (
            <Link
              key={item.route}
              href={item.route}
              title={isCollapsed ? item.label : undefined}
              className={`group flex items-center gap-3 rounded-lg px-2.5 py-2 text-xs font-medium transition-colors ${
                isActive
                  ? "bg-accentSubtle text-textPrimary font-semibold border-l-2 border-accentPrimary"
                  : "text-textSecondary hover:bg-bgSurfaceHover hover:text-textPrimary"
              } ${isCollapsed ? "justify-center px-0" : ""}`}
            >
              <Icon
                className={`h-4 w-4 shrink-0 transition-colors ${
                  isActive ? "text-accentPrimary" : "text-textMuted group-hover:text-textSecondary"
                }`}
              />
              {!isCollapsed && (
                <span className="truncate">{item.label}</span>
              )}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-borderSubtle p-2">
        <button
          type="button"
          onClick={onToggle}
          title={isCollapsed ? expandLabel : collapseLabel}
          className={`flex w-full items-center gap-2 rounded-lg p-2 text-xs font-medium text-textSecondary transition-colors hover:bg-bgSurfaceHover hover:text-textPrimary ${
            isCollapsed ? "justify-center" : ""
          }`}
        >
          {isCollapsed ? (
            <ChevronRight className="h-4 w-4 shrink-0 text-textMuted" />
          ) : (
            <>
              <ChevronLeft className="h-4 w-4 shrink-0 text-textMuted" />
              <span className="truncate">{collapseLabel}</span>
            </>
          )}
        </button>
      </div>
    </aside>
  );
}
