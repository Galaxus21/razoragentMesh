"use client";

import React, { useCallback, useState } from "react";
import Link from "next/link";
import { ChevronDown, ChevronLeft, ChevronRight, Zap } from "lucide-react";
import {
  brandSubtitle,
  brandTitle,
  collapseLabel,
  defaultExpandedCategories,
  expandLabel,
  isCategoryActive,
  isRouteMatching,
  navigationCategories,
  navigationItems,
  NavCategoryConfig,
  NavChildItemConfig,
} from "../constants/sidebarNavigationConfig";

export {
  brandSubtitle,
  brandTitle,
  collapseLabel,
  defaultExpandedCategories,
  expandLabel,
  isCategoryActive,
  isRouteMatching,
  navigationCategories,
  navigationItems,
};
export type { NavCategoryConfig, NavChildItemConfig };

export interface AppSidebarProps {
  readonly isCollapsed: boolean;
  readonly onToggle: () => void;
  readonly activeRoute: string;
}

interface CollapsedCategoryButtonProps {
  readonly category: NavCategoryConfig;
  readonly isActive: boolean;
  readonly onExpand: () => void;
}

function CollapsedCategoryButton({ category, isActive, onExpand }: CollapsedCategoryButtonProps): React.JSX.Element {
  const Icon = category.icon;
  return (
    <button
      type="button"
      onClick={onExpand}
      title={category.label}
      aria-label={category.label}
      className={`group flex h-10 w-full items-center justify-center rounded-lg transition-colors ${
        isActive ? "bg-accentSubtle text-accentPrimary border-l-2 border-accentPrimary" : "text-textSecondary hover:bg-bgSurfaceHover hover:text-textPrimary"
      }`}
    >
      <Icon className={`h-4 w-4 shrink-0 transition-colors ${isActive ? "text-accentPrimary" : "text-textMuted group-hover:text-textSecondary"}`} />
    </button>
  );
}

interface ChildRouteLinkProps {
  readonly item: NavChildItemConfig;
  readonly isActive: boolean;
}

function ChildRouteLink({ item, isActive }: ChildRouteLinkProps): React.JSX.Element {
  return (
    <Link
      href={item.route}
      title={item.description ?? item.label}
      className={`group flex items-center rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors ${
        isActive ? "bg-accentSubtle text-textPrimary font-semibold border-l-2 border-accentPrimary" : "text-textSecondary hover:bg-bgSurfaceHover hover:text-textPrimary"
      }`}
    >
      <span className="truncate">{item.label}</span>
    </Link>
  );
}

interface CategoryAccordionProps {
  readonly category: NavCategoryConfig;
  readonly isExpanded: boolean;
  readonly activeRoute: string;
  readonly onToggleAccordion: (categoryId: string) => void;
}

function CategoryAccordion({ category, isExpanded, activeRoute, onToggleAccordion }: CategoryAccordionProps): React.JSX.Element {
  const Icon = category.icon;
  const isParentActive = isCategoryActive(category, activeRoute);

  return (
    <div className="space-y-0.5">
      <button
        type="button"
        onClick={() => onToggleAccordion(category.id)}
        className={`flex w-full items-center justify-between rounded-lg px-2.5 py-2 text-xs font-semibold transition-colors ${
          isParentActive ? "text-accentPrimary" : "text-textMuted hover:bg-bgSurfaceHover hover:text-textPrimary"
        }`}
      >
        <div className="flex items-center gap-2.5 min-w-0">
          <Icon className="h-4 w-4 shrink-0 text-textMuted" />
          <span className="truncate uppercase tracking-wider text-[11px]">{category.label}</span>
        </div>
        {isExpanded ? <ChevronDown className="h-3.5 w-3.5 shrink-0 text-textMuted" /> : <ChevronRight className="h-3.5 w-3.5 shrink-0 text-textMuted" />}
      </button>

      {isExpanded && (
        <div className="ml-3 space-y-0.5 border-l border-borderSubtle pl-2">
          {category.children.map((child) => (
            <ChildRouteLink key={child.route} item={child} isActive={isRouteMatching(activeRoute, child.route)} />
          ))}
        </div>
      )}
    </div>
  );
}

function SidebarBrandHeader({ isCollapsed }: { readonly isCollapsed: boolean }): React.JSX.Element {
  return (
    <div className="flex h-14 items-center justify-between border-b border-borderSubtle px-3.5">
      <div className="flex items-center gap-2.5 overflow-hidden">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accentPrimary text-white"><Zap className="h-4 w-4" /></div>
        {!isCollapsed && (
          <div className="flex flex-col min-w-0">
            <span className="truncate text-xs font-semibold text-textPrimary">{brandTitle}</span>
            <span className="text-[10px] font-mono text-textMuted">{brandSubtitle}</span>
          </div>
        )}
      </div>
    </div>
  );
}

function SidebarFooterToggle({ isCollapsed, onToggle }: { readonly isCollapsed: boolean; readonly onToggle: () => void }): React.JSX.Element {
  return (
    <div className="border-t border-borderSubtle p-2">
      <button type="button" onClick={onToggle} title={isCollapsed ? expandLabel : collapseLabel} className={`flex w-full items-center gap-2 rounded-lg p-2 text-xs font-medium text-textSecondary transition-colors hover:bg-bgSurfaceHover hover:text-textPrimary ${isCollapsed ? "justify-center" : ""}`}>
        {isCollapsed ? <ChevronRight className="h-4 w-4 shrink-0 text-textMuted" /> : <><ChevronLeft className="h-4 w-4 shrink-0 text-textMuted" /><span className="truncate">{collapseLabel}</span></>}
      </button>
    </div>
  );
}

export function AppSidebar({ isCollapsed, onToggle, activeRoute }: AppSidebarProps): React.JSX.Element {
  const [expandedCategories, setExpandedCategories] = useState<Record<string, boolean>>(defaultExpandedCategories);

  const handleToggleCategory = useCallback((categoryId: string) => {
    setExpandedCategories((prev) => ({ ...prev, [categoryId]: !prev[categoryId] }));
  }, []);

  const handleExpandFromCollapsed = useCallback(
    (categoryId: string) => {
      setExpandedCategories((prev) => ({ ...prev, [categoryId]: true }));
      onToggle();
    },
    [onToggle]
  );

  return (
    <aside className={`relative flex flex-col border-r border-borderSubtle bg-bgSurface transition-all duration-200 ease-in-out ${isCollapsed ? "w-16" : "w-60"}`}>
      <SidebarBrandHeader isCollapsed={isCollapsed} />
      <nav className="flex-1 space-y-2 p-2 overflow-y-auto custom-scrollbar">
        {isCollapsed
          ? navigationCategories.map((category) => (
              <CollapsedCategoryButton key={category.id} category={category} isActive={isCategoryActive(category, activeRoute)} onExpand={() => handleExpandFromCollapsed(category.id)} />
            ))
          : navigationCategories.map((category) => (
              <CategoryAccordion key={category.id} category={category} isExpanded={Boolean(expandedCategories[category.id])} activeRoute={activeRoute} onToggleAccordion={handleToggleCategory} />
            ))}
      </nav>
      <SidebarFooterToggle isCollapsed={isCollapsed} onToggle={onToggle} />
    </aside>
  );
}
