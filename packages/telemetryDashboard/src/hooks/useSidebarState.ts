"use client";

import { useCallback, useEffect, useState } from "react";

export interface UseSidebarStateResult {
  readonly isCollapsed: boolean;
  readonly isHydrated: boolean;
  readonly toggleSidebar: () => void;
  readonly setCollapsed: (collapsed: boolean) => void;
}

export const sidebarStorageKey = "razormesh-sidebar";
export const defaultSidebarCollapsed = false;

export function useSidebarState(): UseSidebarStateResult {
  const [isCollapsed, setIsCollapsed] = useState<boolean>(defaultSidebarCollapsed);
  const [isHydrated, setIsHydrated] = useState<boolean>(false);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(sidebarStorageKey);
      if (stored !== null) {
        setIsCollapsed(stored === "true");
      }
    } catch {
      // LocalStorage access may be restricted in sandboxed iframes or private modes
    } finally {
      setIsHydrated(true);
    }
  }, []);

  const setCollapsed = useCallback((collapsed: boolean) => {
    setIsCollapsed(collapsed);
    try {
      window.localStorage.setItem(sidebarStorageKey, String(collapsed));
    } catch {
      // Ignore storage write failures
    }
  }, []);

  const toggleSidebar = useCallback(() => {
    setIsCollapsed((previousState) => {
      const nextState = !previousState;
      try {
        window.localStorage.setItem(sidebarStorageKey, String(nextState));
      } catch {
        // Ignore storage write failures
      }
      return nextState;
    });
  }, []);

  return {
    isCollapsed,
    isHydrated,
    toggleSidebar,
    setCollapsed,
  };
}
